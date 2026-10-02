import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INDEX_DIR = BASE_DIR / ".rag_index"
DEFAULT_CORPORA = [
    BASE_DIR / "patents_corpus/patent_chunks.jsonl",
    BASE_DIR / "repo_corpus/repo_chunks.jsonl",
]


@dataclass
class ChunkRecord:
    chunk_id: str
    source_type: str
    source_url: str
    title: str
    text: str


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _dedupe_signature(source_type: str, source_url: str, title: str, text: str) -> str:
    normalized_text = " ".join(text.split()).lower()
    return f"{source_type}|{source_url}|{title}|{normalized_text}"


def load_corpora(paths: list[Path]) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    seen_signatures: set[str] = set()
    for p in paths:
        if not p.exists():
            continue
        rows = read_jsonl(p)
        corpus_key = p.as_posix().lower()
        if "patent" in corpus_key:
            for r in rows:
                source_type = "patent"
                source_url = str(r.get("url", ""))
                title = str(r.get("title", ""))
                text = str(r.get("text", ""))
                signature = _dedupe_signature(source_type, source_url, title, text)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                records.append(
                    ChunkRecord(
                        chunk_id=str(r.get("id", "")),
                        source_type=source_type,
                        source_url=source_url,
                        title=title,
                        text=text,
                    )
                )
        elif "repo" in corpus_key:
            for r in rows:
                source_type = "repo"
                source_url = str(r.get("url", ""))
                title = str(r.get("title", ""))
                text = str(r.get("text", ""))
                signature = _dedupe_signature(source_type, source_url, title, text)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                records.append(
                    ChunkRecord(
                        chunk_id=str(r.get("id", "")),
                        source_type=source_type,
                        source_url=source_url,
                        title=title,
                        text=text,
                    )
                )
        else:
            for r in rows:
                source_type = "external"
                source_url = str(r.get("url", ""))
                title = str(r.get("title", ""))
                text = str(r.get("text", ""))
                signature = _dedupe_signature(source_type, source_url, title, text)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                records.append(
                    ChunkRecord(
                        chunk_id=str(r.get("id", "")),
                        source_type=source_type,
                        source_url=source_url,
                        title=title,
                        text=text,
                    )
                )
    return records


def build_index(records: list[ChunkRecord], index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    docs = [f"{r.title}\n{r.text}" for r in records]

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(docs)

    joblib.dump(vectorizer, index_dir / "vectorizer.joblib")
    joblib.dump(matrix, index_dir / "matrix.joblib")

    serializable = [r.__dict__ for r in records]
    (index_dir / "records.json").write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")


def load_index(index_dir: Path) -> tuple[TfidfVectorizer, Any, list[ChunkRecord]]:
    vectorizer = joblib.load(index_dir / "vectorizer.joblib")
    matrix = joblib.load(index_dir / "matrix.joblib")
    rows = json.loads((index_dir / "records.json").read_text(encoding="utf-8"))
    records = [ChunkRecord(**row) for row in rows]
    return vectorizer, matrix, records


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()))


def _keyword_overlap_score(query: str, rec: ChunkRecord) -> float:
    q = _tokenize(query)
    if not q:
        return 0.0
    body = _tokenize(f"{rec.title} {rec.text[:1800]}")
    overlap = len(q & body)
    return overlap / max(1, len(q))


