import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    hook_path = ".githooks"
    result = subprocess.run(["git", "config", "core.hooksPath", hook_path], cwd=str(ROOT))
    if result.returncode != 0:
        return result.returncode
    print(f"Configured git hooks path: {hook_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
