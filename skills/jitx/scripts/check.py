#!/usr/bin/env python3
"""Run the required JITX project checks with compact, cross-platform output."""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    label: str
    status: str
    output: str = ""
    detail: str = ""
    returncode: int | None = None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run JITX lint, type, grep-gate, and optional build checks."
    )
    parser.add_argument("src_dir", help="project Python source directory")
    parser.add_argument(
        "--build",
        metavar="DESIGN",
        help="also run: jitx build <module.path.DesignClass>",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print full output for passing checks as well as failures",
    )
    args = parser.parse_args()
    if not os.path.isdir(args.src_dir):
        parser.error(f"source directory does not exist: {args.src_dir}")
    return args


def run_command(label, command, failure_codes=(1,)):
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return Result(label, "ERROR", detail=f"command not found: {command[0]}")
    except OSError as exc:
        return Result(label, "ERROR", detail=f"could not start {command[0]}: {exc}")

    output = completed.stdout or ""
    if completed.returncode == 0:
        return Result(label, "PASS", output=output, returncode=completed.returncode)

    if is_import_error(output):
        return Result(
            label,
            "ERROR",
            output=output,
            detail="import error",
            returncode=completed.returncode,
        )

    if completed.returncode in failure_codes:
        return Result(label, "FAIL", output=output, returncode=completed.returncode)

    return Result(
        label,
        "ERROR",
        output=output,
        detail=f"unexpected exit code {completed.returncode}",
        returncode=completed.returncode,
    )


def is_import_error(output):
    traceback_import = "Traceback (most recent call last):" in output and re.search(
        r"(?m)^(ImportError|ModuleNotFoundError):", output
    )
    missing_module = re.search(r"(?m)^.*python.*: No module named ", output)
    return bool(traceback_import or missing_module)


def run_grep_gates(src_dir):
    helper = Path(__file__).resolve().with_name("grep_gates.py")
    if not helper.is_file():
        return Result("grep gates", "ERROR", detail=f"missing helper: {helper}")

    result = run_command(
        "grep gates",
        [sys.executable, str(helper), src_dir, "--quiet"],
    )
    if result.status == "ERROR":
        return result

    hard_match = re.search(r"(?m)^hard-fail hits: (\d+)$", result.output)
    review_match = re.search(r"(?m)^review-required hits: (\d+)\b", result.output)
    if not hard_match or not review_match:
        return Result(
            "grep gates",
            "ERROR",
            output=result.output,
            detail="grep_gates.py did not report hit counts",
        )

    hard_fail = int(hard_match.group(1))
    review_required = int(review_match.group(1))
    expected_status = "FAIL" if hard_fail else "PASS"
    if result.status != expected_status:
        return Result(
            "grep gates",
            "ERROR",
            output=result.output,
            detail=(f"grep_gates.py exit disagrees with hard-fail count ({hard_fail})"),
        )

    result.detail = f"{hard_fail} hard-fail, {review_required} review-required"
    return result


def confirm_build_witness(result):
    """Require the printed `status:` line, not just a zero exit.

    A jitx command has been observed exiting 0 while printing a failure
    ("`jitx runtime status` exits 0 and prints Runtime: not running"), so an exit
    code alone is not evidence that this build succeeded. A PASS therefore has to
    carry `status: ok` in the output. An exit 0 with `status: error`, or with no
    status line at all, is ERROR: the check could not establish what happened,
    which is not the same as the build being fine.
    """
    if result.status == "ERROR":
        return result
    text = result.output or ""
    if "status: error" in text:
        return Result(
            "build",
            "FAIL",
            output=text,
            detail="status: error",
            returncode=result.returncode,
        )
    if result.returncode != 0:
        # A nonzero exit is already sufficient evidence of failure. A real failed
        # build prints `errors:` and a traceback rather than a `status:` line, so
        # demanding one here would turn a definite failure into "could not tell".
        return result
    if "status: ok" not in text:
        return Result(
            "build",
            "ERROR",
            output=text,
            detail="exit 0 but no `status:` line to confirm it",
            returncode=result.returncode,
        )
    return result


def print_result(result, verbose):
    detail = f"   {result.detail}" if result.detail else ""
    print(f"{result.label:<15}{result.status}{detail}")
    # The build always prints. Later gate rows ask for build warnings (for example
    # "Reference to structural object ... lost during instantiation"), which a
    # passing build emits and a suppressed PASS would hide.
    always = result.label == "build"
    if result.output and (verbose or always or result.status != "PASS"):
        sys.stdout.write(result.output)
        if not result.output.endswith(("\n", "\r")):
            sys.stdout.write(os.linesep)


def main():
    args = parse_args()
    checks = [
        ("ruff check", ["ruff", "check", args.src_dir], (1,)),
        ("ruff format", ["ruff", "format", "--check", args.src_dir], (1,)),
        ("pyright", ["pyright", args.src_dir], (1,)),
    ]

    results = []
    for label, command, failure_codes in checks:
        result = run_command(label, command, failure_codes)
        results.append(result)
        print_result(result, args.verbose)

    grep_result = run_grep_gates(args.src_dir)
    results.append(grep_result)
    print_result(grep_result, args.verbose)

    if args.build:
        build_result = run_command(
            "build", ["jitx", "build", args.build], failure_codes=(1,)
        )
        build_result = confirm_build_witness(build_result)
        build_result.detail = (
            f"{build_result.detail}; {args.build}"
            if build_result.detail
            else args.build
        )
        results.append(build_result)
        print_result(build_result, args.verbose)

    return 0 if all(result.status == "PASS" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
