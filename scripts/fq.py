#!/usr/bin/env python3
"""fact-reflect queue manager.

Stdlib only. Manages the local knowledge queue (JSONL), the destination
config, and writes approved facts into agent files (CLAUDE.md, AGENTS.md,
.github/copilot-instructions.md, ...). MCP destinations are written by
Claude itself through the MCP tools; this script only records the outcome.

Usage: python3 fq.py <command> [options]   (run with -h for details)
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid

HOME = os.path.expanduser(os.environ.get("FACT_REFLECT_HOME", "~/.fact-reflect"))
CONFIG_PATH = os.path.join(HOME, "config.json")

SECTION_START = "<!-- fact-reflect:start -->"
SECTION_END = "<!-- fact-reflect:end -->"

CATEGORIES = [
    "preference",   # how the user wants things done / tastes
    "project",      # projects, goals, status, decisions on a project
    "person",       # people and relationships
    "decision",     # a choice the user made
    "convention",   # coding/project conventions, tooling rules
    "correction",   # "no, use X not Y" — behavioural rule for the agent
    "fact",         # anything else durable about the user's world
]
STATUSES = ["pending", "applied", "skipped"]

DEFAULT_CONFIG = {
    "version": 1,
    "queue": {
        # "file": local JSONL (Claude Code, desktop). "mcp": pending items
        # live as tasks on the MCP server (works from claude.ai / phone).
        "backend": "file",
        "path": os.path.join(HOME, "queue.jsonl"),
        "mcp": {
            "server": "mcp-memory",
            "add_tool": "add_task",
            "list_tool": "list_tasks",
            "remove_tool": "delete_task",
            "section": "fact-queue",
        },
    },
    "default_destination": "memserver",
    "destinations": {
        "memserver": {
            "type": "mcp",
            "server": "mcp-memory",
            "batch_tool": "remember_facts",
            "single_tool": "remember_fact",
            "search_tool": "recall",
            "base_tags": ["fact-reflect"],
            "description": "MemServer knowledge graph (long-term personal memory)",
        },
        "claude-global": {
            "type": "agent-file",
            "path": "~/.claude/CLAUDE.md",
            "heading": "Learned rules (fact-reflect)",
            "description": "Global Claude Code instructions",
        },
        "claude-project": {
            "type": "agent-file",
            "path": "./CLAUDE.md",
            "heading": "Learned rules (fact-reflect)",
            "description": "Claude Code instructions for the current repo",
        },
        "agents": {
            "type": "agent-file",
            "path": "./AGENTS.md",
            "heading": "Learned rules (fact-reflect)",
            "description": "AGENTS.md (Codex, Cursor, Copilot agent, ...)",
        },
        "copilot": {
            "type": "copilot",
            "path": "./.github/copilot-instructions.md",
            "heading": "Learned rules (fact-reflect)",
            "description": "GitHub Copilot repository instructions",
        },
    },
    # Category -> suggested destination. Anything missing falls back to
    # default_destination. Project-scoped conventions go to the repo file.
    "routing": {
        "preference": "memserver",
        "project": "memserver",
        "person": "memserver",
        "decision": "memserver",
        "fact": "memserver",
        "correction": "claude-global",
        "convention": "claude-project",
    },
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def die(msg, code=1):
    print(f"fact-reflect: {msg}", file=sys.stderr)
    sys.exit(code)


def deep_merge(base, override):
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def atomic_write(path, text):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".fr-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_config(create=True):
    if not os.path.exists(CONFIG_PATH):
        if not create:
            return json.loads(json.dumps(DEFAULT_CONFIG))
        atomic_write(CONFIG_PATH, json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n")
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            user = json.load(fh)
    except json.JSONDecodeError as e:
        die(f"invalid config {CONFIG_PATH}: {e}")
    return deep_merge(DEFAULT_CONFIG, user)


def queue_path(cfg):
    return os.path.expanduser(cfg["queue"]["path"])


def read_queue(path):
    items = []
    if not os.path.exists(path):
        return items
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"fact-reflect: skipping corrupt line {n} in {path}", file=sys.stderr)
    return items


def write_queue(path, items):
    text = "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items)
    atomic_write(path, text)


_WORD = re.compile(r"[\w']+", re.UNICODE)


def normalize(text):
    return " ".join(_WORD.findall(text.lower()))


def fingerprint(text):
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()[:12]


def jaccard(a, b):
    ta, tb = set(normalize(a).split()), set(normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def new_id():
    return "f-" + uuid.uuid4().hex[:8]


def suggest_destination(cfg, item):
    if item.get("destination") and item["destination"] in cfg["destinations"]:
        return item["destination"]
    cat = item.get("category", "fact")
    dest = cfg.get("routing", {}).get(cat) or cfg["default_destination"]
    return dest if dest in cfg["destinations"] else cfg["default_destination"]


def normalize_item(cfg, raw):
    if isinstance(raw, str):
        raw = {"text": raw}
    text = (raw.get("text") or "").strip()
    if not text:
        raise ValueError("item without text")
    cat = raw.get("category", "fact")
    if cat not in CATEGORIES:
        cat = "fact"
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        conf = float(raw.get("confidence", 0.75))
    except (TypeError, ValueError):
        conf = 0.75
    item = {
        "id": raw.get("id") or new_id(),
        "text": text,
        "category": cat,
        "tags": sorted(set(tags)),
        "scope": raw.get("scope", "global"),
        "project": raw.get("project") or os.path.basename(os.getcwd()),
        "source": raw.get("source", "manual"),
        "evidence": (raw.get("evidence") or "")[:300],
        "confidence": max(0.0, min(1.0, conf)),
        "status": "pending",
        "created_at": raw.get("created_at") or now_iso(),
        "fingerprint": fingerprint(text),
    }
    item["destination"] = suggest_destination(cfg, {**raw, "category": cat})
    return item


def find(items, ids):
    want = set(ids)
    found = [i for i in items if i["id"] in want]
    missing = want - {i["id"] for i in found}
    if missing:
        die("unknown id(s): " + ", ".join(sorted(missing)))
    return found


def print_table(items):
    if not items:
        print("(queue empty)")
        return
    for i in items:
        flag = f"[{i['status']}]" if i["status"] != "pending" else ""
        print(f"{i['id']}  {i['category']:<10} -> {i.get('destination','?'):<14} "
              f"({i.get('confidence',0):.2f}) {flag} {i['text']}")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_init(args):
    existed = os.path.exists(CONFIG_PATH)
    cfg = load_config()
    qp = queue_path(cfg)
    if not os.path.exists(qp):
        atomic_write(qp, "")
    print(json.dumps({
        "home": HOME,
        "config": CONFIG_PATH,
        "config_created": not existed,
        "queue": qp,
        "backend": cfg["queue"]["backend"],
    }, indent=2))


def cmd_config(args):
    cfg = load_config()
    if args.action == "show":
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
    elif args.action == "path":
        print(CONFIG_PATH)
    elif args.action == "get":
        node = cfg
        for part in args.key.split("."):
            if not isinstance(node, dict) or part not in node:
                die(f"no such key: {args.key}")
            node = node[part]
        print(json.dumps(node, indent=2, ensure_ascii=False))
    elif args.action == "set":
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            user = json.load(fh)
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        node = user
        parts = args.key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        atomic_write(CONFIG_PATH, json.dumps(user, indent=2, ensure_ascii=False) + "\n")
        print(f"set {args.key} = {json.dumps(value, ensure_ascii=False)}")
    elif args.action == "destinations":
        out = {k: {"type": v["type"], "target": v.get("path") or v.get("server"),
                   "description": v.get("description", "")}
               for k, v in cfg["destinations"].items()}
        print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_add(args):
    cfg = load_config()
    qp = queue_path(cfg)
    if args.text:
        payload = [{"text": args.text, "category": args.category or "fact",
                    "tags": args.tags or [], "source": args.source or "manual",
                    "confidence": args.confidence if args.confidence is not None else 0.9,
                    "destination": args.destination}]
    else:
        raw = args.json if args.json is not None else sys.stdin.read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            die(f"invalid JSON input: {e}")
        if isinstance(payload, dict):
            payload = [payload]
    items = read_queue(qp)
    added, skipped = [], []
    for raw in payload:
        try:
            item = normalize_item(cfg, raw)
        except ValueError as e:
            skipped.append({"text": str(raw)[:80], "reason": str(e)})
            continue
        dup = next((i for i in items if i["fingerprint"] == item["fingerprint"]), None)
        if dup is None:
            dup = next((i for i in items if i["status"] == "pending"
                        and jaccard(i["text"], item["text"]) >= args.similarity), None)
        if dup is not None:
            skipped.append({"text": item["text"], "reason": f"duplicate of {dup['id']} ({dup['status']})"})
            continue
        items.append(item)
        added.append({"id": item["id"], "text": item["text"], "destination": item["destination"]})
    if added:
        write_queue(qp, items)
    print(json.dumps({"added": added, "skipped": skipped,
                      "pending": sum(1 for i in items if i["status"] == "pending")},
                     indent=2, ensure_ascii=False))


def cmd_list(args):
    cfg = load_config()
    items = read_queue(queue_path(cfg))
    if args.status != "all":
        items = [i for i in items if i["status"] == args.status]
    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
    else:
        print_table(items)


def cmd_stats(args):
    cfg = load_config(create=False)
    items = read_queue(queue_path(cfg))
    out = {s: sum(1 for i in items if i["status"] == s) for s in STATUSES}
    out["backend"] = cfg["queue"]["backend"]
    print(json.dumps(out))


def cmd_update(args):
    cfg = load_config()
    qp = queue_path(cfg)
    items = read_queue(qp)
    (item,) = find(items, [args.id])
    if args.text:
        item["text"] = args.text.strip()
        item["fingerprint"] = fingerprint(item["text"])
    if args.category:
        if args.category not in CATEGORIES:
            die(f"category must be one of {CATEGORIES}")
        item["category"] = args.category
    if args.tags is not None:
        item["tags"] = sorted(set(args.tags))
    if args.destination:
        if args.destination not in cfg["destinations"]:
            die(f"unknown destination {args.destination}")
        item["destination"] = args.destination
    if args.scope:
        item["scope"] = args.scope
    item["updated_at"] = now_iso()
    write_queue(qp, items)
    print(json.dumps(item, indent=2, ensure_ascii=False))


def cmd_mark(args):
    cfg = load_config()
    qp = queue_path(cfg)
    items = read_queue(qp)
    for item in find(items, args.ids):
        item["status"] = args.status
        item["updated_at"] = now_iso()
        if args.status == "applied":
            item["applied_to"] = args.destination or item.get("destination")
            item["applied_at"] = now_iso()
    write_queue(qp, items)
    print(json.dumps({"marked": args.ids, "status": args.status}))


def cmd_drop(args):
    cfg = load_config()
    qp = queue_path(cfg)
    items = read_queue(qp)
    find(items, args.ids)
    items = [i for i in items if i["id"] not in set(args.ids)]
    write_queue(qp, items)
    print(json.dumps({"dropped": args.ids}))


def cmd_purge(args):
    cfg = load_config()
    qp = queue_path(cfg)
    items = read_queue(qp)
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=args.older_than)
    keep, removed = [], 0
    for i in items:
        ts = i.get("updated_at") or i.get("created_at")
        try:
            old = _dt.datetime.fromisoformat(ts) <= cutoff
        except (TypeError, ValueError):
            old = True
        if i["status"] != "pending" and old:
            removed += 1
        else:
            keep.append(i)
    write_queue(qp, keep)
    print(json.dumps({"removed": removed, "remaining": len(keep)}))


def _render_section(heading, bullets):
    body = "\n".join(f"- {b}" for b in bullets)
    return f"{SECTION_START}\n## {heading}\n\n{body}\n{SECTION_END}"


def write_bullets(path, heading, new_bullets):
    """Merge bullets into the managed section of a markdown file.

    Returns (written, duplicates)."""
    path = os.path.expanduser(path)
    content = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    pattern = re.compile(re.escape(SECTION_START) + r"(.*?)" + re.escape(SECTION_END), re.S)
    m = pattern.search(content)
    existing = []
    if m:
        for line in m.group(1).splitlines():
            line = line.strip()
            if line.startswith("- "):
                existing.append(line[2:].strip())
    written, dups = [], []
    for b in new_bullets:
        b = " ".join(b.split())
        if any(fingerprint(b) == fingerprint(e) or jaccard(b, e) >= 0.85 for e in existing + written):
            dups.append(b)
        else:
            written.append(b)
    if not written:
        return written, dups
    section = _render_section(heading, existing + written)
    if m:
        content = content[:m.start()] + section + content[m.end():]
    else:
        content = (content.rstrip("\n") + "\n\n" if content.strip() else "") + section + "\n"
    atomic_write(path, content)
    return written, dups


def cmd_write(args):
    cfg = load_config()
    qp = queue_path(cfg)
    items = read_queue(qp)
    dest = cfg["destinations"].get(args.destination)
    if not dest:
        die(f"unknown destination {args.destination}")
    if dest["type"] not in ("agent-file", "copilot"):
        die(f"destination {args.destination} is type {dest['type']}: write it via MCP, then use `mark`")
    path = args.path or dest["path"]
    heading = dest.get("heading", "Learned rules (fact-reflect)")
    selected = find(items, args.ids)
    written, dups = write_bullets(path, heading, [i["text"] for i in selected])
    for i in selected:
        i["status"] = "applied"
        i["applied_to"] = args.destination
        i["applied_at"] = i["updated_at"] = now_iso()
    write_queue(qp, items)
    print(json.dumps({"file": os.path.abspath(os.path.expanduser(path)),
                      "written": written, "already_present": dups},
                     indent=2, ensure_ascii=False))


def cmd_export_mcp(args):
    """Print the payload for an MCP batch save (remember_facts)."""
    cfg = load_config()
    items = find(read_queue(queue_path(cfg)), args.ids)
    dest = cfg["destinations"].get(args.destination)
    if not dest or dest["type"] != "mcp":
        die(f"{args.destination} is not an mcp destination")
    base = dest.get("base_tags", [])
    facts = [{"text": i["text"],
              "tags": sorted(set(base + i.get("tags", []) + [i["category"]]))}
             for i in items]
    print(json.dumps({"server": dest["server"], "tool": dest.get("batch_tool"),
                      "facts": facts}, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="fq.py", description="fact-reflect knowledge queue")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create config and queue if missing").set_defaults(fn=cmd_init)

    c = sub.add_parser("config", help="show/get/set config")
    c.add_argument("action", choices=["show", "path", "get", "set", "destinations"])
    c.add_argument("key", nargs="?")
    c.add_argument("value", nargs="?")
    c.set_defaults(fn=cmd_config)

    a = sub.add_parser("add", help="add facts (JSON on stdin/--json, or --text)")
    a.add_argument("--json")
    a.add_argument("--text")
    a.add_argument("--category", choices=CATEGORIES)
    a.add_argument("--tags", nargs="*")
    a.add_argument("--source")
    a.add_argument("--destination")
    a.add_argument("--confidence", type=float)
    a.add_argument("--similarity", type=float, default=0.8,
                   help="Jaccard threshold for near-duplicates (default 0.8)")
    a.set_defaults(fn=cmd_add)

    l = sub.add_parser("list", help="list queue")
    l.add_argument("--status", default="pending", choices=STATUSES + ["all"])
    l.add_argument("--json", action="store_true")
    l.set_defaults(fn=cmd_list)

    sub.add_parser("stats", help="counts by status").set_defaults(fn=cmd_stats)

    u = sub.add_parser("update", help="edit one item")
    u.add_argument("id")
    u.add_argument("--text")
    u.add_argument("--category")
    u.add_argument("--tags", nargs="*")
    u.add_argument("--destination")
    u.add_argument("--scope", choices=["global", "project"])
    u.set_defaults(fn=cmd_update)

    m = sub.add_parser("mark", help="set status of items")
    m.add_argument("ids", nargs="+")
    m.add_argument("--status", required=True, choices=STATUSES)
    m.add_argument("--destination")
    m.set_defaults(fn=cmd_mark)

    d = sub.add_parser("drop", help="delete items from the queue")
    d.add_argument("ids", nargs="+")
    d.set_defaults(fn=cmd_drop)

    pg = sub.add_parser("purge", help="remove applied/skipped items")
    pg.add_argument("--older-than", type=int, default=0, help="days (default 0 = all)")
    pg.set_defaults(fn=cmd_purge)

    w = sub.add_parser("write", help="write items into an agent/copilot file and mark applied")
    w.add_argument("destination")
    w.add_argument("ids", nargs="+")
    w.add_argument("--path", help="override destination path")
    w.set_defaults(fn=cmd_write)

    e = sub.add_parser("export-mcp", help="print remember_facts payload for items")
    e.add_argument("destination")
    e.add_argument("ids", nargs="+")
    e.set_defaults(fn=cmd_export_mcp)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
