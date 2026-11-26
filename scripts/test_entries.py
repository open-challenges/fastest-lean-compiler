import json
import os
import tempfile
import unittest

import entries

SHA = "a" * 40
GOOD = f"""---
spec: submission.md/v1
title: Faster defeq cache
author: someone
date: 2026-12-01
code: https://github.com/someone/lean4/tree/{SHA}
agent:
  model: Claude
  harness: Claude Code
---
text
"""


class EntriesTest(unittest.TestCase):
    def test_parse(self):
        e = entries.parse("someone", GOOD)
        self.assertEqual((e.commit, e.short_code, e.authors), (SHA, "someone/lean4@aaaaaaa", ["someone"]))

    def test_commit_url_forms(self):
        for code in (f"https://github.com/x/lean4/commit/{SHA}", f"https://github.com/x/lean4/tree/{SHA}/"):
            self.assertEqual(entries.parse("x", GOOD.replace(f"https://github.com/someone/lean4/tree/{SHA}", code)).commit, SHA)
        for bad in ("https://github.com/x/lean4/tree/main", f"https://github.com/x/lean4/tree/{SHA}/src", "stock"):
            with self.assertRaises(entries.EntryError):
                entries.parse("x", GOOD.replace(f"https://github.com/someone/lean4/tree/{SHA}", bad))

    def test_verdict_counts_only_for_its_commit(self):
        root = tempfile.mkdtemp()
        d = os.path.join(root, "submissions", "someone")
        os.makedirs(d)
        open(os.path.join(d, "SUBMISSION.md"), "w").write(GOOD)
        json.dump({"ok": True, "speedup": 1.3, "commit": "b" * 40}, open(os.path.join(d, "verdict.json"), "w"))
        self.assertEqual(entries.standings(entries.load(root)), [])
        json.dump({"ok": True, "speedup": 1.3, "commit": SHA}, open(os.path.join(d, "verdict.json"), "w"))
        rows = entries.standings(entries.load(root))
        self.assertEqual([r.speedup for r in rows], [1.3])
        self.assertTrue(entries.is_record(1.33, rows))
        self.assertFalse(entries.is_record(1.32, rows))

    def test_first_record_must_beat_stock_by_the_margin(self):
        self.assertFalse(entries.is_record(1.01, []))
        self.assertTrue(entries.is_record(1.02, []))


if __name__ == "__main__":
    unittest.main()
