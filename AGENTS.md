# AGENTS.md

This file defines how AI coding agents should work in this repository.

## Collaboration style (required)

- Work in small chunks.
- After each meaningful chunk, pause and check in before continuing.
- Prioritize teaching over just fixing: explain what changed, why, and how to debug similar issues.
- Share failures and first error lines clearly, then explain the root cause and next step.
- Avoid long chains of actions without intermediate updates.

## Preferred execution flow

For most tasks, use this loop:

1. Propose the next small step in 1-2 sentences.
2. Run only that step.
3. Report result (pass/fail, key output, first error if any).
4. Explain what it means.
5. Ask whether to continue to the next step.

## Git and PR workflow

- Never do feature work on `main`.
- Create or switch to a task branch before any edits, commits, rebases, or pushes.
- Treat `main` as protected: no direct commits, no rebases, no resets.
- Before commit/push, summarize staged changes in plain language.
- If push/PR fails, stop and explain the exact blocker before trying larger recovery actions.
- Do not rewrite history without explicit approval.
- Do not force push without explicit approval in the current session.
- If history cleanup seems necessary, propose options and wait for user confirmation before executing.

## CI / Docker notes for this repo

- Canonical compose file: `docker/docker-compose.yml`.
- Preferred env defaults:
  - `COMPOSE_FILE=docker/docker-compose.yml`
  - `COMPOSE_PROFILES=ci`
- Build-stage CI gates run in Docker build (`builder` target).
- Runtime privacy check is intended to run with mounted workspace context.

## Communication format

- Keep updates concise and frequent.
- Include exact command used and exit code when relevant.
- If a command is interactive or risky, explain and ask first.
