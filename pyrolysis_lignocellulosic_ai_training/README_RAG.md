# Local RAG Pipeline: Pyrolysis + Lignocellulosic Expert

This pipeline provides:

1. Local indexing of selected corpora.
2. Citation-first answers.
3. Feasibility output split into facts, assumptions, and unknowns.

## Files

- `local_rag.py` - CLI for indexing and querying.
- `interactive_shell.py` - Interactive chat shell over local RAG.
- `repo_ingest.py` - Build repository corpus JSONL for code/doc retrieval.
- `patents_corpus/patent_chunks.jsonl`
- `repo_corpus/repo_chunks.jsonl` (optional, generated)

## Setup

```powershell
py -m pip install -r requirements.txt
```

## Build Index

```powershell
py .\local_rag.py --build-index
```

If you want project code/docs included in retrieval:

```powershell
py .\repo_ingest.py --repo-root .. --output .\repo_corpus\repo_chunks.jsonl
py .\local_rag.py --build-index
```

`local_rag.py` auto-loads `repo_corpus/repo_chunks.jsonl` when present.

This creates `.rag_index/` with:

- `vectorizer.joblib`
- `matrix.joblib`
- `records.json`

## Ask a Question (Answer Mode)

```powershell
py .\local_rag.py --question "What process controls are critical for pyrolysis gas handling?" --mode answer --top-k 8
```

### Without LLM generation (extractive fallback)

```powershell
py .\local_rag.py --question "What process controls are critical for pyrolysis gas handling?" --mode answer --no-llm
```

## Feasibility Review Mode

```powershell
py .\local_rag.py --question "Evaluate feasibility of a continuous lignocellulosic pyrolysis concept for IP diligence" --mode feasibility --top-k 10
```

Output sections:

- `Facts`
- `Assumptions`
- `Unknowns`
- `Feasibility Signals`
- `Recommended Next Validation Steps`

## Retrieval Quality Controls

Retriever components:

- lexical relevance (cosine similarity)
- query keyword overlap
- reciprocal-rank fusion
- URL-level source deduplication by default

Useful flags:

```powershell
# Adjust external source preference (default 0.0)
py .\local_rag.py --question "..." --mode answer --external-boost 0.10

# Allow multiple hits from the same URL (dedupe is on by default)
py .\local_rag.py --question "..." --mode answer --allow-duplicate-sources

# Force repo-only retrieval when asking implementation/code questions
py .\local_rag.py --question "How does indexing work?" --mode answer --source-filter repo
```

## Optional: Use a Specific Ollama Model

```powershell
py .\local_rag.py --question "..." --mode feasibility --model llama3.1:8b
```

If Ollama is unavailable, the script falls back to extractive output from retrieved chunks.

## Interactive Shell

```powershell
py .\interactive_shell.py
```

In-shell commands:

- `/help`
- `/mode answer|feasibility`
- `/model llama3.1:8b`
- `/filter all|external|patent|repo`
- `/topk 10`
- `/llm on|off`
- `/reindex`
- `/repo-sync` (rebuild repo corpus then rebuild index)
- `/quit`

Any non-command line is treated as your question.

## Docker + Ollama

```powershell
# start Ollama only
docker compose up -d ollama

# pull a model inside the running container
docker compose exec ollama ollama pull llama3.1:8b

# quick health check
docker compose exec ollama ollama list
```

Optional browser UI:

```powershell
# starts Ollama + Open WebUI at http://localhost:3000
docker compose --profile ui up -d
```
