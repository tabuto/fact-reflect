---
description: Review the knowledge queue and choose which facts go to MemServer (MCP), CLAUDE.md, AGENTS.md or Copilot instructions
argument-hint: "[--dest NAME] [--dry-run] [--all] [--auto-skip-dupes]"
---

# /reflect

Arguments: `$ARGUMENTS`

Review the **fact-reflect knowledge queue** with the user and apply only what
they approve. Read the `fact-capture` skill first
(`${CLAUDE_PLUGIN_ROOT}/skills/fact-capture/SKILL.md`).

## 1. Load

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" config show` → destinations, routing, backend.
2. Pending items:
   - `file` backend: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" list --json`
     (with `--all`: `--status all`, then keep `pending` + `skipped`).
   - `mcp` backend: `list_tasks(status="pending")`, keep `section == "fact-queue"`,
     parse `FACT|category|destination|confidence|tags|text`.
3. Empty queue → say so in one line and stop.
4. `--dest NAME` → use NAME as the proposed destination for every item.

## 2. Check against the destination

For items proposed for an `mcp` destination, if its `search_tool` exists, search
each item (limit 3) and label it:

- **new** — nothing similar stored
- **dup** — same meaning already stored (with `--auto-skip-dupes`, mark these skipped without asking)
- **update** — contradicts or refines a stored fact (show the old one in a few words)

For `agent-file`/`copilot` destinations, read the target file and label
duplicates of existing bullets the same way.

## 3. Ask the user

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

With `--dry-run`, stop after showing the table.

## 4. Apply

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

## 5. Close

Reply with one short summary: how many applied per destination, skipped,
still pending, and the files changed. If more than 30 applied/skipped items are
stored, suggest `fq.py purge --older-than 30`.
