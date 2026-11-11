"""The ID function contract, shared by Person A and Person B.

Do not change this file without both people agreeing (see docs/interface.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol, Union

# Placeholder. Person A sets the final value from the accuracy work.
NOT_SURE_CUTOFF = 0.5

NUM_GUESSES = 3

PhotoInput = Union[str, Path]


@dataclass(frozen=True)
class Guess:
    species_id: str
    confidence: float  # 0 to 1


@dataclass(frozen=True)
class IDResult:
    guesses: list[Guess]  # exactly 3, highest confidence first
    not_sure: bool  # True when the top confidence < NOT_SURE_CUTOFF


class IdentifyFn(Protocol):
    def __call__(
        self, photo_path: PhotoInput, latitude: float, longitude: float, obs_date: date
    ) -> IDResult: ...


def validate_result(result: IDResult) -> None:
    """Raise ValueError if a result breaks the contract. Used by tests on both halves."""
    if not isinstance(result, IDResult):
        raise ValueError("identify() must return an IDResult")
    if len(result.guesses) != NUM_GUESSES:
        raise ValueError(f"expected {NUM_GUESSES} guesses, got {len(result.guesses)}")
    for g in result.guesses:
        if not isinstance(g.species_id, str) or not g.species_id:
            raise ValueError("each guess needs a non-empty species_id string")
        if not 0.0 <= g.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {g.confidence}")
    confs = [g.confidence for g in result.guesses]
    if confs != sorted(confs, reverse=True):
        raise ValueError("guesses must be sorted highest confidence first")
    expected_not_sure = confs[0] < NOT_SURE_CUTOFF
    if result.not_sure != expected_not_sure:
        raise ValueError("not_sure flag doesn't match the top confidence and cutoff")
