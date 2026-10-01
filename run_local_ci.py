import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON_FILES = [
    "run_local_ci.py",
    "utils/docker_ollama.py",
    "tests/test_docker_ollama.py",
    "pyrolysis_lignocellulosic_ai_training/interactive_shell.py",
    "pyrolysis_lignocellulosic_ai_training/repo_ingest.py",
    "pyrolysis_lignocellulosic_ai_training/local_rag.py",
    "pyrolysis_lignocellulosic_ai_training/google_patents_ingest.py",
    "scripts/privacy_guard.py",
]


def run_step(label: str, command: list[str]) -> int:
    print(f"\n=== {label} ===")
    completed = subprocess.run(command, cwd=str(ROOT))
    print(f"Exit code: {completed.returncode}")
    return completed.returncode


def add_common_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", action="store_true", help="Run Black formatting check")
    parser.add_argument("--lint", action="store_true", help="Run Ruff lint checks")
    parser.add_argument("--mypy", action="store_true", help="Run mypy static analysis")
    parser.add_argument("--tests", action="store_true", help="Run unit tests")
    parser.add_argument("--privacy", action="store_true", help="Run privacy content/path scan")
    parser.add_argument("--compose", action="store_true", help="Validate Docker Compose config")
    parser.add_argument("--all", action="store_true", help="Run all quality checks")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local CI for the project quality gates")
    add_common_parser(parser)
    return parser.parse_args()


def run_format() -> int:
    return run_step("Black format check", [sys.executable, "-m", "black", "--check", *PYTHON_FILES])


def run_lint() -> int:
    return run_step("Ruff lint", [sys.executable, "-m", "ruff", "check", *PYTHON_FILES])


def run_mypy() -> int:
    return run_step("Mypy static analysis", [sys.executable, "-m", "mypy", *PYTHON_FILES])


def run_tests() -> int:
    return run_step("Unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])


def run_privacy_scan() -> int:
    return run_step("Privacy scan", [sys.executable, "scripts/privacy_guard.py", "--scan-all"])


def run_compose_check() -> int:
    docker_path = shutil.which("docker")
    if not docker_path:
        print("\nDocker CLI not found; skipping compose validation.")
        return 0
    return run_step("Compose validation", ["docker", "compose", "-f", "docker-compose.yml", "config"])


def main() -> int:
    args = parse_args()
    run_all = args.all or not any([args.format, args.lint, args.mypy, args.tests, args.privacy, args.compose])

    if run_all or args.tests:
        exit_code = run_tests()
        if exit_code != 0:
            return exit_code

    if run_all or args.privacy:
        exit_code = run_privacy_scan()
        if exit_code != 0:
            return exit_code

    if run_all or args.format:
        exit_code = run_format()
        if exit_code != 0:
            return exit_code

    if run_all or args.lint:
        exit_code = run_lint()
        if exit_code != 0:
            return exit_code

    if run_all or args.mypy:
        exit_code = run_mypy()
        if exit_code != 0:
            return exit_code

    if run_all or args.compose:
        exit_code = run_compose_check()
        if exit_code != 0:
            return exit_code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
