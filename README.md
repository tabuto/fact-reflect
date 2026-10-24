# fact-reflect

A **knowledge queue** for Claude. Conversations produce candidate facts; you
decide which ones become long-term memory, and where they go.

```
conversation ──/extract-fact──►  queue  ──/reflect (you choose)──►  MemServer (MCP)
  "ricorda: …" ──hook──────────►                                    CLAUDE.md / AGENTS.md
                                                                    .github/copilot-instructions.md
```

Inspired by [claude-reflect](https://github.com/BayramAnnakov/claude-reflect),
but the target is pluggable: an MCP memory server, agent files, or Copilot.

## Commands

| Command | What it does |
|---------|--------------|
| `/extract-fact [focus]` | Extracts durable facts from the current conversation and queues them |
| `/extract-fact --history 7` | Same, from the last 7 days of Claude Code sessions in this project (`--all-projects` for all) |
| `/reflect` | Shows the queue, checks for duplicates on the destination, and applies only what you approve |
| `/reflect --dest copilot` | Proposes a single destination for every item |
| `/reflect --dry-run` | Preview only |
| `/fact-queue` | List, add, edit, drop, purge; show/change destinations |

In `/reflect` you answer in one line: `all`, `1,3`, `2>copilot`,
`4="edited text"`, `-6` (skip), `x7` (delete), `none`.

Lines starting with `ricorda:` / `remember:` / `memorizza:` are queued
automatically by a hook (Claude Code only, no tokens spent).

## Destinations

Configured in `~/.fact-reflect/config.json` (created on first run).

| Name | Type | Target |
|------|------|--------|
| `memserver` *(default)* | `mcp` | `remember_facts` on the `mcp-memory` server, duplicate check with `recall` |
| `claude-global` | `agent-file` | `~/.claude/CLAUDE.md` |
| `claude-project` | `agent-file` | `./CLAUDE.md` |
| `agents` | `agent-file` | `./AGENTS.md` |
| `copilot` | `copilot` | `./.github/copilot-instructions.md` |

Files are written only inside a managed block
(`<!-- fact-reflect:start -->` … `<!-- fact-reflect:end -->`), so the rest of
the file is never touched.

Each fact gets a suggested destination from its category (`routing`):
corrections → `claude-global`, conventions → `claude-project`, everything else
→ `memserver`. Change it:

```bash
python3 scripts/fq.py config set routing.convention copilot
python3 scripts/fq.py config set destinations.work-memory '{"type":"mcp","server":"work-mem","batch_tool":"remember_facts","search_tool":"recall"}'
```

## Queue backends

- **`file`** (default): `~/.fact-reflect/queue.jsonl`. Best with Claude Code
  and the desktop app. Point `queue.path` to a synced folder to share it
  between computers.
- **`mcp`**: the queue lives on the MCP server as tasks (`section: fact-queue`),
  so it works from claude.ai and the phone too. Enable with
  `fq.py config set queue.backend mcp`.

## Install

From Claude Code:

```bash
claude plugin marketplace add tabuto/fact-reflect
claude plugin install fact-reflect@tabuto-plugins
```

Restart Claude Code. From claude.ai / the desktop app: **Customize → Plugins →
add marketplace from GitHub** → `tabuto/fact-reflect`. Installed this way it is
tied to your account and synced to Claude Code; hooks don't run outside Claude
Code, so there use `/extract-fact` and the `mcp` backend.

Requirements: Python 3.8+ (stdlib only), an MCP memory server if you use the
`mcp` destination.

## Privacy

Extraction skips secrets, IDs, account numbers, and sensitive personal data
unless you explicitly ask. Nothing reaches a destination without your approval
in `/reflect`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

---

### In breve (IT)

`/extract-fact` mette in coda i fatti utili della conversazione;
`/reflect` ti mostra la coda e scrive su MemServer (o CLAUDE.md, AGENTS.md,
Copilot) solo quello che approvi. Le righe che iniziano con `ricorda:` vengono
accodate in automatico.

## License

MIT
