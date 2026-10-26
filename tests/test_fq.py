import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FQ = os.path.join(ROOT, "scripts", "fq.py")


class FactQueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, FACT_REFLECT_HOME=os.path.join(self.tmp.name, "home"))
        self.cwd = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.cwd)

    def tearDown(self):
        self.tmp.cleanup()

    def fq(self, *args, stdin=None):
        r = subprocess.run([sys.executable, FQ, *args], input=stdin, capture_output=True,
                           text=True, env=self.env, cwd=self.cwd)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def add(self, items):
        return json.loads(self.fq("add", stdin=json.dumps(items)))

    def test_add_dedup_and_routing(self):
        out = self.add([
            {"text": "Alex deploys demo-app on Render", "category": "project"},
            {"text": "Always use pnpm instead of npm", "category": "correction"},
            {"text": "alex deploys demo-app on render!", "category": "project"},
        ])
        self.assertEqual(len(out["added"]), 2)
        self.assertEqual(len(out["skipped"]), 1)
        dests = {a["text"]: a["destination"] for a in out["added"]}
        self.assertEqual(dests["Always use pnpm instead of npm"], "claude-global")
        self.assertEqual(dests["Alex deploys demo-app on Render"], "memserver")

    def test_write_agent_file_is_idempotent(self):
        out = self.add([{"text": "Run tests with pytest -q", "category": "convention"}])
        fid = out["added"][0]["id"]
        target = os.path.join(self.cwd, "AGENTS.md")
        with open(target, "w") as fh:
            fh.write("# Agents\n\nExisting content.\n")
        self.fq("write", "agents", fid)
        with open(target) as fh:
            text = fh.read()
        self.assertIn("Existing content.", text)
        self.assertIn("- Run tests with pytest -q", text)
        self.assertEqual(text.count("fact-reflect:start"), 1)
        pending = json.loads(self.fq("list", "--json"))
        self.assertEqual(pending, [])
        # second item with same meaning is not duplicated in the file
        out = self.add([{"text": "run tests with pytest -q.", "category": "convention", "id": "f-x"}])
        # exact fingerprint already in queue (applied) -> skipped at queue level
        self.assertEqual(out["added"], [])

    def test_copilot_creates_dirs_and_mark_mcp(self):
        out = self.add([{"text": "Use OnPush change detection in Angular components",
                         "category": "convention", "destination": "copilot"},
                        {"text": "Alex lives in Springfield", "category": "fact"}])
        ids = {a["destination"]: a["id"] for a in out["added"]}
        self.fq("write", "copilot", ids["copilot"])
        self.assertTrue(os.path.exists(os.path.join(self.cwd, ".github", "copilot-instructions.md")))
        payload = json.loads(self.fq("export-mcp", "memserver", ids["memserver"]))
        self.assertEqual(payload["tool"], "remember_facts")
        self.assertIn("fact-reflect", payload["facts"][0]["tags"])
        self.fq("mark", ids["memserver"], "--status", "applied", "--destination", "memserver")
        stats = json.loads(self.fq("stats"))
        self.assertEqual(stats["applied"], 2)
        self.assertEqual(stats["pending"], 0)
        purged = json.loads(self.fq("purge"))
        self.assertEqual(purged["removed"], 2)


if __name__ == "__main__":
    unittest.main()
