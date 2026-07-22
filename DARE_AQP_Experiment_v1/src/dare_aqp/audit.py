"""Exact fixed-stage finite-population bounds.

The population contains ``population_size`` binary residual-anchor indicators.
A simple random sample without replacement observes ``observed_successes`` in
``sample_size`` units.  ``hypergeom_upper_bound`` inverts the lower tail to
return a one-sided (1-delta) upper confidence bound on the total number of
successes before the audit sample.
"""

from functools import lru_cache
from math import comb


def hypergeom_cdf(
    observed_successes: int,
    population_size: int,
    population_successes: int,
    sample_size: int,
) -> float:
    """Return P[X <= observed_successes] for a hypergeometric variable."""
    if not 0 <= population_successes <= population_size:
        raise ValueError("population_successes outside population")
    if not 0 <= sample_size <= population_size:
        raise ValueError("sample_size outside population")
    if observed_successes < 0:
        return 0.0
    max_x = min(sample_size, population_successes)
    if observed_successes >= max_x:
        return 1.0
    min_x = max(0, sample_size - (population_size - population_successes))
    if observed_successes < min_x:
        return 0.0
    numerator = sum(
        comb(population_successes, x)
        * comb(population_size - population_successes, sample_size - x)
        for x in range(min_x, min(observed_successes, max_x) + 1)
    )
    return numerator / comb(population_size, sample_size)


@lru_cache(maxsize=None)
def hypergeom_upper_bound(
    population_size: int,
    sample_size: int,
    observed_successes: int,
    delta: float,
) -> int:
    """Exact one-sided upper bound on total successes.

    The returned largest M satisfies ``P_M(X <= x) >= delta``.  Values above
    it would make the observation fall in a lower-tail rejection region of
    size at most ``delta``.
    """
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must lie in (0, 1)")
    if not 0 <= sample_size <= population_size:
        raise ValueError("sample_size outside population")
    if not 0 <= observed_successes <= sample_size:
        raise ValueError("observed_successes outside sample")
    if sample_size == 0:
        return population_size
    lower = observed_successes
    upper = population_size - sample_size + observed_successes
    accepted = lower
    for total in range(lower, upper + 1):
        if hypergeom_cdf(
            observed_successes, population_size, total, sample_size
        ) + 1e-15 >= delta:
            accepted = total
        else:
            break
    return accepted


def zero_hit_minimum_sample(population_size: int, allowed_successes: int, delta: float) -> int:
    """Minimum SRSWOR size whose zero-hit outcome rejects ``allowed+1``.

    Returns the smallest n such that
    C(N-allowed-1, n) / C(N, n) < delta.  This is a design diagnostic, not a
    claim that a zero-hit outcome will occur for the true population.
    """
    if not 0 <= allowed_successes < population_size:
        raise ValueError("allowed_successes must lie in [0, population_size)")
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must lie in (0, 1)")
    failures = allowed_successes + 1
    for sample_size in range(population_size + 1):
        if sample_size > population_size - failures:
            miss_probability = 0.0
        else:
            miss_probability = (
                comb(population_size - failures, sample_size)
                / comb(population_size, sample_size)
            )
        if miss_probability < delta:
            return sample_size
    return population_size
