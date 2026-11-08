# Local Pyrolysis and Lignocellulosic RAG

<p align="left">
  <a href="https://github.com/vcaboara/ai-pyrolysis-lignocellulosic-expert/actions/workflows/ci.yml">
    <img alt="CI status" src="https://github.com/vcaboara/ai-pyrolysis-lignocellulosic-expert/actions/workflows/ci.yml/badge.svg?branch=main" />
  </a>
   </br>
   <small>Note: Badge is pinned to <code>main</code></small>
</p>

This repository provides a small local retrieval-and-answer workflow for pyrolysis and lignocellulosic research questions. It loads local corpus files, builds a TF-IDF index, retrieves relevant chunks, and can answer questions or produce a feasibility-style review using a local Ollama model when available.

## Branch / PR status

The badge above is intentionally pinned to the `main` branch so the repository landing page shows the default branch status.

This workflow also emits the active ref and event context in the GitHub Actions summary so branch pushes and PR runs are clearly labeled while they are running.

## Table of contents

- [Local Pyrolysis and Lignocellulosic RAG](#local-pyrolysis-and-lignocellulosic-rag)
  - [Branch / PR status](#branch--pr-status)
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
    - [Run the same quality gate in a container](#run-the-same-quality-gate-in-a-container)
    - [Run only selected checks](#run-only-selected-checks)
    - [What the CI wrapper checks](#what-the-ci-wrapper-checks)
  - [Running the test suite directly](#running-the-test-suite-directly)
  - [Privacy and repo hygiene](#privacy-and-repo-hygiene)
  - [Project structure](#project-structure)
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
- `docker/docker-compose.yml` — local Ollama and CI service definition
- `.local_private/` — local-only private files excluded from the public repo

## Prerequisites

- Python 3.13
- Docker + Docker Compose
- A local Ollama service running on `http://localhost:11434`

Recommended setup:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install scikit-learn joblib requests
pip install -r requirements-dev.txt
```

If you want the local model runtime enabled, set the compose file once in the current shell and start the container (or execute other commands):

```powershell
$env:COMPOSE_FILE = "docker/docker-compose.yml"
$env:COMPOSE_PROFILES = "ci"
docker compose up -d
```

For a persistent setup across shells, use a repo-local `.env` (see `.env.example`).

The Docker Compose file (in `docker/` folder) exposes Ollama on port `11434`.

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

### Run the same quality gate in a container

Set the compose file once in the shell and then run the CI service normally:

```powershell
$env:COMPOSE_FILE = "docker/docker-compose.yml"
$env:COMPOSE_PROFILES = "ci"
docker compose --profile ci build ci
docker compose --profile ci up --abort-on-container-exit --exit-code-from ci --no-build ci
```

After the run, clean up the compose-managed container, network, and the local CI image:

```powershell
docker compose --profile ci down --rmi local --volumes --remove-orphans
```

The `ci` service mounts your working tree into the container so checks that rely on Git metadata (such as `privacy_guard.py`) run against a real repository.

### Run only selected checks

```powershell
python run_local_ci.py --format              # Black formatter (check only)
python run_local_ci.py --fix-format          # Black formatter (fix files in place)
python run_local_ci.py --lint                # Ruff linter
python run_local_ci.py --mypy                # Type checker
python run_local_ci.py --tests               # Unit tests
python run_local_ci.py --security            # Bandit SAST scan
python run_local_ci.py --deps-audit          # Dependency vulnerability audit
python run_local_ci.py --image-scan          # Container image vulnerability scan
python run_local_ci.py --privacy             # Privacy/secrets scan
python run_local_ci.py --compose             # Docker Compose validation
```

The `--format` flag performs a check-only Black run. Use `--fix-format` to rewrite files in place, or run Black directly:

```powershell
python -m black --check run_local_ci.py tests/test_local_rag.py pyrolysis_lignocellulosic_ai_training/local_rag.py
python -m black run_local_ci.py tests/test_local_rag.py pyrolysis_lignocellulosic_ai_training/local_rag.py
```

These options are useful when you want to focus on a single gate during development.

### What the CI wrapper checks

- Unit tests under `tests/`
- Bandit security scan
- pip-audit dependency vulnerability scan
- Trivy container image security scan
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

## Project structure

- `docker/` - Docker configuration files (Dockerfile.devsecops, docker-compose.yml, .dockerignore)
- `results/` - Security scan outputs and reports (not committed to git)
- `tests/` - Unit tests
- `scripts/` - Utility scripts
- `utils/` - Python utility modules
- `pyrolysis_lignocellulosic_ai_training/` - Main application package

For security policy, vulnerability findings, and risk assessment, see [SECURITY.md](SECURITY.md).

## Troubleshooting

### Ollama not responding

Check that Docker is running and the service is up:

```powershell
$env:COMPOSE_FILE = "docker/docker-compose.yml"
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

If the Docker build fails during the Black formatting check, that is expected behavior: the builder stage runs `python run_local_ci.py --tests --security --deps-audit --format --lint --mypy`, and Black is part of that gate. Fix the files it reports, or run:

```powershell
python run_local_ci.py --fix-format
```

before rebuilding the CI image.
