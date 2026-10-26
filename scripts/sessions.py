#!/usr/bin/env python3
"""Dump recent Claude Code sessions as compact text for fact extraction.

Claude Code stores transcripts as JSONL under ~/.claude/projects/<slug>/.
This prints the user/assistant text of sessions modified in the last N days,
skipping tool calls and sessions already processed by /reflect.

  python3 sessions.py --days 7 [--project PATH | --all-projects]
                      [--include-processed] [--max-chars 60000]
  python3 sessions.py --mark-processed ID [ID ...]
"""
import argparse
import json
import os
import sys
import time

PROJECTS = os.path.expanduser(os.environ.get("CLAUDE_PROJECTS_DIR", "~/.claude/projects"))
HOME = os.path.expanduser(os.environ.get("FACT_REFLECT_HOME", "~/.fact-reflect"))
PROCESSED = os.path.join(HOME, "processed_sessions.json")


def load_processed():
    try:
        with open(PROCESSED, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save_processed(data):
    os.makedirs(HOME, exist_ok=True)
    tmp = PROCESSED + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, PROCESSED)


def project_slug(path):
    # Claude Code replaces path separators (and dots) with '-'
    return os.path.abspath(path).replace(os.sep, "-").replace(".", "-")


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def session_text(path, per_msg=1500):
    lines = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if rec.get("type") not in ("user", "assistant") or rec.get("isMeta"):
                continue
            msg = rec.get("message") or {}
            txt = text_of(msg.get("content")).strip()
            if not txt or txt.startswith("<command-") or txt.startswith("<local-command"):
                continue
            role = "U" if rec["type"] == "user" else "A"
            if len(txt) > per_msg:
                txt = txt[:per_msg] + " […]"
            lines.append(f"{role}: {txt}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--project", default=os.getcwd())
    p.add_argument("--all-projects", action="store_true")
    p.add_argument("--include-processed", action="store_true")
    p.add_argument("--max-chars", type=int, default=60000)
    p.add_argument("--list", action="store_true", help="only list matching sessions")
    p.add_argument("--mark-processed", nargs="+", metavar="SESSION_ID")
    a = p.parse_args()

    processed = load_processed()
    if a.mark_processed:
        for sid in a.mark_processed:
            processed[sid] = int(time.time())
        save_processed(processed)
        print(json.dumps({"marked": a.mark_processed}))
        return

    if not os.path.isdir(PROJECTS):
        print(json.dumps({"error": f"no Claude Code sessions found in {PROJECTS}"}))
        return
    dirs = [os.path.join(PROJECTS, d) for d in os.listdir(PROJECTS)] if a.all_projects \
        else [os.path.join(PROJECTS, project_slug(a.project))]
    cutoff = time.time() - a.days * 86400
    sessions = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".jsonl"):
                continue
            fp = os.path.join(d, f)
            mt = os.path.getmtime(fp)
            sid = f[:-6]
            if mt < cutoff or (sid in processed and not a.include_processed):
                continue
            sessions.append((mt, sid, fp, os.path.basename(d)))
    sessions.sort(reverse=True)

    if a.list:
        print(json.dumps([{"session": s, "project": pr,
                           "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(mt))}
                          for mt, s, _, pr in sessions], indent=2))
        return

    budget, used = a.max_chars, []
    out = []
    for mt, sid, fp, pr in sessions:
        body = session_text(fp)
        if not body:
            continue
        chunk = f"=== session {sid} | {pr} | {time.strftime('%Y-%m-%d', time.localtime(mt))} ===\n{body}\n"
        if budget - len(chunk) < 0 and used:
            break
        out.append(chunk[:budget])
        budget -= len(chunk)
        used.append(sid)
    sys.stdout.write("".join(out) or "(no unprocessed sessions in range)\n")
    sys.stdout.write(f"\n### SESSIONS_INCLUDED: {' '.join(used)}\n")


if __name__ == "__main__":
    main()
