from app.services.tracking import Tracker, iou


def box(x, y, w=0.1, h=0.3):
    return (x, y, x + w, y + h)


def test_iou():
    assert iou(box(0, 0), box(0, 0)) == 1.0
    assert iou(box(0, 0), box(0.5, 0.5)) == 0.0


def test_person_confirmed_after_two_consecutive_samples():
    t = Tracker()
    t.update([box(0.2, 0.3)], [0])
    assert t.confirmed() == []
    t.update([box(0.21, 0.31)], [1])
    [track] = t.confirmed()
    assert track.observations == [0, 1]


def test_single_blip_is_not_a_person():
    t = Tracker()
    t.update([box(0.2, 0.3)], [0])
    t.update([], [])
    t.update([], [])
    assert t.confirmed() == []


def test_short_miss_keeps_the_track():
    t = Tracker(max_misses=2)
    t.update([box(0.2, 0.3)], [0])
    t.update([box(0.2, 0.3)], [1])
    t.update([], [])  # missed one sample (occlusion, smoke)
    ids = t.update([box(0.22, 0.3)], [2])
    assert len(t.tracks) == 1 and ids == [t.tracks[0].id]


def test_long_miss_starts_a_new_track():
    t = Tracker(max_misses=1)
    t.update([box(0.2, 0.3)], [0])
    t.update([box(0.2, 0.3)], [1])
    t.update([], [])
    t.update([], [])
    t.update([box(0.2, 0.3)], [2])
    assert len(t.tracks) == 2


def test_two_people_keep_their_identities():
    t = Tracker()
    a1, b1 = t.update([box(0.1, 0.3), box(0.6, 0.3)], [0, 1])
    b2, a2 = t.update([box(0.62, 0.3), box(0.12, 0.31)], [2, 3])
    assert (a1, b1) == (a2, b2)


def test_centroid_fallback_for_fast_motion():
    t = Tracker(max_centre_dist=0.15)
    first = t.update([box(0.2, 0.3, 0.05, 0.1)], [0])
    second = t.update([box(0.28, 0.3, 0.05, 0.1)], [1])  # no overlap, centres 0.08 apart
    assert first == second


def test_still_image_mode_confirms_immediately():
    t = Tracker(confirm_after=1)
    t.update([box(0.2, 0.3)], [0])
    assert len(t.confirmed()) == 1
