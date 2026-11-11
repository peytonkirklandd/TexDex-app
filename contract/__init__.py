"""Shared contract. Person B imports `identify` from here.

USE_FAKE_ID=1 (the default) returns fake guesses. Set USE_FAKE_ID=0 once Person A's
real function in data_engine/identify.py is ready; no other code changes needed.
"""
import os

from .id_contract import NOT_SURE_CUTOFF, Guess, IDResult, validate_result


def identify(photo_path, latitude, longitude, obs_date) -> IDResult:
    if os.getenv("USE_FAKE_ID", "1") == "1":
        from .fake_identify import fake_identify as fn
    else:
        from data_engine.identify import identify as fn
    return fn(photo_path, latitude, longitude, obs_date)


__all__ = ["identify", "Guess", "IDResult", "NOT_SURE_CUTOFF", "validate_result"]
