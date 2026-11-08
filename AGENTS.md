# Repository Agent Guidelines

## Workflow

- Work in small, reviewable chunks and pause for user confirmation between larger changes.
- Prefer minimal, targeted edits over broad refactors.
- Do not run destructive git commands unless the user explicitly requests them.
- When debugging, report the first failing step and the exact failure line.

## Docker and CI

- Canonical compose file: `docker/docker-compose.yml`.
- CI profile commands should use `docker compose -f docker/docker-compose.yml --profile ci ...`.
- Treat local runtime images as build artifacts, not pull-only dependencies.

## Documentation Standards

- Hard-wrap Markdown prose at 120 characters maximum.
- Keep list items and long bullets wrapped to 120 characters as well.
- Prefer concise sections and actionable wording.
- When updating existing docs, preserve headings and intent while enforcing line-length limits.

## Quality Expectations

- Validate changed commands when practical.
- Keep changes scoped to the request.
- If assumptions are required, state them clearly in the final summary.
