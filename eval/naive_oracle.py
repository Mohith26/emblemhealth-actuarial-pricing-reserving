"""Independent naive chain-ladder oracle (Validation B).

Deliberately written with plain Python loops and lists -- no numpy, no code
shared with ratecraft.reserving -- so it is an independent implementation to
cross-check the vectorized engine.  Max deviation between the two is a
reported metric.
"""

from typing import List, Optional, Tuple


def naive_chain_ladder(tri: List[List[Optional[float]]], tail: float = 1.0
                       ) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Chain-ladder via loops.  ``tri`` is a list of rows; unobserved cells are None.

    Returns (factors, cdfs, ultimates, ibnr).
    """
    n_o = len(tri)
    n_d = max(len(r) for r in tri) if n_o else 0

    def cell(i, j):
        row = tri[i]
        if j < len(row):
            return row[j]
        return None

    factors: List[float] = []
    for j in range(n_d - 1):
        num = 0.0
        den = 0.0
        for i in range(n_o):
            a = cell(i, j)
            b = cell(i, j + 1)
            if a is not None and b is not None:
                den += a
                num += b
        factors.append(num / den if den > 0 else 1.0)

    cdf = [0.0] * n_d
    if n_d:
        cdf[n_d - 1] = tail
        for j in range(n_d - 2, -1, -1):
            cdf[j] = cdf[j + 1] * factors[j]

    ultimates: List[float] = []
    ibnr: List[float] = []
    for i in range(n_o):
        latest = 0.0
        age = 0
        for j in range(n_d):
            v = cell(i, j)
            if v is not None:
                latest = v
                age = j
        ult = latest * cdf[age] if n_d else latest
        ultimates.append(ult)
        ibnr.append(ult - latest)
    return factors, cdf, ultimates, ibnr


def triangle_to_lists(tri) -> List[List[Optional[float]]]:
    """Convert a numpy triangle with NaNs to the oracle's list-of-lists form."""
    out: List[List[Optional[float]]] = []
    for row in tri:
        out.append([None if v != v else float(v) for v in row])
    return out
