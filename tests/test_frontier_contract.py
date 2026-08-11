from itertools import permutations

from frozen_reference import SourceFrozenFrontier, source_frontier_order
from garc.controller import Candidate, FrozenFrontier


def candidate(unit, score, track=0, name=None, created=0):
    return Candidate(name or f"c{unit}", unit, track, score, created, 0)


def test_selection_parity_and_tie_breaking():
    rows = [candidate(3, .8, 2), candidate(1, .8, 9), candidate(2, .9, 5), candidate(4, .8, 1)]
    for ordering in permutations(rows):
        frontier = FrozenFrontier(10)
        frontier.update(list(ordering))
        assert frontier.best() == source_frontier_order(rows)[0]


def test_frontier_admission_retention_and_selection_parity():
    target, source = FrozenFrontier(3), SourceFrozenFrontier(3)
    batches = [
        [candidate(4, .4), candidate(2, .8, 3), candidate(1, .8, 2), candidate(3, .2)],
        [candidate(2, .9, 3), candidate(5, 1.0)],
        [candidate(1, 2.0), candidate(6, .7)],
    ]
    for batch in batches:
        assert target.update(batch) == source.update(batch)
        assert sorted(target.rows(), key=target._key) == source_frontier_order(source.rows_by_unit.values())
        assert target.best() == source.best()
        assert target.discarded == source.discarded
    selected = target.best().unit_id
    target.terminalize(selected)
    source.terminalize(selected)
    assert target.best() == source.best()
    assert target.queried == source.queried


def test_dedup_retention_terminalization_and_aging():
    frontier = FrozenFrontier(2)
    admitted, dropped = frontier.update([candidate(1, .2, created=2), candidate(2, .9), candidate(3, .8)])
    assert admitted == 2 and dropped == [1] and frontier.discarded == {1}
    frontier.update([candidate(1, 1.0), candidate(2, .95)])
    assert len(frontier) == 2 and frontier.best().unit_id == 2
    frontier.terminalize(2)
    frontier.update([candidate(2, 2.0)])
    assert frontier.best().unit_id == 3 and 2 in frontier.queried
    assert frontier.ages(5) == [5]
