"""
performance_analyzer.py

Measures how fast a Java program runs and how much memory it allocates,
so the optimizer can decide whether an optional Java 21 change is worth
keeping.

What this version does (in simple words)
----------------------------------------
1. It compiles the WHOLE project (when a project folder is known), with
   the one changed file swapped in. If that is impossible it falls back
   to compiling the single file alone.
2. It finds the real entry class (with its package name) by asking the
   compiled classes, not by guessing from text.
3. It runs the program inside ONE Java process many times (a small
   helper class called BenchHarness), so Java start-up noise does not
   disturb the timing.
4. It measures:
      - time of each call to main()      (median, in ms)
      - bytes allocated by each call     (median, in MB)
5. It also records a fingerprint (SHA-256) of everything the program
   prints, so the optimizer can reject a change that alters the output.

It does NOT measure Big-O complexity. It measures real time and real
allocated memory for the program as it is written.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ----------------------------------------------------------------------
# Small Java helper that runs main() many times inside ONE JVM
# ----------------------------------------------------------------------

_HARNESS_SOURCE = r'''
import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.lang.management.ManagementFactory;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;

public class BenchHarness {

    public static void main(String[] args) throws Exception {
        String className = args[0];
        int warmup = Integer.parseInt(args[1]);
        int runs = Integer.parseInt(args[2]);
        long budgetNs = Long.parseLong(args[3]) * 1_000_000L;

        PrintStream realOut = System.out;
        PrintStream realErr = System.err;

        Method main;
        try {
            main = Class.forName(className).getMethod("main", String[].class);
            main.setAccessible(true);
        } catch (Throwable t) {
            realOut.println("ERR cannot load main of " + className + ": " + t);
            System.exit(3);
            return;
        }

        com.sun.management.ThreadMXBean mx = null;
        try {
            mx = (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();
        } catch (Throwable ignored) {
        }
        long tid = Thread.currentThread().threadId();

        long[] times = new long[runs];
        long[] bytes = new long[runs];
        int measured = 0;
        String hash = null;
        long startAll = System.nanoTime();
        int total = warmup + runs;

        for (int i = 0; i < total; i++) {
            boolean isWarm = i < warmup;

            if (isWarm && i > 0 && System.nanoTime() - startAll > budgetNs / 2) {
                i = warmup - 1;
                continue;
            }
            if (!isWarm && measured >= 3 && System.nanoTime() - startAll > budgetNs) {
                break;
            }

            ByteArrayOutputStream sink = new ByteArrayOutputStream();
            PrintStream ps = new PrintStream(sink, false, StandardCharsets.UTF_8);
            System.setOut(ps);
            System.setErr(ps);

            long b0 = mx != null ? mx.getThreadAllocatedBytes(tid) : 0L;
            long t0 = System.nanoTime();
            Throwable failure = null;
            try {
                main.invoke(null, (Object) new String[0]);
            } catch (InvocationTargetException e) {
                failure = e.getCause();
            } catch (Throwable e) {
                failure = e;
            }
            long t1 = System.nanoTime();
            long b1 = mx != null ? mx.getThreadAllocatedBytes(tid) : 0L;

            ps.flush();
            System.setOut(realOut);
            System.setErr(realErr);

            if (failure != null) {
                realOut.println("ERR program threw " + failure);
                System.exit(3);
            }
            if (i == 0) {
                hash = sha256(sink.toByteArray());
            }
            if (!isWarm) {
                times[measured] = t1 - t0;
                bytes[measured] = b1 - b0;
                measured++;
            }
        }

        Arrays.sort(times, 0, measured);
        Arrays.sort(bytes, 0, measured);
        realOut.println("BENCH " + times[measured / 2] + " " + bytes[measured / 2]
                + " " + hash + " " + measured);
    }

    private static String sha256(byte[] data) throws Exception {
        byte[] d = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder sb = new StringBuilder();
        for (byte x : d) {
            sb.append(String.format("%02x", x));
        }
        return sb.toString();
    }
}
'''


@dataclass
class BenchmarkResult:
    """Stores the result of one Java benchmark."""

    success: bool
    runtime_ms: Optional[float] = None
    memory_mb: Optional[float] = None     # MB ALLOCATED per call of main()
    runs: int = 0
    warmup_runs: int = 0
    error: Optional[str] = None
    output_hash: Optional[str] = None     # fingerprint of what the program prints
    entry_class: Optional[str] = None     # e.g. com.acme.added.Lists
    mode: Optional[str] = None            # "project" or "single-file"

    def __str__(self) -> str:
        if not self.success:
            return f"Benchmark failed: {self.error}"

        runtime = (
            f"{self.runtime_ms:.3f} ms"
            if self.runtime_ms is not None
            else "N/A"
        )

        memory = (
            f"{self.memory_mb:.3f} MB"
            if self.memory_mb is not None
            else "N/A"
        )

        return (
            f"Runtime: {runtime}, "
            f"Allocated: {memory}, "
            f"Runs: {self.runs}, "
            f"Mode: {self.mode}"
        )


class PerformanceAnalyzer:
    """
    Compile and benchmark Java code.

    Typical use by the optimizer:

        analyzer.set_project(Path("path/to/migrated/project"))
        result = analyzer.benchmark(new_source, "com/acme/Foo.java")

    If no project folder is set, the single file is compiled alone
    (still package-aware).
    """

    _SKIP_DIRS = {
        ".git", ".svn", ".hg", ".idea", ".vscode", "__pycache__",
        ".pytest_cache", "target", "build", "out", ".gradle", ".mvn",
    }

    def __init__(
        self,
        java_command: str = "java",
        javac_command: str = "javac",
        javap_command: str = "javap",
        warmup_runs: int = 5,
        measured_runs: int = 15,
        jvm_launches: int = 3,
        timeout_seconds: int = 60,
    ) -> None:
        if warmup_runs < 0:
            raise ValueError("warmup_runs must be >= 0")

        if measured_runs <= 0:
            raise ValueError("measured_runs must be > 0")

        if jvm_launches <= 0:
            raise ValueError("jvm_launches must be > 0")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

        self.java_command = java_command
        self.javac_command = javac_command
        self.javap_command = javap_command
        self.warmup_runs = warmup_runs
        self.measured_runs = measured_runs
        self.jvm_launches = jvm_launches
        self.timeout_seconds = timeout_seconds

        self.project_root: Optional[Path] = None
        self.entry_class: Optional[str] = None
        self._harness_dir: Optional[Path] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_project(
        self,
        project_root: Optional[Path],
        entry_class: Optional[str] = None,
    ) -> None:
        """
        Tell the analyzer where the whole (migrated) project lives.

        entry_class (optional): fully qualified class whose main() should
        be run instead of the changed file's own main(). Useful when the
        changed file is a library class without main().
        """
        self.project_root = (
            Path(project_root).resolve() if project_root else None
        )
        self.entry_class = entry_class

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def benchmark(
        self,
        source_code: str,
        filename: str = "",
    ) -> BenchmarkResult:
        """
        Compile and benchmark Java source code.

        filename: path of the file relative to the project root, for
        example "com/acme/Foo.java".
        """

        if not source_code.strip():
            return BenchmarkResult(
                success=False,
                error="Java source is empty.",
            )

        java_filename = self._java_filename(source_code, filename)
        package = self._package_of(source_code)

        harness_dir = self._ensure_harness()
        if isinstance(harness_dir, str):
            return BenchmarkResult(success=False, error=harness_dir)

        temp_dir = Path(tempfile.mkdtemp(prefix="java21_optimizer_"))

        try:
            changed_path = temp_dir / "changed" / java_filename
            changed_path.parent.mkdir(parents=True, exist_ok=True)
            changed_path.write_text(source_code, encoding="utf-8")

            classes_dir = temp_dir / "classes"
            classes_dir.mkdir()

            mode = "single-file"
            compiled = False
            project_error = None

            # ---- Try 1: the whole project, with this file swapped in --
            if self.project_root is not None and filename:
                others = self._project_sources(
                    self.project_root, filename
                )
                if others is not None:
                    ok, err = self._compile(
                        [*others, changed_path], classes_dir, temp_dir
                    )
                    if ok:
                        mode = "project"
                        compiled = True
                    else:
                        project_error = err
                        shutil.rmtree(classes_dir, ignore_errors=True)
                        classes_dir.mkdir()

            # ---- Try 2: this file alone ------------------------------
            if not compiled:
                ok, err = self._compile(
                    [changed_path], classes_dir, temp_dir
                )
                if not ok:
                    message = err or "Compilation failed."
                    if project_error:
                        message = (
                            "Whole-project compile failed:\n"
                            f"{project_error}\n\n"
                            "Single-file compile also failed:\n"
                            f"{message}"
                        )
                    return BenchmarkResult(success=False, error=message)

            # ---- Find what to run ------------------------------------
            entry = self.entry_class or self._find_entry_class(
                classes_dir, java_filename, package
            )

            if entry is None:
                return BenchmarkResult(
                    success=False,
                    error=(
                        f"{java_filename} has no "
                        "'public static void main(String[] args)', so "
                        "there is nothing to run. Use "
                        "set_project(root, entry_class=...) to run the "
                        "project's real main class instead."
                    ),
                )

            result = self._run_benchmark(
                harness_dir, classes_dir, entry
            )
            result.entry_class = entry
            result.mode = mode
            return result

        except Exception as exc:
            return BenchmarkResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Harness (compiled once, reused)
    # ------------------------------------------------------------------

    def _ensure_harness(self):
        """Returns the harness directory, or an error string."""

        if self._harness_dir is not None and self._harness_dir.exists():
            return self._harness_dir

        directory = Path(tempfile.mkdtemp(prefix="java21_harness_"))
        atexit.register(shutil.rmtree, directory, True)

        source = directory / "BenchHarness.java"
        source.write_text(_HARNESS_SOURCE, encoding="utf-8")

        ok, err = self._compile([source], directory, directory)
        if not ok:
            return f"Could not compile the benchmark helper: {err}"

        self._harness_dir = directory
        return directory

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------

    def _compile(
        self,
        sources: list[Path],
        out_dir: Path,
        scratch_dir: Path,
    ) -> tuple[bool, Optional[str]]:
        """Compile the given files with javac (uses an @argfile)."""

        argfile = scratch_dir / f"javac_args_{os.getpid()}_{id(sources)}.txt"
        lines = [
            "-encoding", "UTF-8",
            "-proc:none",
            "-nowarn",
            "-Xlint:none",
            "-d", str(out_dir),
            *[str(s) for s in sources],
        ]
        argfile.write_text(
            "\n".join(self._quote(x) for x in lines),
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [self.javac_command, f"@{argfile}"],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds * 3,
            )

        except FileNotFoundError:
            return (
                False,
                (
                    f"'{self.javac_command}' was not found. "
                    "Make sure JDK 21 is installed and javac is in PATH."
                ),
            )

        except subprocess.TimeoutExpired:
            return False, "Java compilation timed out."

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return False, f"Compilation failed:\n{error[:2000]}"

        return True, None

    @staticmethod
    def _quote(value: str) -> str:
        """Quote a value for a javac @argfile."""
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _project_sources(
        self,
        root: Path,
        changed_relative: str,
    ) -> Optional[list[Path]]:
        """
        All .java files of the project except the file being replaced.
        Returns None if the file is not inside the project.
        """

        changed = (root / changed_relative).resolve()
        files: list[Path] = []

        for path in root.rglob("*.java"):
            relative_parts = path.relative_to(root).parts
            if any(part in self._SKIP_DIRS for part in relative_parts):
                continue
            if path.resolve() == changed:
                continue
            files.append(path)

        return files

    # ------------------------------------------------------------------
    # Finding the class to run
    # ------------------------------------------------------------------

    def _find_entry_class(
        self,
        classes_dir: Path,
        java_filename: str,
        package: str,
    ) -> Optional[str]:
        """
        Ask the COMPILED classes which one (compiled from this file)
        has public static void main(String[]).
        """

        package_dir = classes_dir.joinpath(*package.split(".")) if package else classes_dir

        if not package_dir.is_dir():
            return None

        names = sorted(
            (f"{package}." if package else "") + p.stem
            for p in package_dir.glob("*.class")
        )

        found: list[str] = []

        for start in range(0, len(names), 40):
            chunk = names[start:start + 40]

            try:
                result = subprocess.run(
                    [self.javap_command, "-cp", str(classes_dir), *chunk],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return None

            blocks = re.split(r'(?m)^(?=Compiled from ")', result.stdout)

            for block in blocks:
                if not block.startswith("Compiled from "):
                    continue

                source_name = re.match(r'Compiled from "([^"]+)"', block)
                if not source_name or source_name.group(1) != java_filename:
                    continue

                declaration = re.search(
                    r"\b(?:class|interface|enum|record)\s+([\w.$]+)",
                    block,
                )
                if not declaration:
                    continue

                if re.search(
                    r"public\s+static\s+void\s+main\("
                    r"java\.lang\.String(?:\[\]|\.\.\.)\)",
                    block,
                ):
                    found.append(declaration.group(1))

        if not found:
            return None

        top_level = [name for name in found if "$" not in name]
        return (top_level or found)[0]

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def _run_benchmark(
        self,
        harness_dir: Path,
        classes_dir: Path,
        entry_class: str,
    ) -> BenchmarkResult:
        """Launch a few JVMs; each one calls main() many times."""

        runtimes: list[float] = []
        allocations: list[float] = []
        hashes: set[str] = set()
        measured_total = 0

        working_dir = self.project_root or classes_dir
        budget_ms = int(self.timeout_seconds * 1000 * 0.6)

        for _ in range(self.jvm_launches):
            command = [
                self.java_command,
                "-XX:+UseSerialGC",
                "-cp",
                os.pathsep.join([str(harness_dir), str(classes_dir)]),
                "BenchHarness",
                entry_class,
                str(self.warmup_runs),
                str(self.measured_runs),
                str(budget_ms),
            ]

            try:
                result = subprocess.run(
                    command,
                    cwd=working_dir,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except FileNotFoundError:
                return BenchmarkResult(
                    success=False,
                    error=(
                        f"'{self.java_command}' was not found. "
                        "Make sure JDK 21 is installed and java is in PATH."
                    ),
                )
            except subprocess.TimeoutExpired:
                return BenchmarkResult(
                    success=False,
                    error="Java execution timed out.",
                )

            line = None
            for candidate in result.stdout.splitlines():
                if candidate.startswith(("BENCH ", "ERR ")):
                    line = candidate

            if line is None:
                detail = result.stderr.strip()[:500]
                return BenchmarkResult(
                    success=False,
                    error=(
                        "The program produced no result. It may have "
                        "called System.exit() or crashed."
                        + (f"\n{detail}" if detail else "")
                    ),
                )

            if line.startswith("ERR "):
                return BenchmarkResult(success=False, error=line[4:])

            _, time_ns, alloc_bytes, digest, measured = line.split()

            runtimes.append(int(time_ns) / 1_000_000.0)
            allocations.append(int(alloc_bytes) / (1024 * 1024))
            hashes.add(digest)
            measured_total += int(measured)

        if len(hashes) != 1:
            return BenchmarkResult(
                success=False,
                error=(
                    "The program prints different output on each launch "
                    "(time, random numbers, ...), so a change cannot be "
                    "checked for correctness."
                ),
            )

        return BenchmarkResult(
            success=True,
            runtime_ms=statistics.median(runtimes),
            memory_mb=statistics.median(allocations),
            runs=measured_total,
            warmup_runs=self.warmup_runs,
            output_hash=hashes.pop(),
        )

    # ------------------------------------------------------------------
    # Java source inspection
    # ------------------------------------------------------------------

    @staticmethod
    def _package_of(source_code: str) -> str:
        match = re.search(
            r"(?m)^\s*package\s+([\w.]+)\s*;",
            source_code,
        )
        return match.group(1) if match else ""

    @staticmethod
    def _java_filename(source_code: str, filename: str) -> str:
        """
        Public classes must live in a file with the same name.
        Otherwise use the real file name, or guess from the first class.
        """

        public_type = re.search(
            r"\bpublic\s+(?:final\s+|abstract\s+)*"
            r"(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)",
            source_code,
        )
        if public_type:
            return f"{public_type.group(1)}.java"

        if filename:
            candidate = Path(filename).name
            if candidate.endswith(".java"):
                return candidate

        first_type = re.search(
            r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)",
            source_code,
        )
        if first_type:
            return f"{first_type.group(1)}.java"

        return "Candidate.java"