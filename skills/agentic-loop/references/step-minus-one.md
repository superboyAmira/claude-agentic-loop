# Step -1 — Project markup bootstrap

If the project has **no** navigation/markup index, create it **before** Step 0.

## When to run

Run Step -1 when **none** of these exist (or only empty stubs):

- `.llm/manifest.json`
- `CLAUDE.md`
- `AGENTS.md`

If `.llm/manifest.json` exists and is usable -> **skip** Step -1 (but still apply the manifest
rules below when adding new docs later).

A project that keeps its index at a legacy `.cursor/manifest.json` -> move it to
`.llm/manifest.json` (`git mv` when tracked), then continue.

## Model

Use a **`sonnet`** subagent (`Agent` tool, `subagent_type: general-purpose`, `model: sonnet`),
or run it inline if the parent is already on Sonnet. Do **not** spend Opus parent time on
bootstrap indexing.

## What to create

Create the `.llm/` directory first — it is the **only** agent directory that gets committed:

```bash
mkdir -p .llm
```

Minimum:

1. `.llm/manifest.json` — index of important docs/code areas (`version`, `generated`,
   `module`, `documents[]` with `id`, `path`, `title`, `summary`, `tags`, `related`)
2. Optional if helpful: a short `CLAUDE.md` with test/lint commands and "where to look".

Scan: README, `docs/`, `cmd/`, `internal/`, `src/`, `deploy/`, existing business docs. Keep
summaries factual; do not invent APIs.

## `.gitignore` rules (mandatory)

`.llm/manifest.json` is the shared, git-trackable navigation index. Everything else the agent
writes is local runtime state. Ensure the project's `.gitignore` contains:

```gitignore
# Local agent state, never shared
.llm/telemetry/
```

- `.llm/telemetry/` — the transcript ledger (`events.jsonl`, `session.json`); the collector
  also drops a self-ignoring `.gitignore` there, but the explicit entry keeps intent visible
- `.llm/manifest.json` stays tracked — verify with `git check-ignore -v -- .llm/manifest.json`
  (empty output = trackable)

Do not ignore `.llm/` as a whole: that would hide the manifest.

## Manifest rules (mandatory)

Only list paths that Git can see.

1. **Never** add a path to `documents[]` if `git check-ignore -q <path>` says it is ignored.
2. Before adding an entry, verify with `git check-ignore -v -- <path> || true` (empty output
   => trackable => OK for the manifest).
3. Prefer product/business docs under a **tracked** tree, conventionally `docs/business/`.
4. If a **business / runbook / operator** doc created during the loop lands under an ignored
   path (e.g. parent `/docs/` is ignored):
   - **un-ignore** it. Prefer ignoring **contents** (`/docs/*`) not the directory itself
     (`/docs/`), otherwise Git will not apply negations under that tree:
     ```gitignore
     /docs/*
     !/docs/business/
     !/docs/business/**
     ```
   - then add the path to `.llm/manifest.json`
5. Session scratch (`docs/agentic/…`, drafts) may stay ignored; do **not** put those paths in
   the manifest. Link them from the plan/session README instead.
6. When promoting a business doc out of ignore, update `needs-documenting.md` accordingly.

## Gate

After writing files, show paths + Stage report for Step -1 (see `stage-report.md`), then
continue to Step 0 on the planning parent model (ask the user for `/model opus`).
