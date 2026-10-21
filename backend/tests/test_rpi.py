import pytest

from app.services.rpi import band_for, compute, env_risk_from_zone
from app.services.settings import DEFAULTS

S = DEFAULTS


def rpi(**kw):
    base = dict(posture="lying", posture_confidence=0.9, detection_confidence=0.9, env_risk=None)
    return compute(settings=S, **{**base, **kw})


def test_formula_with_env_risk():
    r = rpi(env_risk=1.0)
    assert r.score == pytest.approx(0.6 * 1.0 + 0.25 * 0.9 + 0.15 * 1.0)
    assert r.band == "critical" and r.env_risk_used


def test_missing_env_risk_renormalises_posture_and_confidence():
    """SRS UC-03 AF2: R unavailable → posture + confidence only, same 0–1 scale."""
    r = rpi(env_risk=None)
    assert r.score == pytest.approx((0.6 * 1.0 + 0.25 * 0.9) / 0.85, abs=1e-4)
    assert not r.env_risk_used


def test_zero_env_weight_is_accepted():
    s = {**S, "rpi.weights": {"w_p": 0.7, "w_c": 0.3, "w_r": 0.0}}
    r = compute(posture="sitting", posture_confidence=0.9, detection_confidence=0.5,
                env_risk=1.0, settings=s)  # fmt: skip
    assert r.score == pytest.approx(0.7 * 0.5 + 0.3 * 0.5)


def test_posture_ordering():
    scores = {
        p: rpi(posture=p, env_risk=0.5).score for p in ("lying", "bending", "sitting", "standing")
    }
    assert scores["lying"] > scores["bending"] > scores["sitting"] > scores["standing"]


def test_low_confidence_posture_is_penalised_but_still_ranked_and_flagged():
    sure = rpi(posture_confidence=0.9)
    unsure = rpi(posture_confidence=0.4)
    assert unsure.low_confidence and not sure.low_confidence
    assert 0 < unsure.score < sure.score


def test_explicit_low_confidence_flag_wins():
    assert rpi(posture_confidence=0.95, low_confidence=True).low_confidence


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (0.75, "critical"),
        (0.749, "high"),
        (0.55, "high"),
        (0.35, "medium"),
        (0.349, "low"),
        (0, "low"),
    ],
)
def test_band_thresholds(score, band):
    assert band_for(score, S["rpi.bands"]) == band


def test_scores_are_clamped():
    r = rpi(detection_confidence=1.7, env_risk=3.0)
    assert 0 <= r.score <= 1


def test_env_risk_from_zone_status():
    assert env_risk_from_zone("unsafe") == env_risk_from_zone("blocked") == 1.0
    assert env_risk_from_zone("caution") == 0.5 and env_risk_from_zone("safe") == 0.0
    assert env_risk_from_zone("unclassified") is None and env_risk_from_zone(None) is None
