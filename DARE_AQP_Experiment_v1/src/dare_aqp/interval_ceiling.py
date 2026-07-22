"""Exact multi-resolution interval-oracle ceiling policies."""

from dataclasses import dataclass
import heapq
import math


@dataclass(frozen=True)
class Query:
    operator: str
    lo: int
    hi: int

    @property
    def length(self):
        return self.hi - self.lo


def split_interval(lo, hi):
    if hi - lo <= 1:
        raise ValueError("cannot split a leaf interval")
    mid = lo + (hi - lo) // 2
    return (lo, mid), (mid, hi)


def anchor_count(prefix, lo, hi):
    return prefix[hi] - prefix[lo]


def make_prefix(population_size, anchor_units):
    values = [0] * population_size
    for unit in anchor_units:
        if not 0 <= unit < population_size:
            raise ValueError("anchor outside population")
        if values[unit]:
            raise ValueError("duplicate anchor unit")
        values[unit] = 1
    prefix = [0]
    for value in values:
        prefix.append(prefix[-1] + value)
    return prefix


def _record_leaf(interval, prefix, found):
    lo, hi = interval
    if hi - lo == 1 and anchor_count(prefix, lo, hi):
        found.add(lo)
        return True
    return False


def any_binary_full(population_size, anchor_units):
    """Localize every anchor by exact binary ANY_EVENT queries."""
    prefix = make_prefix(population_size, anchor_units)
    queries = [Query("ANY_EVENT", 0, population_size)]
    stack = [(0, population_size)] if anchor_units else []
    found = set()
    while stack:
        lo, hi = stack.pop()
        if _record_leaf((lo, hi), prefix, found):
            continue
        left, right = split_interval(lo, hi)
        for child in (left, right):
            queries.append(Query("ANY_EVENT", *child))
            if anchor_count(prefix, *child):
                if not _record_leaf(child, prefix, found):
                    stack.append(child)
    return queries, found


def _proxy_priority(proxy, lo, hi):
    block = proxy[lo:hi]
    return (max(block), sum(block) / len(block), -(hi - lo), -lo)


def count_root_any_best_first(population_size, anchor_units, proxy, target_recall, oracle_priority=False):
    """COUNT root, then split positive intervals using ANY_EVENT children."""
    prefix = make_prefix(population_size, anchor_units)
    target = math.ceil(target_recall * len(anchor_units) - 1e-12)
    queries = [Query("COUNT_EVENTS", 0, population_size)]
    found = set()
    heap = []

    def push(interval):
        lo, hi = interval
        if _record_leaf(interval, prefix, found):
            return
        if oracle_priority:
            priority = (anchor_count(prefix, lo, hi), -(hi - lo), -lo)
        else:
            priority = _proxy_priority(proxy, lo, hi)
        heapq.heappush(heap, (tuple(-x for x in priority), lo, hi))

    if target:
        push((0, population_size))
    while len(found) < target and heap:
        _, lo, hi = heapq.heappop(heap)
        left, right = split_interval(lo, hi)
        for child in (left, right):
            queries.append(Query("ANY_EVENT", *child))
            if anchor_count(prefix, *child):
                push(child)
    if len(found) < target:
        raise AssertionError("failed to localize requested target")
    return queries, found


def count_guided(population_size, anchor_units, proxy, target_recall):
    """Use exact count conservation and split highest-density known blocks."""
    prefix = make_prefix(population_size, anchor_units)
    total = len(anchor_units)
    target = math.ceil(target_recall * total - 1e-12)
    queries = [Query("COUNT_EVENTS", 0, population_size)]
    found = set()
    heap = []

    def push(interval, count):
        lo, hi = interval
        if count <= 0:
            return
        if hi - lo == 1:
            found.add(lo)
            return
        density = count / (hi - lo)
        proxy_priority = _proxy_priority(proxy, lo, hi)
        key = (-density, -count, tuple(-x for x in proxy_priority), lo, hi)
        heapq.heappush(heap, key)

    if target:
        push((0, population_size), total)
    while len(found) < target and heap:
        _, neg_count, _, lo, hi = heapq.heappop(heap)
        count = -neg_count
        left, right = split_interval(lo, hi)
        left_count = anchor_count(prefix, *left)
        queries.append(Query("COUNT_EVENTS", *left))
        right_count = count - left_count
        push(left, left_count)
        push(right, right_count)
    if len(found) < target:
        raise AssertionError("failed to localize requested target")
    return queries, found


def trace_cost(queries, fixed_fraction, count_multiplier=1.0, certify_count=0, certify_cost=1.0):
    total = 0.0
    for query in queries:
        base = fixed_fraction + (1.0 - fixed_fraction) * query.length
        if query.operator == "COUNT_EVENTS":
            base *= count_multiplier
        total += base
    return total + certify_count * certify_cost

