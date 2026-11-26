import unittest

import verify


class FlagsTest(unittest.TestCase):
    def test_small_change_has_no_flags(self):
        self.assertEqual(verify.flags([{"path": "src/Lean/Meta/WHNF.lean", "added": 40, "deleted": 12}], 52, [], []), [])

    def test_each_flag(self):
        got = verify.flags([{"path": "stage0/stdlib/Lean/X.c", "added": 6000, "deleted": 0},
                            {"path": "blob.bin", "binary": True}], 25000, ["blob.bin"], ["cedar"])
        self.assertEqual(len(got), 5, got)


if __name__ == "__main__":
    unittest.main()
