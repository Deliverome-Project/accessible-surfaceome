"""Paired significance tests for classifier comparisons on a shared benchmark.

Two classifiers scored on the same proteins give paired binary outcomes
(correct / incorrect per protein), so the comparison is McNemar's: only the
discordant proteins carry information, and under the null each is equally
likely to favour either classifier. SurfaceBench comparisons have a handful of
discordant proteins, far too few for the chi-squared approximation, so this is
the exact (binomial) form.

Stdlib only, so the gist mirrors can carry the same function without a SciPy
dependency.
"""
from __future__ import annotations

from collections.abc import Sequence
from math import comb


def exact_mcnemar(a_correct: Sequence[bool], b_correct: Sequence[bool]) -> tuple[int, int, float]:
    """Exact two-sided McNemar test on paired correctness.

    Returns ``(n_only_a, n_only_b, p)``: the proteins only A got right, the
    proteins only B got right, and the two-sided exact p-value (1.0 when no
    protein is discordant).
    """
    if len(a_correct) != len(b_correct):
        raise ValueError("paired inputs must have the same length")
    only_a = sum(1 for a, b in zip(a_correct, b_correct, strict=True) if a and not b)
    only_b = sum(1 for a, b in zip(a_correct, b_correct, strict=True) if b and not a)
    n = only_a + only_b
    if n == 0:
        return only_a, only_b, 1.0
    tail = sum(comb(n, k) for k in range(min(only_a, only_b) + 1)) / 2**n
    return only_a, only_b, min(1.0, 2 * tail)
