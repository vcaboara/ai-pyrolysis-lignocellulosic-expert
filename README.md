# Local Pyrolysis and Lignocellulosic RAG

<p align="left">
  <a href="https://github.com/vcaboara/ai-pyrolysis-lignocellulosic-expert/actions/workflows/ci.yml">
    <img alt="CI status" src="https://github.com/vcaboara/ai-pyrolysis-lignocellulosic-expert/actions/workflows/ci.yml/badge.svg?branch=main" />
  </a>
</p>

Note: This badge is pinned to `main` because GitHub does not support dynamically selecting the current branch/PR in a plain Markdown badge URL. For branch- or PR-specific status, open the workflow run (Actions / Checks) and see the step summary for the active ref.

This repository provides a small local retrieval-and-answer workflow for pyrolysis and lignocellulosic research questions. It loads local corpus files, builds a TF-IDF index, retrieves relevant chunks, and can answer questions or produce a feasibility-style review using a local Ollama model when available.

## Branch / PR status

The badge above is intentionally pinned to the `main` branch so the repository landing page shows the default branch status. GitHub does not inject the current branch or PR name into plain Markdown, so branch-specific status must come from CI-generated badge URLs or workflow summaries.

This workflow also emits the active ref and event context in the GitHub Actions summary so branch pushes and PR runs are clearly labeled while they are running.

## Table of contents

- [Local Pyrolysis and Lignocellulosic RAG](#local-pyrolysis-and-lignocellulosic-rag)
  - [Table of contents](#table-of-contents)
  - [Repository layout](#repository-layout)
  - [Prerequisites](#prerequisites)
  - [Basic usage](#basic-usage)
    - [Build the search index](#build-the-search-index)
    - [Ask a question](#ask-a-question)
    - [Run a feasibility pre-review](#run-a-feasibility-pre-review)
    - [Restrict retrieval to a source type](#restrict-retrieval-to-a-source-type)
    - [Disable the local LLM and use only retrieved evidence](#disable-the-local-llm-and-use-only-retrieved-evidence)
    - [Add custom corpora](#add-custom-corpora)
  - [Using run\_local\_ci.py](#using-run_local_cipy)
    - [Run everything](#run-everything)
    - [Run only selected checks](#run-only-selected-checks)
    - [What the CI wrapper checks](#what-the-ci-wrapper-checks)
  - [Running the test suite directly](#running-the-test-suite-directly)
  - [Privacy and repo hygiene](#privacy-and-repo-hygiene)
  - [Troubleshooting](#troubleshooting)
    - [Ollama not responding](#ollama-not-responding)
    - [Index errors](#index-errors)
    - [CI failure](#ci-failure)

## Repository layout

- `pyrolysis_lignocellulosic_ai_training/local_rag.py` — retrieval, indexing, answer, and feasibility logic
- `tests/test_docker_ollama.py` — CLI smoke tests for Docker/Ollama helper commands
- `tests/test_local_rag.py` — unit tests for the local retrieval and indexing helpers
- `scripts/privacy_guard.py` — repo privacy scan for sensitive content and blocked paths
- `run_local_ci.py` — local quality gate wrapper used to mirror CI checks
- `docker-compose.yml` — local Ollama service definition
- `.local_private/` — local-only private files excluded from the public repo

## Prerequisites

- Python 3.13
- Docker + Docker Compose
- A local Ollama service running on `http://localhost:11434`

Recommended setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install scikit-learn joblib requests
pip install -r requirements-dev.txt
```

If you want the local model runtime enabled, start the container:

```powershell
docker compose up -d
```

The Docker Compose file exposes Ollama on port `11434`.

## Basic usage

### Build the search index

```powershell
python -m pyrolysis_lignocellulosic_ai_training.local_rag --build-index
```

This reads the default corpora and saves the vector index under the repository-local `.rag_index/` directory.

### Ask a question

```powershell
python -m pyrolysis_lignocellulosic_ai_training.local_rag --question "What are the key process considerations for lignocellulosic pyrolysis?" --mode answer
```

### Run a feasibility pre-review

```powershell
python -m pyrolysis_lignocellulosic_ai_training.local_rag --question "Assess whether this process is feasible for mixed biomass feedstocks." --mode feasibility
```

### Restrict retrieval to a source type

```powershell
python -m pyrolysis_lignocellulosic_ai_training.local_rag --question "What are the likely patent trends?" --source-filter patent
```

### Disable the local LLM and use only retrieved evidence

```powershell
python -m pyrolysis_lignocellulosic_ai_training.local_rag --question "Summarize the evidence." --no-llm
```

### Add custom corpora

```powershell
python -m pyrolysis_lignocellulosic_ai_training.local_rag --build-index --corpus path\to\custom.jsonl
```

You can pass `--corpus` multiple times to include additional JSONL files.

## Using run_local_ci.py

`run_local_ci.py` is the project’s local quality gate. It runs the same style, lint, type-check, privacy, and test checks that are expected before a change is considered review-ready.

### Run everything

```powershell
python run_local_ci.py --all
```

### Run only selected checks

```powershell
python run_local_ci.py --tests
python run_local_ci.py --privacy
python run_local_ci.py --format
python run_local_ci.py --fix-format
python run_local_ci.py --lint
python run_local_ci.py --mypy
python run_local_ci.py --compose
```

The `--format` flag performs a check-only Black run. Use `--fix-format` to rewrite files in place, or run Black directly:

```powershell
python -m black --check run_local_ci.py tests/test_local_rag.py pyrolysis_lignocellulosic_ai_training/local_rag.py
python -m black run_local_ci.py tests/test_local_rag.py pyrolysis_lignocellulosic_ai_training/local_rag.py
```

These options are useful when you want to focus on a single gate during development.

### What the CI wrapper checks

- Unit tests under `tests/`
- Privacy scan for blocked content and private paths
- Black formatting
- Ruff linting
- Mypy static analysis
- Docker Compose validation

## Running the test suite directly

```powershell
python -m unittest discover -s tests -v
```

This runs the project’s test collection without the additional quality-gate wrappers.

## Privacy and repo hygiene

- Keep private or sensitive corpora out of the public repo.
- Use `.local_private/` for local-only content that must not be committed.
- Run the privacy scan before committing or opening a PR.

## Troubleshooting

### Ollama not responding

Check that Docker is running and the service is up:

```powershell
docker compose ps
curl http://localhost:11434
```

### Index errors

If the index is missing or stale, rebuild it:

```powershell
python -m pyrolysis_lignocellulosic_ai_training.local_rag --build-index
```

### CI failure

Run the local gate from the repo root:

```powershell
python run_local_ci.py --all
```

This surfaces the same kinds of issues that GitHub Actions will catch before a PR is merged.