def _rrf(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def _is_ip_query(query: str) -> bool:
    q = query.lower()
    needles = ["ip", "patent", "prior art", "novelty", "claim chart", "diligence"]
    return any(n in q for n in needles)


def _is_repo_query(query: str) -> bool:
    q = query.lower()
    needles = ["repo", "repository", "code", "script", "function", "local_rag", "rebuild index"]
    return any(n in q for n in needles)


def retrieve(
    query: str,
    vectorizer: TfidfVectorizer,
    matrix: Any,
    records: list[ChunkRecord],
    top_k: int,
    external_boost: float,
    dedupe_sources: bool,
    mode: str,
    source_filter: str,
) -> list[tuple[float, ChunkRecord]]:
    qv = vectorizer.transform([query])
    cosine_scores = cosine_similarity(qv, matrix)[0]

    keyword_scores = [0.0] * len(records)
    for i, rec in enumerate(records):
        keyword_scores[i] = _keyword_overlap_score(query, rec)

    cosine_ranked = cosine_scores.argsort()[::-1]
    keyword_ranked = sorted(range(len(records)), key=lambda i: keyword_scores[i], reverse=True)

    cosine_rank_pos = {idx: pos for pos, idx in enumerate(cosine_ranked, start=1)}
    keyword_rank_pos = {idx: pos for pos, idx in enumerate(keyword_ranked, start=1)}

    merged_scores: list[float] = [0.0] * len(records)
    ip_like_query = _is_ip_query(query) or mode == "feasibility"

    repo_like_query = _is_repo_query(query)

    for i, rec in enumerate(records):
        if source_filter != "all" and rec.source_type != source_filter:
            merged_scores[i] = -1.0
            continue
        source_boost = external_boost if rec.source_type == "external" else 0.0
        patent_boost = 0.08 if ip_like_query and rec.source_type == "patent" else 0.0
        repo_boost = 0.10 if repo_like_query and rec.source_type == "repo" else 0.0
        merged_scores[i] = (
            0.65 * float(cosine_scores[i])
            + 0.20 * float(keyword_scores[i])
            + 0.15 * (_rrf(cosine_rank_pos[i]) + _rrf(keyword_rank_pos[i]))
            + source_boost
            + patent_boost
            + repo_boost
        )

    ranked_idx = sorted(range(len(records)), key=lambda i: merged_scores[i], reverse=True)

    selected: list[int] = []
    seen_urls: set[str] = set()
    for idx in ranked_idx:
        rec = records[idx]
        if dedupe_sources and rec.source_url and rec.source_url in seen_urls:
            continue
        selected.append(idx)
        if rec.source_url:
            seen_urls.add(rec.source_url)
        if len(selected) >= top_k:
            break

    if ip_like_query and top_k >= 4:
        current_patent = sum(1 for i in selected if records[i].source_type == "patent")
        min_patent = max(2, top_k // 3)
        if current_patent < min_patent:
            patent_pool = [idx for idx in ranked_idx if records[idx].source_type == "patent" and idx not in selected]
            while patent_pool and current_patent < min_patent and selected:
                replace_at = len(selected) - 1
                while replace_at >= 0 and records[selected[replace_at]].source_type == "patent":
                    replace_at -= 1
                if replace_at < 0:
                    break
                selected[replace_at] = patent_pool.pop(0)
                current_patent += 1

    if len(selected) < top_k:
        for idx in ranked_idx:
            if idx in selected:
                continue
            selected.append(idx)
            if len(selected) >= top_k:
                break

    out: list[tuple[float, ChunkRecord]] = []
    for idx in selected:
        out.append((float(merged_scores[idx]), records[idx]))
    return out


def build_context(hits: list[tuple[float, ChunkRecord]]) -> tuple[str, list[dict[str, str]]]:
    lines = []
    refs = []
    for i, (_, rec) in enumerate(hits, start=1):
        ref = f"S{i}"
        refs.append({"ref": ref, "title": rec.title, "url": rec.source_url, "source_type": rec.source_type})
        snippet = rec.text[:1200].replace("\n", " ").strip()
        lines.append(f"[{ref}] {rec.title}\nURL: {rec.source_url}\nExcerpt: {snippet}")
    return "\n\n".join(lines), refs


def call_ollama(prompt: str, model: str, timeout_sec: int = 120) -> str | None:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout_sec)
        if resp.status_code != 200:
            return None
        body = resp.json()
        return body.get("response", "").strip()
    except requests.RequestException:
        return None


def fallback_answer(question: str, refs: list[dict[str, str]], hits: list[tuple[float, ChunkRecord]]) -> str:
    lines = [
        "No local LLM response was available, so this is an extractive answer from retrieved sources.",
        "",
        f"Question: {question}",
        "",
        "Most relevant evidence:",
    ]
    for i, (_, rec) in enumerate(hits, start=1):
        text = rec.text[:300].replace("\n", " ").strip()
        lines.append(f"- [S{i}] {text}")
    lines.append("")
    lines.append("Citations:")
    for r in refs:
        lines.append(f"- [{r['ref']}] {r['title']} ({r['url']})")
    return "\n".join(lines)


def answer_mode(
    question: str,
    context: str,
    refs: list[dict[str, str]],
    model: str,
    use_llm: bool,
    hits: list[tuple[float, ChunkRecord]],
) -> str:
    prompt = (
        "You are a pyrolysis and lignocellulosic domain assistant. "
        "Answer only from the provided sources. If uncertain, say so clearly. "
        "Always cite evidence using source tags like [S1], [S2].\n\n"
        f"Question:\n{question}\n\n"
        f"Sources:\n{context}\n\n"
        "Output format:\n"
        "1) Direct answer\n2) Key evidence bullets with [S#]\n3) Gaps/uncertainties\n"
    )

    if use_llm:
        llm_text = call_ollama(prompt, model=model)
        if llm_text:
            cite_block = "\n\nSource map:\n" + "\n".join([f"- [{r['ref']}] {r['title']} ({r['url']})" for r in refs])
            return llm_text + cite_block

    return fallback_answer(question, refs, hits)


def feasibility_mode(
    question: str,
    context: str,
    refs: list[dict[str, str]],
    model: str,
    use_llm: bool,
    hits: list[tuple[float, ChunkRecord]],
) -> str:
    prompt = (
        "You are performing a feasibility pre-review for pyrolysis and lignocellulosic IP evaluation. "
        "Use only the source excerpts. Do not invent data. Cite [S#] for each factual claim.\n\n"
        f"Evaluation target:\n{question}\n\n"
        f"Sources:\n{context}\n\n"
        "Return markdown with these sections exactly:\n"
        "## Facts\n"
        "## Assumptions\n"
        "## Unknowns\n"
        "## Feasibility Signals\n"
        "## Recommended Next Validation Steps\n"
    )

    if use_llm:
        llm_text = call_ollama(prompt, model=model)
        if llm_text:
            cite_block = "\n\nSource map:\n" + "\n".join([f"- [{r['ref']}] {r['title']} ({r['url']})" for r in refs])
            return llm_text + cite_block

    facts = []
    for i, (_, rec) in enumerate(hits, start=1):
        text = rec.text[:240].replace("\n", " ").strip()
        facts.append(f"- {text} [S{i}]")

    assumptions = [
        "- Feedstock properties and moisture range for your process are not fully specified.",
        "- Target throughput and operating temperature window are assumed from prior art patterns.",
        "- Regulatory and emissions compliance targets are assumed to require documented gas handling.",
    ]

    unknowns = [
        "- Experimental yield and product-quality data for your exact feedstock/process configuration.",
        "- Comparative novelty boundaries against nearest claim language in cited prior art.",
        "- Scale-up constraints, energy balance, and capex/opex at intended deployment scale.",
    ]

    steps = [
        "- Build a claim chart against top-10 nearest patents in the retrieved set.",
        "- Run controlled pilot tests to measure yield, Cfix, emissions, and energy reuse.",
        "- Generate a traceable technical dossier separating measured values from assumptions.",
    ]

    out = [
        "## Facts",
        *facts,
        "",
        "## Assumptions",
        *assumptions,
        "",
        "## Unknowns",
        *unknowns,
        "",
        "## Feasibility Signals",
        "- Positive: corpus shows recurring support for controlled pyrolysis gas "
        "handling and continuous-operation designs.",
        "- Positive: multiple references discuss lignocellulosic conversion pathways "
        "and process temperature control.",
        "- Caution: no direct evidence yet of your proprietary performance deltas " "without your measured data.",
        "",
        "## Recommended Next Validation Steps",
        *steps,
        "",
        "Source map:",
    ]
    out.extend([f"- [{r['ref']}] {r['title']} ({r['url']})" for r in refs])
    return "\n".join(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local RAG for pyrolysis and lignocellulosic expert review.")
    parser.add_argument("--build-index", action="store_true", help="Build or rebuild the local vector index")
    parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR), help="Index directory")
    parser.add_argument("--question", help="Question for answer or feasibility mode")
    parser.add_argument("--mode", choices=["answer", "feasibility"], default="answer")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model name")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM generation and use extractive fallback")
    parser.add_argument(
        "--external-boost",
        type=float,
        default=0.0,
        help="Extra score added to external corpus chunks during reranking",
    )
    parser.add_argument(
        "--allow-duplicate-sources",
        action="store_true",
        help="Allow multiple chunks from the same source URL in top-k",
    )
    parser.add_argument(
        "--source-filter",
        choices=["all", "external", "patent", "repo"],
        default="all",
        help="Restrict retrieval to a specific source type",
    )
    parser.add_argument(
        "--corpus",
        action="append",
        help="Additional corpus JSONL path. Can be used multiple times.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    index_dir = Path(args.index_dir)

    corpus_paths = DEFAULT_CORPORA.copy()
    if args.corpus:
        corpus_paths.extend([Path(c) for c in args.corpus])

    if args.build_index:
        records = load_corpora(corpus_paths)
        if not records:
            raise SystemExit("No corpus records found. Check corpus file paths.")
        build_index(records, index_dir)
        print(f"Index built with {len(records)} chunks at {index_dir.resolve()}")

    if args.question:
        if not (index_dir / "vectorizer.joblib").exists():
            records = load_corpora(corpus_paths)
            if not records:
                raise SystemExit("No corpus records found. Cannot build index.")
            build_index(records, index_dir)

        vectorizer, matrix, records = load_index(index_dir)
        hits = retrieve(
            args.question,
            vectorizer,
            matrix,
            records,
            top_k=args.top_k,
            external_boost=args.external_boost,
            dedupe_sources=not args.allow_duplicate_sources,
            mode=args.mode,
            source_filter=args.source_filter,
        )
        context, refs = build_context(hits)

        use_llm = not args.no_llm
        if args.mode == "answer":
            output = answer_mode(args.question, context, refs, model=args.model, use_llm=use_llm, hits=hits)
        else:
            output = feasibility_mode(args.question, context, refs, model=args.model, use_llm=use_llm, hits=hits)

        print(output)


if __name__ == "__main__":
    main()
