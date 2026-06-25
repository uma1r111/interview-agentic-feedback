# repositories/__init__.py
# Repository pattern: abstracts all data access behind interfaces.
# Concrete implementations (SQLite today, Postgres tomorrow) swap here
# without touching any service or route code.

from repositories.base import BaseRepository
from repositories.candidate_repository import CandidateRepository
from repositories.intake_repository import IntakeRepository

__all__ = [
    "BaseRepository",
    "CandidateRepository",
    "IntakeRepository",
]