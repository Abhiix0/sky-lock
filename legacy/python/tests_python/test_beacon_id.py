"""Tests for skylock.beacon_id — blink code matched filter."""

import pytest

from skylock.beacon_id import (
    build_code_template,
    compute_blink_score,
    evaluate_candidates,
    get_confirmed_candidate,
)
from skylock.config import BeaconCodeConfig, IdConfig


class TestBeaconId:
    def test_build_code_template(self):
        # 2 bits, 3 samples per bit
        template = build_code_template("10", 3)
        assert template == [1.0, 1.0, 1.0, 0.0, 0.0, 0.0]

    def test_compute_blink_score_perfect_match(self):
        config = BeaconCodeConfig(bits="10", samples_per_bit=3)
        # History exactly matches template
        history = [100.0, 50.0, 10.0, 0.0, 0.0, 0.0]
        res = compute_blink_score(history, config)
        assert res["score"] == pytest.approx(1.0)
        assert res["best_shift"] == 0

    def test_compute_blink_score_shifted_match(self):
        config = BeaconCodeConfig(bits="10", samples_per_bit=3)
        # Shifted by 2 frames: 1.0, 0.0, 0.0, 0.0, 1.0, 1.0
        history = [10.0, 0.0, 0.0, 0.0, 50.0, 100.0]
        res = compute_blink_score(history, config)
        assert res["score"] == pytest.approx(1.0)
        assert res["best_shift"] == 2

    def test_compute_blink_score_degenerate_all_on(self):
        config = BeaconCodeConfig(bits="10", samples_per_bit=3)
        history = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        res = compute_blink_score(history, config)
        assert res["score"] == 0.0

    def test_compute_blink_score_degenerate_all_off(self):
        config = BeaconCodeConfig(bits="10", samples_per_bit=3)
        history = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        res = compute_blink_score(history, config)
        assert res["score"] == 0.0

    def test_evaluate_candidates_steady_mode(self):
        cands = [
            {"id": 1, "total_observations": 1, "history": []},
            {"id": 2, "total_observations": 5, "history": []},
        ]
        code_config = BeaconCodeConfig(mode="steady")
        id_config = IdConfig(id_confirm_frames=3)

        res = evaluate_candidates(cands, code_config, id_config)

        # Candidate 2 should be confirmed and sorted first
        assert res[0]["id"] == 2
        assert res[0]["confirmed"] is True
        assert res[1]["id"] == 1
        assert res[1].get("confirmed") is not True

    def test_evaluate_candidates_code_mode(self):
        code_config = BeaconCodeConfig(mode="code", bits="10", samples_per_bit=3)
        id_config = IdConfig(id_threshold=0.8, id_confirm_frames=2)

        cands = [
            # Perfect match, confirm streak 1 -> becomes 2 and confirmed
            {"id": 1, "history": [10.0, 10.0, 10.0, 0.0, 0.0, 0.0], "confirm_streak": 1},
            # Complete mismatch
            {"id": 2, "history": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "confirm_streak": 0},
        ]

        res = evaluate_candidates(cands, code_config, id_config)

        assert res[0]["id"] == 1
        assert res[0]["confirmed"] is True
        assert res[0]["score"] > 0.9

        assert res[1]["id"] == 2
        assert res[1].get("confirmed", False) is False
        assert res[1]["score"] == 0.0

    def test_get_confirmed_candidate(self):
        cands = [
            {"id": 1, "confirmed": False},
            {"id": 2, "confirmed": True},
        ]
        res = get_confirmed_candidate(cands)
        assert res is not None
        assert res["id"] == 2
