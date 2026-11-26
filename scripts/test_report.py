import unittest

import entries
import report


def verdict(speedup=1.3, flags=()):
    row = {"round": 1, "first": "stock", "same_theorems": True, "speedup": speedup,
           "stock": {"seconds": 600.0}, "entry": {"seconds": 600.0 / speedup}}
    return {"ok": True, "speedup": speedup, "stock_seconds": 600.0, "entry_seconds": 600.0 / speedup,
            "theorems": 12345, "base": "v4.36.0", "rounds": [row],
            "diff": {"files": 2, "added": 10, "deleted": 3, "largest": [], "flags": list(flags)}}


class DecideTest(unittest.TestCase):
    ENTRY = {"ok": True, "folder": "someone"}

    def test_record_merges(self):
        d, lines = report.decide(verdict(1.3), self.ENTRY, [])
        self.assertEqual((d["merge"], d["record"]), (True, True))
        self.assertIn("record", d["labels"])

    def test_flagged_record_waits(self):
        d, lines = report.decide(verdict(1.3, ["changes 1 binary file(s): x.bin"]), self.ENTRY, [])
        self.assertEqual((d["merge"], d["record"]), (False, True))
        self.assertIn("needs-review", d["labels"])

    def test_noise_is_not_a_record(self):
        d, _ = report.decide(verdict(1.01), self.ENTRY, [])
        self.assertEqual((d["merge"], d["record"]), (False, False))

    def test_different_theorems_fail(self):
        v = {"ok": False, "stage": "compare", "error": "the entry's theorems differ from stock Lean's",
             "difference": {"line": 7, "stock": "a", "entry": "b"}}
        d, lines = report.decide(v, self.ENTRY, [])
        self.assertEqual(d["labels"], ["failed"])
        self.assertIn("line 7", "\n".join(lines))

    def test_stock_failure_is_the_judges(self):
        d, _ = report.decide({"ok": False, "stage": "stock", "error": "x"}, self.ENTRY, [])
        self.assertEqual(d["labels"], ["judge-problem"])

    def test_invalid_entry(self):
        d, _ = report.decide({}, {"ok": False, "error": "nope"}, [])
        self.assertEqual(d["labels"], ["invalid"])


if __name__ == "__main__":
    unittest.main()
