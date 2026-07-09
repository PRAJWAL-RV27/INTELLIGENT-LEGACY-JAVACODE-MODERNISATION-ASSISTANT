"""
reporter.py — Collects per-file change records and prints a final summary.
"""
from dataclasses import dataclass, field


@dataclass
class FileReport:
    path: str
    changes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


class Reporter:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose   = verbose
        self._reports: list[FileReport] = []

    # ── Public API ─────────────────────────────────────────────────────────────

    def record(self, path: str, changes: list[str]) -> None:
        """Store the result for one file."""
        self._reports.append(FileReport(path=path, changes=list(changes)))

    def print_summary(self, dry_run: bool = False) -> None:
        total     = len(self._reports)
        changed   = [r for r in self._reports if r.changed]
        unchanged = [r for r in self._reports if not r.changed]

        print("\n" + "=" * 60)
        print("  TRANSFORMATION SUMMARY")
        print("=" * 60)
        print(f"  Total files processed : {total}")
        print(f"  Files modified        : {len(changed)}")
        print(f"  Files unchanged       : {len(unchanged)}")

        if dry_run:
            print("\n  ⚠  DRY RUN — no files were written to disk.")

        if changed:
            print(f"\n  Modified files:")
            for r in changed:
                print(f"\n    📄  {r.path}")
                for c in r.changes:
                    print(f"          • {c}")

        if unchanged and self.verbose:
            print(f"\n  Unchanged files:")
            for r in unchanged:
                print(f"    ✅  {r.path}")

        print("=" * 60)

    def get_summary_text(self, dry_run: bool = False) -> str:
        """Return the summary as a string."""
        total     = len(self._reports)
        changed   = [r for r in self._reports if r.changed]
        unchanged = [r for r in self._reports if not r.changed]

        lines = []
        lines.append("=" * 60)
        lines.append("  TRANSFORMATION SUMMARY")
        lines.append("=" * 60)
        lines.append(f"  Total files processed : {total}")
        lines.append(f"  Files modified        : {len(changed)}")
        lines.append(f"  Files unchanged       : {len(unchanged)}")

        if dry_run:
            lines.append("\n  ⚠  DRY RUN — no files were written to disk.")

        if changed:
            lines.append(f"\n  Modified files:")
            for r in changed:
                lines.append(f"\n    📄  {r.path}")
                for c in r.changes:
                    lines.append(f"          • {c}")

        if unchanged and self.verbose:
            lines.append(f"\n  Unchanged files:")
            for r in unchanged:
                lines.append(f"    ✅  {r.path}")

        lines.append("=" * 60)
        return "\n".join(lines)
