"""Tests for score combining (data_engine/combine.py). Answers worked out by hand."""
import pytest

from data_engine.combine import combine_scores, location_prior

SPECIES = ["a", "b", "c", "d"]


def test_prior_uses_add_one_smoothing():
    # 6 + 2 = 8 sightings, 4 species -> denominator is 8 + 4 = 12
    prior = location_prior({"a": 6, "b": 2}, SPECIES)
    assert prior["a"] == pytest.approx(7 / 12)
    assert prior["b"] == pytest.approx(3 / 12)
    assert prior["c"] == pytest.approx(1 / 12)  # never seen, but not zero
    assert sum(prior.values()) == pytest.approx(1.0)


def test_prior_with_no_sightings_is_flat():
    prior = location_prior({}, SPECIES)
    assert all(p == pytest.approx(0.25) for p in prior.values())


def test_prior_ignores_species_not_on_our_list():
    prior = location_prior({"a": 1, "zebra": 99}, SPECIES)
    assert "zebra" not in prior
    assert sum(prior.values()) == pytest.approx(1.0)


def test_full_weight_is_photo_times_prior_rescaled():
    image = {"a": 0.5, "b": 0.5}
    prior = {"a": 0.75, "b": 0.25}
    # a: 0.5 * 0.75 = 0.375, b: 0.5 * 0.25 = 0.125, total 0.5
    result = combine_scores(image, prior, weight=1.0)
    assert result["a"] == pytest.approx(0.75)
    assert result["b"] == pytest.approx(0.25)


def test_half_weight_softens_the_boost():
    image = {"a": 0.5, "b": 0.5}
    prior = {"a": 0.8, "b": 0.2}
    # sqrt(0.8) : sqrt(0.2) = 2 : 1, so a gets 2/3 instead of the 0.8 full weight would give
    result = combine_scores(image, prior, weight=0.5)
    assert result["a"] == pytest.approx(2 / 3)
    assert result["b"] == pytest.approx(1 / 3)


def test_zero_weight_ignores_location():
    image = {"a": 0.6, "b": 0.3, "c": 0.1}
    prior = {"a": 0.01, "b": 0.01, "c": 0.98}
    assert combine_scores(image, prior, weight=0.0) == pytest.approx(image)


def test_no_prior_returns_rescaled_photo_scores():
    result = combine_scores({"a": 2.0, "b": 1.0, "c": 1.0}, None)
    assert result == pytest.approx({"a": 0.5, "b": 0.25, "c": 0.25})


def test_boost_can_flip_a_close_call_but_not_a_clear_photo():
    prior = location_prior({"a": 98}, ["a", "b"])  # a = 0.99, b = 0.01
    close = combine_scores({"a": 0.45, "b": 0.55}, prior)
    assert close["a"] > close["b"]  # look-alikes: location decides
    clear = combine_scores({"a": 0.01, "b": 0.99}, prior)
    assert clear["b"] > clear["a"]  # a clear photo of the rare one still wins


def test_results_always_add_up_to_one():
    result = combine_scores({"a": 0.2, "b": 0.1, "c": 0.05}, {"a": 0.5, "b": 0.3, "c": 0.2})
    assert sum(result.values()) == pytest.approx(1.0)
    assert all(0.0 <= v <= 1.0 for v in result.values())


def test_all_zero_photo_scores_give_equal_confidence():
    result = combine_scores({"a": 0.0, "b": 0.0}, {"a": 0.9, "b": 0.1})
    assert result == pytest.approx({"a": 0.5, "b": 0.5})


def test_negative_photo_score_is_an_error():
    with pytest.raises(ValueError):
        combine_scores({"a": -0.1, "b": 0.5}, None)
