# Changelog

## 1.0.0 — 2026-09-11

- Initial Claude Code port of [superboyAmira/cursor-agentic-loop](https://github.com/superboyAmira/cursor-agentic-loop):
  6 skills, 8 pinned-model subagents, transcript-based telemetry hooks.
- `install.sh` — installs into `~/.claude/{skills,agents,agentic-loop/hooks}` and wires
  telemetry hooks into `~/.claude/settings.json`. Also supports `--no-hooks` and `--uninstall`.
- `sync-from-local.sh` — pulls edits made to the installed copy back into this repo.
- `release.sh` — version/changelog/tag helper for publishing new versions.
