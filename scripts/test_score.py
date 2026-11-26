import unittest

import verify


class ScoreTest(unittest.TestCase):
    def test_a_position_advantage_cancels(self):
        # same toolchain, and the second build of each round is 4% faster
        rows = [{"speedup": 1.04}, {"speedup": 1 / 1.04}, {"speedup": 1.04}, {"speedup": 1 / 1.04}]
        self.assertAlmostEqual(verify.score(rows), 1.0, places=6)

    def test_a_real_speedup_survives_it(self):
        rows = [{"speedup": 1.25 * 1.04}, {"speedup": 1.25 / 1.04}, {"speedup": 1.25 * 1.04}, {"speedup": 1.25 / 1.04}]
        self.assertAlmostEqual(verify.score(rows), 1.25, places=6)


if __name__ == "__main__":
    unittest.main()
