# fact-reflect

A **knowledge queue** for Claude. Conversations produce candidate facts; you
decide which ones become long-term memory, and where they go.

```
conversation ──/reflect (extract + check + queue + you choose)──►  MemServer (MCP)
                                                                     CLAUDE.md / AGENTS.md
                                                                     .github/copilot-instructions.md
```

Inspired by [claude-reflect](https://github.com/BayramAnnakov/claude-reflect),
but the target is pluggable: an MCP memory server, agent files, or Copilot.

## Commands

| Command | What it does |
|---------|--------------|
| `/reflect [focus]` | Extracts durable facts from the current conversation, checks them against memory, queues them, then shows the full queue and applies only what you approve |
| `/reflect --history 7` | Same, also including the last 7 days of Claude Code sessions in this project (`--all-projects` for all) |
| `/reflect --dest copilot` | Proposes a single destination for every item |
| `/reflect --dry-run` | Preview only, queues nothing |
| `/fact-queue` | List, add, edit, drop, purge; show/change destinations |

In `/reflect` you answer in one line: `all`, `1,3`, `2>copilot`,
`4="edited text"`, `-6` (skip), `x7` (delete), `none`.

There are no hooks: nothing is scanned or queued in the background. Facts are
only extracted and queued when you explicitly run `/reflect`.

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
tied to your account and synced to Claude Code; without a persistent local
shell, use the `mcp` backend (see below) so `/reflect` can queue facts on the
MCP server instead of a local file.

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

`/reflect` estrae i fatti utili dalla conversazione corrente (o da N giorni di
sessioni passate con `--history N`), li confronta con quanto già in memoria,
li accoda, poi ti mostra la coda e scrive su MemServer (o CLAUDE.md,
AGENTS.md, Copilot) solo quello che approvi. Nessun hook in background: tutto
parte solo quando lanci `/reflect`.

## License

MIT
