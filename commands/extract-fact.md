---
description: Extract durable facts from this conversation (or recent Claude Code sessions) and add them to the knowledge queue for review
argument-hint: "[focus] [--history DAYS] [--all-projects] [--dry-run]"
---

# /extract-fact

Arguments: `$ARGUMENTS`

You are filling the **fact-reflect knowledge queue**. Nothing is written to
MemServer or to agent files here: that happens later in `/reflect`.

## 1. Setup

1. Read the `fact-capture` skill (`${CLAUDE_PLUGIN_ROOT}/skills/fact-capture/SKILL.md`)
   for the criteria, the phrasing rules and the backends. Follow them strictly.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" init` and note `backend`.
   If no shell is available, use the `mcp` backend described in the skill.

## 2. Choose the source

- **No `--history`** → analyse the current conversation, from the start.
  If the user gave a focus (any free text in the arguments), extract only facts
  about that topic.
- **`--history N`** (Claude Code only) → run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sessions.py" --days N`
  (add `--all-projects` if requested). It prints unprocessed sessions of the
  current project as `U:`/`A:` lines and ends with `### SESSIONS_INCLUDED: ...`.
  If output is cut at `--max-chars`, process what you got and tell the user to
  run the command again for the rest.

## 3. Extract

Go through the material and build candidate facts following the skill. For
each candidate decide `category`, `tags`, `confidence`, `scope`
(`project` if it only makes sense inside the current repo, else `global`) and a
short `evidence`. Prefer fewer, richer facts over many fragments; merge
statements about the same subject. Take facts from what the **user** said or
confirmed — assistant turns are context, not a source.

If the material contains lines starting with `ricorda:` / `remember:` they may
already be queued by the hook: the script will drop duplicates anyway.

## 4. Check before queueing (optional but recommended)

If the default destination is an MCP server and its search tool is available
(e.g. `recall`), run one search per candidate subject (limit 3). Drop candidates
already stored with the same meaning; for candidates that **contradict** a stored
fact, keep them and add the tag `update` and an evidence note
"supersedes: <old fact>".

## 5. Queue

- `--dry-run` → only show the candidate table, queue nothing.
- `file` backend → one call: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" add` with a JSON array on stdin.
- `mcp` backend → one `add_task` per fact, as described in the skill.

For `--history`, after queueing mark the sessions as processed:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sessions.py" --mark-processed <ids from SESSIONS_INCLUDED>`.

## 6. Report

Reply in the user's language, short:

- a compact table: id · category · suggested destination · fact
- how many were skipped as duplicates
- one line: "Run /reflect to choose what goes to MemServer."

Do not ask for approval here: the queue *is* the approval step.
