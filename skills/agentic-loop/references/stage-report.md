# Stage telemetry (after every step)

After **each** completed step (-1…10, including 4.5), print a **Stage report** block in chat
**before** moving on. Do not skip. Also append the same block to `docs/agentic/<session>/telemetry.md`.

Print even when the step is still in progress (status: `in progress`) if you pause for user
Q&A; print again with `done` when the step finishes.

## Required format

Use this shape (field names fixed; fill real values or `n/a`). `gate` and `findings` appear when
the step ran the verify gate / a review phase.

```markdown
### Stage report — Step N · <Name>
- status: done | in progress | skipped | blocked
- model_parent: <id or unknown>
- models_subagents: [<id>, ...]
- agents_used: [<agentic-loop-*> xN (tokens), ...]
- tools: Read/Grep/Agent/Write/Bash/... (counts if known)
- files_touched: N (list key paths, max 10)
- tokens: <parent in/out; subagents in/out; total - from the transcript ledger; else `n/a (not exposed)`>
- context: <size of the parent's last prompt, from the ledger>
- wall_time: <ISO local start->end or `Xm Ys`; mandatory when known>
- gate: <verify gate result in this step: pass | fail (+ failed steps); runs / red runs>
- findings: <review steps: total / accepted / rejected, per reviewer accepted/total>
- cost_notes: <mode notes; else brief fact>
- artifacts: <paths written this step>
- next: Step N+1 · <Name> | <concrete next action>
```

### Example

```markdown
### Stage report — Step 5 · Agent Review
- status: done
- model_parent: <executor model id>
- models_subagents: [<reviewer model id>]
- agents_used: [agentic-loop-quality x2 (1.9M tok), agentic-loop-testing x2 (1.4M tok), agentic-loop-fixer x2 (6.1M tok), …]
- tools: Agent x12 / Bash x6 / Read x4
- files_touched: 3 (internal/a.go, internal/a_test.go, internal/b.go)
- tokens: parent in 1,180,993 / out 8,146 over 14 message(s); subagents in 11,402,118 / out 61,590 over 12 agent(s); total 12,652,847
- context: ~92k tokens in the last parent prompt (peak 96k)
- wall_time: 21m 04s
- gate: pass (last run; 3 run(s), 1 red)
- findings: total 17 / accepted 6 / rejected 11 (quality 3/4, implementation 1/2, testing 2/5, documentation 0/3, simplification 0/3)
- cost_notes: 2 iterations; stopped on no progress (iteration 2 accepted 0)
- artifacts: internal/service/achievements/iron_reputation.go
- next: Step 6 · Code smells
```

## Where the numbers come from

Do **not** guess. Real tokens, durations and subagent stats come from the transcript ledger —
see [telemetry-hooks.md](telemetry-hooks.md) for the field map.

The collector is installed user-wide at `~/.claude/agentic-loop/hooks/` and wired into
`~/.claude/settings.json`. Run from the project directory:

```bash
T=~/.claude/agentic-loop/hooks/telemetry-report.py
python3 $T mark "Step 6 · Code smells"                   # at step start
python3 $T report --step 6 --name "Code smells"          # at step end
python3 $T findings --step 6 --reviewer smells --total 4 --accepted 1 --rejected 3   # review steps
python3 $T summary                                       # before Docs & PR
python3 $T yield                                         # review yield across all runs
python3 $T status                                        # sanity check
```

`report` prints the Stage report block with every measurable field filled from the ledger
(including `gate` and `findings` recorded since the mark) and `<fill: …>` placeholders for the
judgement fields (`status`, `cost_notes`, `artifacts`, `next`). Fill those in yourself - never
ship a report with placeholders left in it.

If the collector is **not** installed: offer to run `./install.sh` from the claude-agentic-loop
clone, and until then report `tokens: n/a (hooks not installed)` rather than inventing numbers.

## Review yield (steps 5–8)

Every review step records, **per reviewer invocation**, how many findings it produced and how
many the fixer accepted - the only way to tell which review passes earn their cost.

1. Reviewers prefix every finding with an ID: `Q` quality, `I` implementation, `T` testing,
   `D` documentation, `S` simplification, `SM` smells, `X` external, `C` critical
   (numbering restarts every iteration: `Q1`, `Q2`, …). The verify-gate repair uses `G`.
2. The fixer answers per ID: `fixed: Q2 -> …` / `rejected: T1 -> …`.
3. After the fixer, for each reviewer that ran (including clean ones, with `--total 0`):

   ```bash
   python3 $T findings --step 5 --reviewer testing --iteration 1 \
     --total 5 --accepted 2 --rejected 3 --severe-accepted 1
   ```

   `--severe-accepted` = accepted CRITICAL + MAJOR. Findings dropped as exact repeats of already
   rejected ones count as rejected.
4. Rows go to the project ledger and to the user-wide `~/.claude/agentic-loop/telemetry/review-yield.jsonl`.
   `telemetry-report.py yield` aggregates them across projects: after 15–20 loops it shows which
   reviewer produces 2 accepted findings out of 40, and that one gets cut or re-prompted.

## Rules

- Prefer real numbers from the ledger; then `/cost` output.
- Include failed/retried subagents in the report.
- Keep the block compact; no essay.
- **wall_time is mandatory when the clock is known.** Include user-gate wait; note idle/abort
  separately. If unknown: `n/a`.
- Keep a running ledger for steps -1…10 in `telemetry.md`.
- Skipping the Stage report is a process failure — same severity as skipping session docs.

## Loop cost summary (after the last completed step, before Docs & PR / Stop)

Print this table even if some cells are `n/a`. Also write it to
`docs/agentic/<session>/telemetry.md`. `telemetry-report.py summary` produces it, across every
session transcript the loop used (a resumed loop spans several).

```markdown
### Loop cost summary
| Step | Name | Wall | Subagents | Tokens parent in/out | Tokens subagents in/out | Findings acc/total | Gate runs (red) |
|------|------|------|-----------|----------------------|-------------------------|--------------------|-----------------|
| -1 | Markup | … | 0 | n/a | - | - | - |
| … | … | … | … | … | … | … | … |
| **Σ** | | **…** | **N** | **…** | **…** | **…** | |

- session_wall: <first stage start -> now>
- tokens_total: <parent + subagents>
- tokens_source: transcript ledger (N session transcript(s)) | n/a (not exposed)
- limit_hits: <counter[scope]=value>limit, if any>
```

Do not skip the summary because tokens are missing — still show wall time and subagent counts.
