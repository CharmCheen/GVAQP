import itertools
import random
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "src"))

from dare_aqp.audit import hypergeom_cdf, hypergeom_upper_bound, zero_hit_minimum_sample


class HypergeometricAuditTests(unittest.TestCase):
    def test_full_census_is_exact(self):
        for population in range(1, 12):
            for successes in range(population + 1):
                self.assertEqual(
                    hypergeom_upper_bound(population, population, successes, 0.05),
                    successes,
                )

    def test_no_sample_returns_population(self):
        self.assertEqual(hypergeom_upper_bound(17, 0, 0, 0.05), 17)

    def test_cdf_matches_enumeration(self):
        population, successes, sample = 7, 3, 2
        subsets = list(itertools.combinations(range(population), sample))
        empirical = sum(
            sum(i < successes for i in subset) <= 1 for subset in subsets
        ) / len(subsets)
        self.assertAlmostEqual(hypergeom_cdf(1, population, successes, sample), empirical)

    def test_exhaustive_small_population_coverage(self):
        delta = 0.10
        for population in range(2, 10):
            for sample in range(1, population + 1):
                for successes in range(population + 1):
                    subsets = list(itertools.combinations(range(population), sample))
                    failures = 0
                    for subset in subsets:
                        observed = sum(i < successes for i in subset)
                        bound = hypergeom_upper_bound(population, sample, observed, delta)
                        failures += bound < successes
                    self.assertLessEqual(failures / len(subsets), delta + 1e-12)

    def test_audit_rng_can_be_independent(self):
        seed = 41
        discovery = random.Random(seed + 1).sample(range(30), 5)
        audit_a = random.Random(seed + 2).sample(range(30), 5)
        _ = random.Random(seed + 1).sample(range(30), 10)
        audit_b = random.Random(seed + 2).sample(range(30), 5)
        self.assertEqual(audit_a, audit_b)
        self.assertNotEqual(discovery, audit_a)

    def test_zero_hit_minimum_sample_is_minimal(self):
        population, allowed, delta = 30, 2, 0.05
        n = zero_hit_minimum_sample(population, allowed, delta)
        miss = lambda k: (
            0.0 if k > population - allowed - 1
            else __import__("math").comb(population - allowed - 1, k)
            / __import__("math").comb(population, k)
        )
        self.assertLess(miss(n), delta)
        self.assertGreaterEqual(miss(n - 1), delta)


if __name__ == "__main__":
    unittest.main()
