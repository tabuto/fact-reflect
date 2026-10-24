#!/usr/bin/env python3
"""UserPromptSubmit hook: queue explicit markers without spending tokens.

Lines like "ricorda: ...", "remember: ...", "memorizza: ...", "nota: ..."
are added to the queue with high confidence. Everything else is left to
/extract-fact. Never blocks the prompt; failures are silent.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

MARKER = re.compile(r"^\s*(?:ricorda|ricordati|memorizza|remember|nota bene|fact)\s*:\s*(.{5,})$",
                    re.IGNORECASE | re.MULTILINE)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    prompt = data.get("prompt") or ""
    found = [m.group(1).strip() for m in MARKER.finditer(prompt)]
    if not found:
        return
    try:
        import fq
        cfg = fq.load_config()
        if cfg["queue"]["backend"] != "file":
            # MCP-backed queue: let Claude queue it through the skill.
            print("[fact-reflect] explicit fact marker detected: queue it with the fact-capture skill.")
            return
        qp = fq.queue_path(cfg)
        items = fq.read_queue(qp)
        project = os.path.basename(data.get("cwd") or os.getcwd())
        added = []
        for text in found:
            item = fq.normalize_item(cfg, {"text": text, "confidence": 0.95,
                                           "source": f"hook:marker:{data.get('session_id','')}",
                                           "project": project})
            if any(i["fingerprint"] == item["fingerprint"] for i in items):
                continue
            items.append(item)
            added.append(item["id"])
        if added:
            fq.write_queue(qp, items)
            # stdout of UserPromptSubmit is added to Claude's context
            print(f"[fact-reflect] queued {len(added)} fact(s) for review ({', '.join(added)}). "
                  f"Do not save them elsewhere; the user will review them with /reflect.")
    except Exception as e:  # never break the user's prompt
        print(f"[fact-reflect] marker capture failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
