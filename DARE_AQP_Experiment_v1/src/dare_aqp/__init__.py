"""Finite-population audit primitives for the DARE-AQP pilot."""

from .audit import hypergeom_cdf, hypergeom_upper_bound, zero_hit_minimum_sample

__all__ = ["hypergeom_cdf", "hypergeom_upper_bound", "zero_hit_minimum_sample"]
