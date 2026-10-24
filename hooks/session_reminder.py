#!/usr/bin/env python3
"""SessionStart hook: remind about pending facts in the local queue."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


def main():
    try:
        import fq
        cfg = fq.load_config(create=False)
        if cfg["queue"]["backend"] != "file":
            return
        items = fq.read_queue(fq.queue_path(cfg))
        n = sum(1 for i in items if i.get("status") == "pending")
        if n:
            print(f"[fact-reflect] {n} fact(s) pending in the knowledge queue. "
                  f"Mention it briefly to the user only if relevant; they can run /reflect.")
    except Exception:
        pass


if __name__ == "__main__":
    main()
