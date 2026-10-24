---
description: Inspect and manage the fact-reflect knowledge queue (list, add, edit, drop, purge, destinations, config)
argument-hint: "[list|add <text>|edit <id> <text>|drop <id...>|purge|destinations|config]"
---

# /fact-queue

Arguments: `$ARGUMENTS`

Small utility around `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py"`
(see the `fact-capture` skill for backends). Map the arguments:

| argument | action |
|----------|--------|
| *(empty)* or `list` | `fq.py list` and show it as a compact table |
| `all` | `fq.py list --status all` |
| `add <text>` | `fq.py add --text "<text>" --category <best guess>` |
| `edit <id> <text>` | `fq.py update <id> --text "<text>"` |
| `dest <id> <name>` | `fq.py update <id> --destination <name>` |
| `drop <id...>` | `fq.py drop <ids>` |
| `purge [days]` | `fq.py purge --older-than <days or 0>` |
| `destinations` | `fq.py config destinations` |
| `config` | `fq.py config show` |
| `set <key> <value>` | `fq.py config set <key> <value>` (e.g. `routing.convention copilot`) |

Run `fq.py init` first if the config does not exist. With the `mcp` backend use
`list_tasks` / `add_task` / `delete_task` instead. Answer briefly in the user's language.
