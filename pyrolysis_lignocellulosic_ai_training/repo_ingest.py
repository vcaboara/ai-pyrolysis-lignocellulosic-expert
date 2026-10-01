import argparse
import json
from pathlib import Path

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".sh",
    ".ps1",
    ".bat",
    ".sql",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    ".rag_index",
    "repo_corpus",
}


def iter_files(root: Path, include_hidden: bool, max_file_kb: int):
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        parts = set(path.parts)
        if any(d in parts for d in SKIP_DIRS):
            continue

        if not include_hidden and any(part.startswith(".") for part in path.parts if part not in {".", ".."}):
            continue

        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue

        try:
            size_kb = path.stat().st_size / 1024
        except OSError:
            continue

        if size_kb > max_file_kb:
            continue

        yield path


def chunk_text(text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    clean = text.replace("\r\n", "\n")
    chunks: list[str] = []
    start = 0
    step = max(1, chunk_chars - overlap_chars)
    while start < len(clean):
        end = min(len(clean), start + chunk_chars)
        piece = clean[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(clean):
            break
        start += step
    return chunks


def to_record(file_path: Path, rel_path: str, chunk_idx: int, text: str) -> dict:
    return {
        "id": f"repo:{rel_path}:{chunk_idx}",
        "title": f"repo::{rel_path}",
        "url": f"repo://{rel_path}",
        "path": rel_path,
        "text": text,
    }


def build_repo_corpus(
    repo_root: Path,
    output_jsonl: Path,
    chunk_chars: int,
    overlap_chars: int,
    max_file_kb: int,
    include_hidden: bool,
) -> tuple[int, int]:
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    file_count = 0
    chunk_count = 0
    with output_jsonl.open("w", encoding="utf-8") as out:
        for file_path in iter_files(repo_root, include_hidden=include_hidden, max_file_kb=max_file_kb):
            try:
                raw = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            rel_path = file_path.relative_to(repo_root).as_posix()
            file_chunks = chunk_text(raw, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
            if not file_chunks:
                continue

            file_count += 1
            for i, ch in enumerate(file_chunks, start=1):
                rec = to_record(file_path, rel_path, i, ch)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                chunk_count += 1

    return file_count, chunk_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a repository corpus for local RAG retrieval.")
    parser.add_argument("--repo-root", default=".", help="Path to repository root")
    parser.add_argument(
        "--output",
        default="pyrolysis_lignocellulosic_ai_training/repo_corpus/repo_chunks.jsonl",
        help="Output JSONL file",
    )
    parser.add_argument("--chunk-chars", type=int, default=1600, help="Chunk size in characters")
    parser.add_argument("--overlap-chars", type=int, default=250, help="Chunk overlap in characters")
    parser.add_argument("--max-file-kb", type=int, default=256, help="Skip files larger than this size")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden files and directories")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output = Path(args.output).resolve()

    files, chunks = build_repo_corpus(
        repo_root=repo_root,
        output_jsonl=output,
        chunk_chars=args.chunk_chars,
        overlap_chars=args.overlap_chars,
        max_file_kb=args.max_file_kb,
        include_hidden=args.include_hidden,
    )

    print(f"Repo corpus written: {output}")
    print(f"Files indexed: {files}")
    print(f"Chunks written: {chunks}")


if __name__ == "__main__":
    main()
