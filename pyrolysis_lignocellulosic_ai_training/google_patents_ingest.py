import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

DEFAULT_QUERY_URLS = [
    "https://patents.google.com/?q=(pyrolysis)&oq=pyrolysis",
    "https://patents.google.com/?q=(pyrolysis;+lignocellulosic)&oq=pyrolysis;+lignocellulosic",
]


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def collapse_repeated_token_spans(text: str, min_span_tokens: int = 10, max_span_tokens: int = 60) -> str:
    tokens = text.split()
    if len(tokens) < min_span_tokens * 2:
        return text

    out: list[str] = []
    i = 0
    while i < len(tokens):
        max_window = min(max_span_tokens, (len(tokens) - i) // 2)
        repeated = False
        for window in range(max_window, min_span_tokens - 1, -1):
            left = tokens[i : i + window]
            right = tokens[i + window : i + (window * 2)]
            if left == right:
                out.extend(left)
                i += window * 2
                repeated = True
                break
        if not repeated:
            out.append(tokens[i])
            i += 1

    return " ".join(out)


def dedupe_consecutive_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    cleaned: list[str] = []
    prev_norm = ""
    for part in parts:
        sentence = normalize_whitespace(part)
        if not sentence:
            continue
        norm = sentence.lower()
        if norm == prev_norm:
            continue
        cleaned.append(sentence)
        prev_norm = norm
    return " ".join(cleaned)


def clean_patent_text(text: str) -> str:
    text = normalize_whitespace(text)
    text = collapse_repeated_token_spans(text)
    text = dedupe_consecutive_sentences(text)
    return normalize_whitespace(text)


def chunk_text(text: str, max_chars: int = 2200, overlap: int = 220) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def extract_patent_codes(text: str) -> list[str]:
    # Common granted/published formats like US12570904B2, WO2020123456A1, EP2291488A2
    rx = re.compile(r"\b(?:US|WO|EP|CN|JP|KR|CA|RU|AU)\d{5,12}[A-Z]?\d?\b")
    seen = set()
    out = []
    for m in rx.findall(text):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def query_to_download_url(query_url: str) -> str:
    # Mirrors the Download link seen on Google Patents query pages.
    encoded = quote(query_url.split("?", 1)[1] if "?" in query_url else "", safe="")
    return f"https://patents.google.com/xhr/query?url={encoded}&exp=&download=true"


def fetch_query_page(session: requests.Session, url: str, timeout: int) -> dict:
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "lxml")
    text = normalize_whitespace(soup.get_text(" ", strip=True))

    patent_codes = extract_patent_codes(text)
    # Keep the first N to focus on top-ranked results shown by Google Patents page.
    top_codes = patent_codes[:120]

    download_url = query_to_download_url(url)
    csv_text = ""
    try:
        csv_resp = session.get(download_url, timeout=timeout)
        if csv_resp.status_code == 200 and "text" in csv_resp.headers.get("Content-Type", ""):
            csv_text = csv_resp.text
    except requests.RequestException:
        csv_text = ""

    return {
        "query_url": url,
        "download_url": download_url,
        "top_patent_codes": top_codes,
        "query_text_excerpt": text[:12000],
        "csv_snapshot": csv_text[:200000],
    }


def fetch_patent_detail(session: requests.Session, patent_code: str, timeout: int) -> dict | None:
    detail_url = f"https://patents.google.com/patent/{patent_code}/en"
    try:
        resp = session.get(detail_url, timeout=timeout)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")

        title_tag = soup.find("meta", attrs={"name": "DC.title"})
        title_value = title_tag.get("content") if title_tag else ""
        title = title_value.strip() if isinstance(title_value, str) else ""

        abstract_tag = soup.find("meta", attrs={"name": "DC.description"})
        abstract_value = abstract_tag.get("content") if abstract_tag else ""
        abstract = abstract_value.strip() if isinstance(abstract_value, str) else ""

        claims_nodes = soup.find_all(["claim-text", "div"], attrs={"num": True})
        claims_text = " ".join(node.get_text(" ", strip=True) for node in claims_nodes[:80])

        full_text = clean_patent_text(" ".join([title, abstract, claims_text]))
        if len(full_text) < 200:
            full_text = clean_patent_text(soup.get_text(" ", strip=True))[:50000]

        return {
            "patent_code": patent_code,
            "url": detail_url,
            "title": title,
            "text": full_text,
        }
    except requests.RequestException:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Google Patents prior art into a local corpus.")
    parser.add_argument("--out-dir", default="patents_corpus", help="Output directory")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--max-patents", type=int, default=80, help="Max patent detail pages to fetch")
    parser.add_argument(
        "--patent-code",
        action="append",
        dest="patent_codes",
        help="Patent code to fetch directly (e.g., US7959765B2). Can be used multiple times.",
    )
    parser.add_argument(
        "--query-url",
        action="append",
        dest="query_urls",
        help="Google Patents query URL. Can be provided multiple times.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "PriorArtIngest/1.0 (+local feasibility research)",
            "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
        }
    )

    query_urls = args.query_urls if args.query_urls else DEFAULT_QUERY_URLS
    query_results = []
    all_codes = []

    if args.patent_codes:
        all_codes.extend(args.patent_codes)
    else:
        for q in query_urls:
            data = fetch_query_page(session, q, args.timeout)
            query_results.append(data)
            all_codes.extend(data["top_patent_codes"])
            time.sleep(args.delay)

    dedup_codes = []
    seen = set()
    for code in all_codes:
        if code not in seen:
            seen.add(code)
            dedup_codes.append(code)
    dedup_codes = dedup_codes[: args.max_patents]

    patent_pages = []
    for code in dedup_codes:
        row = fetch_patent_detail(session, code, args.timeout)
        if row:
            patent_pages.append(row)
        time.sleep(args.delay)

    chunks: list[dict[str, object]] = []
    for row in patent_pages:
        for i, ch in enumerate(chunk_text(row["text"]), start=1):
            chunks.append(
                {
                    "id": f"pat_{len(chunks)+1:05d}",
                    "patent_code": row["patent_code"],
                    "url": row["url"],
                    "title": row["title"],
                    "chunk_index": i,
                    "text": ch,
                }
            )

    (out_dir / "patent_queries.json").write_text(
        json.dumps(query_results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "patent_pages.json").write_text(json.dumps(patent_pages, indent=2, ensure_ascii=False), encoding="utf-8")

    with (out_dir / "patent_chunks.jsonl").open("w", encoding="utf-8") as f:
        for row in chunks:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = [
        "# Patent Prior-Art Corpus Summary",
        "",
        f"- Query pages ingested: {len(query_results)}",
        f"- Unique patent codes identified: {len(dedup_codes)}",
        f"- Patent detail pages captured: {len(patent_pages)}",
        f"- Chunks generated: {len(chunks)}",
        "",
        "## Query sources",
    ]
    if query_results:
        for q in query_urls:
            summary.append(f"- {q}")
    else:
        summary.append("- Manual patent code mode")
    summary.append("")
    summary.append("## Sample patent codes")
    for code in dedup_codes[:30]:
        summary.append(f"- {code}")

    (out_dir / "README.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"Done. Saved prior-art corpus to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
