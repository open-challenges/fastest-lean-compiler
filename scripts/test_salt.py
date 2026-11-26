import os
import tempfile
import unittest

import salt


def tree(files: dict[str, str]) -> str:
    d = tempfile.mkdtemp()
    for path, text in files.items():
        p = os.path.join(d, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)
    return d


class SaltTest(unittest.TestCase):
    FILES = {"A.lean": "theorem a : True := trivial", "Sub/B.lean": "-- ends in a comment",
             "lakefile.lean": "import Lake", ".lake/build/ir/X.lean": "x", ".lake/packages/p/P.lean": "def p := 1",
             ".git/x.lean": "x", "Pre.lean": "prelude\ninductive T", "notes.md": "no"}

    def test_salts_sources_and_packages_only(self):
        d = tree(self.FILES)
        self.assertEqual(salt.salt_tree(d, 1), 3)
        for path in ("A.lean", "Sub/B.lean", ".lake/packages/p/P.lean"):
            self.assertIn("theorem flcSalt_", open(os.path.join(d, path)).read(), path)
        for path in ("lakefile.lean", ".lake/build/ir/X.lean", ".git/x.lean", "Pre.lean", "notes.md"):
            self.assertNotIn("flcSalt", open(os.path.join(d, path)).read(), path)

    def test_salt_starts_on_a_fresh_line(self):
        d = tree(self.FILES)
        salt.salt_tree(d, 1)
        text = open(os.path.join(d, "Sub/B.lean")).read()
        self.assertTrue(text.startswith("-- ends in a comment\n\n"))

    def test_same_seed_same_salt_and_sums_are_right(self):
        a, b, c = tree(self.FILES), tree(self.FILES), tree(self.FILES)
        salt.salt_tree(a, 5), salt.salt_tree(b, 5), salt.salt_tree(c, 6)
        ta, tb, tc = (open(os.path.join(x, "A.lean")).read() for x in (a, b, c))
        self.assertEqual(ta, tb)
        self.assertNotEqual(ta, tc)
        import re
        m = re.search(r"Nat\.add (\d+) (\d+) = (\d+)", ta)
        self.assertEqual(int(m.group(1)) + int(m.group(2)), int(m.group(3)))


if __name__ == "__main__":
    unittest.main()
