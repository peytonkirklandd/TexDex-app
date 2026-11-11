"""Real ID function. Person A builds this (due Sat Nov 21).

Must follow contract/id_contract.py exactly and pass tests/test_contract.py.
Plan: BioCLIP 2 scores, combined with the month-by-region likelihood (location boost).
"""
from __future__ import annotations

from datetime import date

from contract.id_contract import IDResult, PhotoInput


def identify(
    photo_path: PhotoInput, latitude: float, longitude: float, obs_date: date
) -> IDResult:
    raise NotImplementedError("Person A: real identify() goes here (due Nov 21)")
