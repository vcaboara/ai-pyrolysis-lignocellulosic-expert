import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def ensure_compose_file() -> Path:
    root = Path(__file__).resolve().parent.parent
    compose = root / "docker-compose.yml"
    if not compose.exists():
        raise FileNotFoundError(f"Missing docker-compose.yml at {compose}")
    return compose


def cmd_compose(args: list[str]) -> int:
    compose = ensure_compose_file()
    base = ["docker", "compose", "-f", str(compose)]
    result = run(base + args, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def cmd_ollama(args: list[str]) -> int:
    # uses the running compose service if available
    result = run(
        ["docker", "compose", "-f", str(ensure_compose_file()), "exec", "ollama", "ollama", *args], check=False
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def ensure_container_running() -> None:
    status = run(["docker", "ps", "--filter", "name=ollama", "--format", "{{.Names}}"], check=False)
    if status.returncode != 0:
        raise RuntimeError("Docker is unavailable or not running.")
    if not status.stdout.strip():
        raise RuntimeError("Ollama container is not running. Start it with: docker compose up -d ollama")


def action_up(args: list[str]) -> int:
    return cmd_compose(["up", "-d", *args])


def action_down(args: list[str]) -> int:
    return cmd_compose(["down", *args])


def action_logs(args: list[str]) -> int:
    return cmd_compose(["logs", *args])


def action_pull(args: list[str]) -> int:
    ensure_container_running()
    return cmd_ollama(["pull", *args])


def action_list(args: list[str]) -> int:
    ensure_container_running()
    return cmd_ollama(["list"])


def action_ps(args: list[str]) -> int:
    return run(["docker", "ps", *args], check=False).returncode


def action_status(args: list[str]) -> int:
    # print compose status and installed models
    compose = ensure_compose_file()
    print("Compose status:")
    status = run(["docker", "compose", "-f", str(compose), "ps"], check=False)
    if status.stdout:
        print(status.stdout, end="")
    if status.stderr:
        print(status.stderr, end="", file=sys.stderr)
    print("\nInstalled models:")
    try:
        ensure_container_running()
        return cmd_ollama(["list"])
    except RuntimeError as exc:
        print(str(exc))
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Small helper for Docker + Ollama workflows",
        epilog=(
            "Examples:\n"
            "  py .\\utils\\docker_ollama.py up\n"
            "  py .\\utils\\docker_ollama.py pull llama3.1:8b\n"
            "  py .\\utils\\docker_ollama.py status\n"
            "  py .\\utils\\docker_ollama.py -h"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("up", help="Start services").add_argument("services", nargs="*")
    subparsers.add_parser("down", help="Stop services").add_argument("services", nargs="*")
    subparsers.add_parser("logs", help="View logs").add_argument("services", nargs="*")
    subparsers.add_parser("pull", help="Pull an Ollama model").add_argument("model")
    subparsers.add_parser("list", help="List installed models")
    subparsers.add_parser("ps", help="List docker containers")
    subparsers.add_parser("status", help="Check compose status and model list")
    return parser


def main() -> int:
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    args = parser.parse_args()

    if args.command == "up":
        return action_up(args.services)
    if args.command == "down":
        return action_down(args.services)
    if args.command == "logs":
        return action_logs(args.services)
    if args.command == "pull":
        return action_pull([args.model])
    if args.command == "list":
        return action_list([])
    if args.command == "ps":
        return action_ps([])
    if args.command == "status":
        return action_status([])

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
