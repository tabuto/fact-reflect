---
description: Extract durable facts from this conversation (or recent Claude Code sessions), check them against memory, queue them, then review and apply what the user approves
argument-hint: "[focus] [--history DAYS] [--all-projects] [--dest NAME] [--dry-run] [--all] [--auto-skip-dupes]"
---

# /reflect

Arguments: `$ARGUMENTS`

One command, start to finish: extract candidate facts, check them against
what is already stored, queue them, then let the user choose what actually
goes to MemServer (MCP), CLAUDE.md, AGENTS.md or Copilot instructions. Read
the `fact-capture` skill first (`${CLAUDE_PLUGIN_ROOT}/skills/fact-capture/SKILL.md`)
and follow its criteria, phrasing rules and backends strictly.

## 1. Setup

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" init` and note `backend`.
If no shell is available, use the `mcp` backend described in the skill.

## 2. Extract

Choose the source:

- **Always**: the current conversation, from the start. If the arguments
  contain free text besides the flags below, treat it as a focus and extract
  only facts about that topic.
- **`--history N`** (Claude Code only, add to the current conversation, not
  instead of it) → also run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sessions.py" --days N`
  (add `--all-projects` if requested). It prints unprocessed sessions of the
  current project as `U:`/`A:` lines and ends with `### SESSIONS_INCLUDED: ...`.
  If output is cut at `--max-chars`, process what you got and tell the user to
  run the command again for the rest.

Go through the material and build candidate facts following the skill. For
each candidate decide `category`, `tags`, `confidence`, `scope` (`project` if
it only makes sense inside the current repo, else `global`) and a short
`evidence`. Prefer fewer, richer facts over many fragments; merge statements
about the same subject. Take facts from what the **user** said or confirmed —
assistant turns are context, not a source.

No candidates found (and no items already pending in the queue) → say so in
one line and stop.

## 3. Check against memory before queueing

If the default destination is an MCP server and its search tool is available
(e.g. `recall`), run one search per candidate subject (limit 3). Drop
candidates already stored with the same meaning; for candidates that
**contradict** a stored fact, keep them, tag `update`, and add an evidence
note "supersedes: <old fact>".

## 4. Queue

- `--dry-run` → show the candidate table (merged with any already-pending
  items, see step 5) and stop; queue nothing.
- `file` backend → one call: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" add` with a JSON array on stdin.
- `mcp` backend → one `add_task` per fact, as described in the skill.

With `--history`, after queueing mark the sessions as processed:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sessions.py" --mark-processed <ids from SESSIONS_INCLUDED>`.

## 5. Load the full queue

The items just queued may join others already pending from before (e.g. added
via `/fact-queue add`). Load everything pending:

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" config show` → destinations, routing, backend.
2. Pending items:
   - `file` backend: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" list --json`
     (with `--all`: `--status all`, then keep `pending` + `skipped`).
   - `mcp` backend: `list_tasks(status="pending")`, keep `section == "fact-queue"`,
     parse `FACT|category|destination|confidence|tags|text`.
3. `--dest NAME` → use NAME as the proposed destination for every item.

## 6. Check against the destination

For items proposed for an `mcp` destination, if its `search_tool` exists,
search each item (limit 3, skip ones already checked in step 3) and label it:

- **new** — nothing similar stored
- **dup** — same meaning already stored (with `--auto-skip-dupes`, mark these skipped without asking)
- **update** — contradicts or refines a stored fact (show the old one in a few words)

For `agent-file`/`copilot` destinations, read the target file and label
duplicates of existing bullets the same way.

## 7. Ask the user

Show one numbered table, in the user's language:

`# · fact · category · → destination · label · conf`

Then list the available destination names (from the config) and ask for the
decision in one reply, with this syntax (explain it in one line):

- `all` — apply every item to its proposed destination
- `1,3,5` — apply only these (the others stay pending)
- `2>copilot` — apply item 2 to another destination
- `4="new text"` — edit item 4, then apply it
- `-6` — skip item 6 (won't be proposed again unless `/reflect --all`)
- `x7` — delete item 7 from the queue
- `none` — change nothing

Items not mentioned stay **pending**. If an `AskUserQuestion` tool is
available and there are ≤ 4 items, you may ask with a multi-select instead.

(`--dry-run` already stopped the flow at step 4, before this point is reached.)

## 8. Apply

Group approved items by destination.

**MCP destination** (`type: mcp`):
1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" export-mcp <dest> <ids...>` → payload.
2. Call the server's `batch_tool` (e.g. `remember_facts`) **once** with the
   `facts` array. If only `single_tool` exists, call it per fact.
   For **update** items, also mark the old memory as outdated if the server
   offers a tool for it — ask first if unsure.
3. Only after success: `fq.py mark <ids> --status applied --destination <dest>`.

**File destinations** (`agent-file`, `copilot`):
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" write <dest> <ids...>` — writes into the managed
section and marks the items applied. Relative paths (`./CLAUDE.md`) resolve
from the current working directory: if that is not the intended repo, say so
and ask for the path (`--path`).

**Edits** → `fq.py update <id> --text "..."` before applying.
**Skips** → `fq.py mark <ids> --status skipped`. **Deletes** → `fq.py drop <ids>`.

With the `mcp` backend, use the MCP tools for all of the above and
`delete_task` each item once applied, skipped or deleted.

If a write fails, leave those items pending and report the error.

## 9. Close

Reply with one short summary: how many facts were extracted and queued, how
many dropped as duplicates before queueing, and then per destination how many
applied, skipped, still pending, and the files changed. If more than 30
applied/skipped items are stored, suggest `fq.py purge --older-than 30`.
