from safeplay.engine import SkipEngine
from safeplay.models import Scene


def scene(key, start, end, category="violence", reliability="verified"):
    return Scene(key, start, end, category, "test", reliability)


def ready(scenes):
    e = SkipEngine(.5)
    e.load(scenes, 200, confirmed=True)
    e.enabled = True
    e.filters = {"violence": True, "language": True}
    return e


def test_adjacent_overlapping_and_categories():
    e = ready([scene("a", 10, 20), scene("b", 20, 25, "language"), scene("c", 24, 30)])
    assert e.tick(9.6, False, 1) == (30.5, ["a", "b", "c"])
    assert e.tick(9.7, False, 1.1) is None
    assert e.tick(30.5, False, 1.2) is None


def test_unreliable_disabled_pause_and_filter():
    e = ready([scene("a", 10, 20, reliability="community")])
    assert e.tick(10, False, 1) is None
    e.load([scene("b", 10, 20)], 200, True)
    e.filters["violence"] = False
    assert e.tick(10, False, 2) is None
    e.filters["violence"] = True
    assert e.tick(10, True, 3) is None
    assert e.tick(10, False, 4)[0] == 20.5


def test_manual_backward_seek_rearms_and_conflict_suspends():
    e = ready([scene("a", 10, 20)])
    assert e.tick(10, False, 1)
    assert e.tick(20.5, False, 1.5) is None
    assert e.tick(8, False, 4) is None
    assert e.tick(10, False, 5)
    assert e.tick(10, False, 6.5) is None
    assert e.suspended


def test_failed_seek_retries():
    e = ready([scene("a", 10, 20)])
    _, keys = e.tick(10, False, 1)
    e.seek_failed(keys)
    assert e.tick(10, False, 2)
