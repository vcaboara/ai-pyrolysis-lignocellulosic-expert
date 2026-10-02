import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL_PRIVATE_DIR = ROOT / ".local_private"

# Generic defaults. Add sensitive terms/domains/paths in local-only denylist files.
DEFAULT_BLOCKED_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
]

DEFAULT_BLOCKED_PATH_PATTERNS = [
    re.compile(r"(^|/)\.local_private(/|$)", re.IGNORECASE),
    re.compile(r"(^|/)private_site_corpus(/|$)", re.IGNORECASE),
    re.compile(r"(^|/)private_site_builder\.py$", re.IGNORECASE),
]


def _load_regex_file(path: Path) -> list[re.Pattern[str]]:
    if not path.exists():
        return []
    patterns: list[re.Pattern[str]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        patterns.append(re.compile(re.escape(item), re.IGNORECASE))
    return patterns


def blocked_patterns() -> list[re.Pattern[str]]:
    terms_file = LOCAL_PRIVATE_DIR / "privacy_terms.txt"
    domains_file = LOCAL_PRIVATE_DIR / "privacy_domains.txt"
    return DEFAULT_BLOCKED_PATTERNS + _load_regex_file(terms_file) + _load_regex_file(domains_file)


def blocked_path_patterns() -> list[re.Pattern[str]]:
    paths_file = LOCAL_PRIVATE_DIR / "privacy_paths.txt"
    return DEFAULT_BLOCKED_PATH_PATTERNS + _load_regex_file(paths_file)


BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".joblib",
    ".pyc",
}


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)


def is_binary_path(path: Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS


def staged_files() -> list[Path]:
    cp = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "failed to read staged files")
    items: list[Path] = []
    for line in cp.stdout.splitlines():
        line = line.strip()
        if line:
            items.append(Path(line))
    return items


def tracked_files() -> list[Path]:
    cp = run_git(["ls-files"])
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "failed to read tracked files")
    return [Path(line.strip()) for line in cp.stdout.splitlines() if line.strip()]


def read_staged_text(path: Path) -> str:
    cp = run_git(["show", f":{path.as_posix()}"])
    if cp.returncode != 0:
        return ""
    return cp.stdout


def read_worktree_text(path: Path) -> str:
    full = ROOT / path
    try:
        return full.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def scan_paths(paths: list[Path]) -> list[str]:
    violations: list[str] = []
    patterns = blocked_path_patterns()
    for path in paths:
        p = path.as_posix()
        for rx in patterns:
            if rx.search(p):
                violations.append(f"blocked path pattern '{rx.pattern}' matched: {p}")
    return violations


def scan_text(path: Path, text: str) -> list[str]:
    violations: list[str] = []
    lowered = text.lower()
    for rx in blocked_patterns():
        if rx.search(lowered):
            violations.append(f"blocked content pattern '{rx.pattern}' matched in: {path.as_posix()}")
    return violations


def scan(files: list[Path], from_staged: bool) -> list[str]:
    violations = scan_paths(files)
    for path in files:
        if is_binary_path(path):
            continue
        text = read_staged_text(path) if from_staged else read_worktree_text(path)
        if not text:
            continue
        violations.extend(scan_text(path, text))
    return violations


def scan_commit_message(msg_file: Path) -> list[str]:
    text = msg_file.read_text(encoding="utf-8", errors="ignore")
    return scan_text(Path("<commit-message>"), text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Privacy guard for blocked terms/paths before commit")
    parser.add_argument("--scan-all", action="store_true", help="Scan all tracked files in the working tree")
    parser.add_argument("--commit-msg-file", help="Commit message file path (for commit-msg hook)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.commit_msg_file:
        violations = scan_commit_message(Path(args.commit_msg_file))
    elif args.scan_all:
        violations = scan(tracked_files(), from_staged=False)
    else:
        violations = scan(staged_files(), from_staged=True)

    if violations:
        print("Privacy guard failed:")
        for item in violations:
            print(f"- {item}")
        print("\nRemove or rename blocked content before committing.")
        return 1

    print("Privacy guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
