---
name: fact-capture
description: Queue durable facts about the user (preferences, projects, decisions, people, corrections, conventions) for later review instead of saving them straight to memory. Use when the user says "ricorda:", "remember:", "metti in coda", asks to extract facts from a conversation, or asks to review/flush the knowledge queue (/extract-fact, /reflect).
---

# fact-capture — the knowledge queue

This plugin puts a **review step** between conversations and long-term memory.
Facts are first queued; the user later decides with `/reflect` what goes where
(MemServer via MCP, CLAUDE.md, AGENTS.md, Copilot instructions, ...).

**Policy while this plugin is installed:** do not call `remember_fact` /
`remember_facts` (or edit CLAUDE.md / AGENTS.md / copilot-instructions) on your
own initiative to store something learned in conversation. Queue it. The only
writes to destinations happen inside `/reflect`, after the user approves, or
when the user explicitly asks to save something right now.

## What is worth queueing

Queue a candidate only if it would still be true and useful in a month, in a
conversation about something else:

- **preference** — how the user wants things done, tastes, recurring choices
- **project** — a project they run: name, goal, stack, status, hosting, key decisions
- **person** — someone in their world and their relation to the user (no private details about that person)
- **decision** — a choice they made ("we go with Quarkus for the new service")
- **convention** — rules for a codebase or toolchain ("tests with pytest -q", "branch naming feat/...")
- **correction** — a rule for the agent after a correction ("no, use pnpm not npm")
- **fact** — other stable facts about their world (roles, places, tools, setups)

Do **not** queue:

- one-off task instructions, questions, small talk, transient moods
- things you inferred, researched, fetched or recommended — only what the user said or confirmed
- anything already in the queue or (if you checked) already in MemServer
- secrets: passwords, tokens, API keys, IDs, card or account numbers
- sensitive personal data (health, sexual life, criminal matters, religion,
  political views, ...) unless the user explicitly asks to store it — and even
  then never IDs, card numbers or credentials

## How to phrase a fact

- One atomic fact per item, self-contained, readable without the conversation:
  "Alex hosts demo-app on Render and deploys via git push + webhook"
  — not "it's on Render".
- Name the subject explicitly (the user's name/nickname if known, otherwise "The user").
- Write in the language the user uses for their memory (default: the conversation language).
- Keep dates absolute ("since October 2026", not "since last week").
- `confidence`: 0.95 explicit "remember", 0.85 stated plainly, 0.7 implied by context.
- `evidence`: a short paraphrase (≤ 200 chars) of where it came from.
- `tags`: 1–4 lowercase keywords (project name, domain).

## Locating the scripts

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder. If it is not expanded in your
context, resolve it once and reuse the path:

```bash
FQ=$(ls -d ~/.claude/plugins/cache/*/fact-reflect/*/scripts/fq.py ~/.claude/plugins/*/fact-reflect/scripts/fq.py 2>/dev/null | head -1); echo "$FQ"
```

## Storage backends

Read the config first: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" config show`
(run `... fq.py init` once if it does not exist). `queue.backend` decides:

### `file` (default — Claude Code / desktop)

Queue with JSON on stdin (array or single object):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fq.py" add <<'JSON'
[{"text": "...", "category": "project", "tags": ["pyspendless"],
  "confidence": 0.85, "evidence": "...", "source": "chat"}]
JSON
```

The script dedups (exact + near-duplicate) and assigns a suggested destination
from `routing` in the config. Other useful commands: `list [--json] [--status all]`,
`update ID --text/--category/--destination`, `mark IDS --status skipped`, `drop IDS`.

### `mcp` (when there is no persistent shell, e.g. claude.ai chat or phone)

The queue lives on the MCP server as tasks, so it is shared by all devices.
Use the tools named in `queue.mcp` (default server `mcp-memory`):

- queue: `add_task(content=..., section="fact-queue")` where `content` is
  `FACT|<category>|<destination>|<confidence>|<tags comma>|<text>`
- read: `list_tasks(status="pending")`, keep only `section == "fact-queue"`
- after `/reflect` applies or skips an item: `delete_task` on it

If the script is unavailable and no config can be read, assume the `mcp`
backend with the defaults above, and destination `memserver`.

## Destinations (used by /reflect)

| type | how it is written |
|------|-------------------|
| `mcp` | Claude calls the server's `batch_tool` (e.g. `remember_facts`) with `{text, tags}`; then `fq.py mark IDS --status applied --destination NAME` |
| `agent-file` | `fq.py write NAME IDS` — merged into a managed `<!-- fact-reflect -->` section of CLAUDE.md / AGENTS.md |
| `copilot` | same as agent-file, default path `.github/copilot-instructions.md` |

Add or change destinations with `fq.py config set destinations.<name> '<json>'`
and routing with `fq.py config set routing.<category> <name>`.
