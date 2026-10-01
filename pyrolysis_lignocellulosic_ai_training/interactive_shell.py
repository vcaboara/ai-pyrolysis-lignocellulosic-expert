import argparse
from dataclasses import dataclass
from pathlib import Path

from local_rag import (
    DEFAULT_CORPORA,
    DEFAULT_INDEX_DIR,
    answer_mode,
    build_context,
    build_index,
    feasibility_mode,
    load_corpora,
    load_index,
    retrieve,
)
from repo_ingest import build_repo_corpus


@dataclass
class SessionConfig:
    mode: str = "answer"
    top_k: int = 8
    model: str = "llama3.1:8b"
    use_llm: bool = True
    source_filter: str = "all"
    external_boost: float = 0.0
    dedupe_sources: bool = True


def ensure_index(index_dir: Path, corpus_paths: list[Path]) -> None:
    if (index_dir / "vectorizer.joblib").exists():
        return
    records = load_corpora(corpus_paths)
    if not records:
        raise SystemExit("No corpus records found. Run repo ingest/corpus builders first.")
    build_index(records, index_dir)


def rebuild_index(index_dir: Path, corpus_paths: list[Path]) -> str:
    records = load_corpora(corpus_paths)
    if not records:
        return "No corpus records found."
    build_index(records, index_dir)
    return f"Index rebuilt with {len(records)} chunks at {index_dir.resolve()}"


def run_query(question: str, cfg: SessionConfig, index_dir: Path) -> str:
    vectorizer, matrix, records = load_index(index_dir)
    hits = retrieve(
        question,
        vectorizer,
        matrix,
        records,
        top_k=cfg.top_k,
        external_boost=cfg.external_boost,
        dedupe_sources=cfg.dedupe_sources,
        mode=cfg.mode,
        source_filter=cfg.source_filter,
    )
    context, refs = build_context(hits)

    if cfg.mode == "answer":
        return answer_mode(
            question,
            context,
            refs,
            model=cfg.model,
            use_llm=cfg.use_llm,
            hits=hits,
        )

    return feasibility_mode(
        question,
        context,
        refs,
        model=cfg.model,
        use_llm=cfg.use_llm,
        hits=hits,
    )


def print_help() -> None:
    print("Commands:")
    print("  /help                         Show this help")
    print("  /show                         Show active session settings")
    print("  /mode answer|feasibility      Set response mode")
    print("  /topk <int>                   Set retrieval depth")
    print("  /model <name>                 Set Ollama model")
    print("  /llm on|off                   Enable/disable model generation")
    print("  /filter all|external|patent|repo    Restrict retrieval source")
    print("  /boost <float>                Set external source score boost")
    print("  /dedupe on|off                Deduplicate source URLs")
    print("  /reindex                      Rebuild index from configured corpora")
    print("  /repo-sync                    Build repo corpus and reindex")
    print("  /quit                         Exit shell")
    print("Any other input is treated as a question.")


def show_config(cfg: SessionConfig, index_dir: Path) -> None:
    print("Session settings:")
    print(f"- mode: {cfg.mode}")
    print(f"- top_k: {cfg.top_k}")
    print(f"- model: {cfg.model}")
    print(f"- llm: {'on' if cfg.use_llm else 'off'}")
    print(f"- source_filter: {cfg.source_filter}")
    print(f"- external_boost: {cfg.external_boost}")
    print(f"- dedupe_sources: {'on' if cfg.dedupe_sources else 'off'}")
    print(f"- index_dir: {index_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive shell for local RAG + Ollama")
    parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR), help="Index directory")
    parser.add_argument("--repo-root", default="..", help="Repository root for /repo-sync")
    parser.add_argument(
        "--repo-output",
        default="repo_corpus/repo_chunks.jsonl",
        help="Repo corpus output path relative to this script directory",
    )
    parser.add_argument("--mode", choices=["answer", "feasibility"], default="answer")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--source-filter", choices=["all", "external", "patent", "repo"], default="all")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    index_dir = Path(args.index_dir)
    repo_root = (script_dir / args.repo_root).resolve()
    repo_output = (script_dir / args.repo_output).resolve()

    cfg = SessionConfig(
        mode=args.mode,
        top_k=max(1, args.top_k),
        model=args.model,
        use_llm=not args.no_llm,
        source_filter=args.source_filter,
    )

    corpus_paths = DEFAULT_CORPORA.copy()

    ensure_index(index_dir, corpus_paths)

    print("Local RAG interactive shell")
    print("Type /help for commands.")

    while True:
        try:
            line = input("rag> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not line:
            continue

        if line.startswith("/"):
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd == "/help":
                print_help()
            elif cmd == "/show":
                show_config(cfg, index_dir)
            elif cmd == "/mode":
                if arg in {"answer", "feasibility"}:
                    cfg.mode = arg
                    print(f"mode set to {cfg.mode}")
                else:
                    print("usage: /mode answer|feasibility")
            elif cmd == "/topk":
                try:
                    cfg.top_k = max(1, int(arg))
                    print(f"top_k set to {cfg.top_k}")
                except ValueError:
                    print("usage: /topk <int>")
            elif cmd == "/model":
                if arg:
                    cfg.model = arg
                    print(f"model set to {cfg.model}")
                else:
                    print("usage: /model <name>")
            elif cmd == "/llm":
                if arg.lower() == "on":
                    cfg.use_llm = True
                    print("llm enabled")
                elif arg.lower() == "off":
                    cfg.use_llm = False
                    print("llm disabled")
                else:
                    print("usage: /llm on|off")
            elif cmd == "/filter":
                if arg in {"all", "external", "patent", "repo"}:
                    cfg.source_filter = arg
                    print(f"source_filter set to {cfg.source_filter}")
                else:
                    print("usage: /filter all|external|patent|repo")
            elif cmd == "/boost":
                try:
                    cfg.external_boost = float(arg)
                    print(f"external_boost set to {cfg.external_boost}")
                except ValueError:
                    print("usage: /boost <float>")
            elif cmd == "/dedupe":
                if arg.lower() == "on":
                    cfg.dedupe_sources = True
                    print("dedupe enabled")
                elif arg.lower() == "off":
                    cfg.dedupe_sources = False
                    print("dedupe disabled")
                else:
                    print("usage: /dedupe on|off")
            elif cmd == "/reindex":
                print(rebuild_index(index_dir, corpus_paths))
            elif cmd == "/repo-sync":
                files, chunks = build_repo_corpus(
                    repo_root=repo_root,
                    output_jsonl=repo_output,
                    chunk_chars=1600,
                    overlap_chars=250,
                    max_file_kb=256,
                    include_hidden=False,
                )
                print(f"repo corpus updated: {repo_output} ({files} files, {chunks} chunks)")
                print(rebuild_index(index_dir, corpus_paths))
            elif cmd == "/quit":
                print("Exiting.")
                break
            else:
                print("Unknown command. Type /help for options.")
            continue

        try:
            print(run_query(line, cfg, index_dir))
        except Exception as exc:
            print(f"query failed: {exc}")


if __name__ == "__main__":
    main()
