#!/usr/bin/env python3
"""
Java 8→21 Transformer — Entry Point
=====================================

Usage:
  python main.py <source_dir> <destination_dir>
  python main.py <source_dir> <destination_dir> --dry-run
  python main.py <source_dir> <destination_dir> --verbose
  python main.py <source_dir> <destination_dir> --optimize
  python main.py <source_dir> <destination_dir> --optimize --verbose

Pipeline:
  Phase 1 — Mandatory Java 8→21 transformations
  Phase 2 — Optional performance-aware Java 21 transformations
"""

import argparse
import sys
from pathlib import Path

from file_walker import FileWalker
from java_transformer import JavaTransformer
from reporter import Reporter

from optimizer.optimizer_pipeline import OptionalOptimizationPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform Java source files (8–20) to Java 21.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py ./src ./src_java21
  python main.py ./src ./out --dry-run
  python main.py ./src ./out --verbose
  python main.py ./src ./out --optimize
  python main.py ./src ./out --optimize --verbose
        """,
    )

    parser.add_argument(
        "source",
        help="Source folder containing Java files",
    )

    parser.add_argument(
        "destination",
        help="Destination folder for transformed output",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print every individual transformation",
    )

    parser.add_argument(
        "--optimize",
        action="store_true",
        help=(
            "Enable performance-aware optional Java 21 "
            "transformations"
        ),
    )

    parser.add_argument(
        "--target-java-version",
        type=int,
        choices=range(8, 22),
        default=21,
        help="Target Java version for optional transformations (default: 21)",
    )

    return parser.parse_args()


def main() -> None:

    args = parse_args()

    source = Path(args.source).resolve()
    dest = Path(args.destination).resolve()

    # ---------------------------------------------------------
    # Validate paths
    # ---------------------------------------------------------

    if not source.exists():
        print(
            f"[ERROR] Source directory does not exist: {source}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not source.is_dir():
        print(
            f"[ERROR] Source path is not a directory: {source}",
            file=sys.stderr,
        )
        sys.exit(1)

    if source == dest:
        print(
            "[ERROR] Source and destination must be different "
            "directories.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ---------------------------------------------------------
    # Header
    # ---------------------------------------------------------

    print("=" * 70)
    print("  Java 8→21 Source Transformer")
    print("=" * 70)

    print(f"  Source      : {source}")
    print(f"  Destination : {dest}")
    print(f"  Dry run     : {args.dry_run}")
    print(f"  Verbose     : {args.verbose}")
    print(f"  Optimizer   : {args.optimize}")
    print(f"  Target Java : {args.target_java_version}")
    print()

    # ---------------------------------------------------------
    # Initialize components
    # ---------------------------------------------------------

    walker = FileWalker(source, dest)

    # Existing mandatory migration pipeline
    transformer = JavaTransformer(
        verbose=args.verbose
    )

    # Existing reporting system
    reporter = Reporter(
        verbose=args.verbose
    )

    # ---------------------------------------------------------
    # Optional performance-aware optimizer
    # ---------------------------------------------------------

    optimizer = None

    if args.optimize:

        optimizer = OptionalOptimizationPipeline(
            min_runtime_improvement_percent=5.0,
            min_memory_improvement_percent=0.0,
            target_java_version=args.target_java_version,
        )

        print("  Performance-aware optimization: ENABLED")
        print("  Minimum runtime improvement    : 5.0%")
        print("  Minimum memory improvement     : 0.0%")
        print()

    # ---------------------------------------------------------
    # Find Java files
    # ---------------------------------------------------------

    java_files = walker.find_java_files()

    if not java_files:
        print("No .java files found in source directory.")
        sys.exit(0)

    print(
        f"Found {len(java_files)} Java file(s). Processing...\n"
    )
        # ---------------------------------------------------------
    # Pre-pass (only with --optimize): write the fully migrated
    # project to the destination first, so the benchmarker can
    # compile the WHOLE project instead of one lonely file.
    # ---------------------------------------------------------

    if optimizer is not None and not args.dry_run:

        silent_transformer = JavaTransformer(verbose=False)

        for java_file in java_files:

            rel_path = java_file.relative_to(source)

            try:
                text = java_file.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            migrated, _ = silent_transformer.transform(
                text,
                str(rel_path),
            )

            target = dest / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(migrated, encoding="utf-8")

        optimizer.optimizer.analyzer.set_project(dest)
    # ---------------------------------------------------------
    # Process each Java file
    # ---------------------------------------------------------

    for java_file in java_files:

        rel_path = java_file.relative_to(source)
        dest_file = dest / rel_path

        print(f"[FILE] {rel_path}")

        # -----------------------------------------------------
        # Read source
        # -----------------------------------------------------

        try:
            original = java_file.read_text(
                encoding="utf-8",
                errors="replace",
            )

        except OSError as e:

            print(
                f"  [WARN] Could not read {rel_path}: {e}",
                file=sys.stderr,
            )

            continue

        # =====================================================
        # PHASE 1
        # Mandatory Java 8 → Java 21 migration
        # =====================================================

        transformed, changes = transformer.transform(
            original,
            str(rel_path),
        )

        reporter.record(
            str(rel_path),
            changes,
        )

        print(
            f"  Mandatory transformations: {len(changes)}"
        )

        # =====================================================
        # PHASE 2
        # Optional performance-aware Java 21 modernization
        # =====================================================

        if optimizer is not None:

            print(
                "  Running performance-aware optimization..."
            )

            try:

                optimization_result = optimizer.transform(
                    transformed,
                    str(rel_path),
                )

                # Use optimized source only when the optimizer
                # actually accepted a candidate.
                transformed = optimization_result.source

                # Make accepted optimizer rewrites show up in the summary
                applied_notes = [
                    f"Optimizer applied: {r.candidate_name}"
                    for r in (optimization_result.results or [])
                    if r.applied
                ]
                if applied_notes:
                    reporter.add_changes(str(rel_path), applied_notes)

                # -------------------------------------------------
                # Display optimization results
                # -------------------------------------------------

                if optimization_result.results:

                    for result in optimization_result.results:

                        print()
                        print("  " + "=" * 60)
                        print(
                            f"  Candidate : {result.candidate_name}"
                        )
                        print("  " + "=" * 60)

                        # -----------------------------------------
                        # Original benchmark
                        # -----------------------------------------

                        if result.original_benchmark is not None:

                            benchmark = (
                                result.original_benchmark
                            )

                            if benchmark.success:

                                if benchmark.runtime_ms is not None:
                                    print(
                                        f"  Before Runtime : "
                                        f"{benchmark.runtime_ms:.3f} ms"
                                    )

                                if benchmark.memory_mb is not None:
                                    print(
                                        f"  Before Memory  : "
                                        f"{benchmark.memory_mb:.3f} MB"
                                    )

                            else:

                                print(
                                    "  Before Benchmark: "
                                    f"FAILED - {benchmark.error}"
                                )

                        # -----------------------------------------
                        # Candidate benchmark
                        # -----------------------------------------

                        if result.candidate_benchmark is not None:

                            benchmark = (
                                result.candidate_benchmark
                            )

                            if benchmark.success:

                                if benchmark.runtime_ms is not None:
                                    print(
                                        f"  After Runtime  : "
                                        f"{benchmark.runtime_ms:.3f} ms"
                                    )

                                if benchmark.memory_mb is not None:
                                    print(
                                        f"  After Memory   : "
                                        f"{benchmark.memory_mb:.3f} MB"
                                    )

                            else:

                                print(
                                    "  After Benchmark : "
                                    f"FAILED - {benchmark.error}"
                                )

                        # -----------------------------------------
                        # Improvement
                        # -----------------------------------------

                        if (
                            result.runtime_improvement_percent
                            is not None
                        ):

                            print(
                                f"  Runtime Change : "
                                f"{result.runtime_improvement_percent:.2f}%"
                            )

                        if (
                            result.memory_improvement_percent
                            is not None
                        ):

                            print(
                                f"  Memory Change  : "
                                f"{result.memory_improvement_percent:.2f}%"
                            )

                        # -----------------------------------------
                        # Decision
                        # -----------------------------------------

                        if result.applied:
                            decision = "APPLIED"
                        else:
                            decision = "NOT APPLIED"

                        print(
                            f"  Decision       : {decision}"
                        )

                        print(
                            f"  Reason         : {result.reason}"
                        )

                        print("  " + "=" * 60)

                else:

                    print(
                        "  Optional transformations: 0"
                    )

            except Exception as e:

                # The optimizer is optional.
                # If it fails, preserve the mandatory
                # Java 21 transformation.

                print(
                    f"  [WARN] Optional optimizer failed: {e}",
                    file=sys.stderr,
                )

                print(
                    "  Continuing with mandatory "
                    "Java 21 transformation."
                )

        # =====================================================
        # Write transformed source
        # =====================================================

        if not args.dry_run:

            try:

                dest_file.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                dest_file.write_text(
                    transformed,
                    encoding="utf-8",
                )

            except OSError as e:

                print(
                    f"  [WARN] Could not write {rel_path}: {e}",
                    file=sys.stderr,
                )

                continue

        print()

    # ---------------------------------------------------------
    # Copy non-Java files
    # ---------------------------------------------------------

    if not args.dry_run:

        walker.copy_non_java_files()

        walker.patch_config_files(
            verbose=args.verbose
        )

    # ---------------------------------------------------------
    # Final report
    # ---------------------------------------------------------

    reporter.print_summary(
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
