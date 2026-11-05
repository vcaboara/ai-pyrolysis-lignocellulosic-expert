# The repo hook setup uses a fixed git command with static metadata arguments only.
import subprocess  # nosec B404
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    hook_path = ".githooks"
    # Git is invoked with a fixed executable and static repo metadata args only.
    result = subprocess.run(["git", "config", "core.hooksPath", hook_path], cwd=str(ROOT))  # nosec B603 B607
    if result.returncode != 0:
        return result.returncode
    print(f"Configured git hooks path: {hook_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
