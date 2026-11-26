import unittest

import verify


class FlagsTest(unittest.TestCase):
    def test_small_change_has_no_flags(self):
        self.assertEqual(verify.flags([{"path": "src/Lean/Meta/WHNF.lean", "added": 40, "deleted": 12}], 52, [], []), [])

    def test_each_flag(self):
        got = verify.flags([{"path": "stage0/stdlib/Lean/X.c", "added": 6000, "deleted": 0},
                            {"path": "blob.bin", "binary": True}], 25000, ["blob.bin"], ["cedar"])
        self.assertEqual(len(got), 5, got)
        got = verify.flags([], 0, [], [], ["CMakeLists.txt"])
        self.assertEqual(len(got), 1, got)

    def test_added_lines_and_download_detection(self):
        patch = "\n".join(["diff --git a/CMakeLists.txt b/CMakeLists.txt", "--- a/CMakeLists.txt", "+++ b/CMakeLists.txt",
                           "@@ -1,0 +2,2 @@", "+  GIT_REPOSITORY https://example.com/blob", "+set(X 1)",
                           "diff --git a/src/Lean/Meta/A.lean b/src/Lean/Meta/A.lean", "+++ b/src/Lean/Meta/A.lean",
                           "+-- see https://lean-lang.org", "+def x := 1"])
        adds = verify.added_lines(patch)
        self.assertEqual(sorted(adds), ["CMakeLists.txt", "src/Lean/Meta/A.lean"])
        hits = [p for p, ls in adds.items() if verify.BUILD_FILE.search(p) and any(verify.DOWNLOAD.search(l) for l in ls)]
        self.assertEqual(hits, ["CMakeLists.txt"])


if __name__ == "__main__":
    unittest.main()
