# repositories/base.py
"""
Abstract base repository.

Defines the contract that every concrete repository must fulfil.
Using generics so type checkers understand what T each repo returns.

WHY THIS EXISTS
---------------
Without a base class, the service layer would import concrete database
modules directly (tight coupling). With this, services depend on the
*interface*, not the implementation. Swapping SQLite → Postgres means
creating a new concrete class, not changing every service that uses data.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Any, Dict

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Generic repository interface.

    Concrete repos don't have to implement all of these — only the ones
    that make sense for their entity. Override what you need, raise
    NotImplementedError for what doesn't apply.
    """

    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """Fetch a single entity by its primary identifier."""
        raise NotImplementedError

    @abstractmethod
    def get_all(self) -> List[T]:
        """Fetch all entities of this type."""
        raise NotImplementedError

    @abstractmethod
    def save(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Persist an entity (insert or replace)."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        Remove an entity by ID.
        Returns True if a row was deleted, False if not found.
        """
        raise NotImplementedError

    def update(self, entity_id: str, data: Dict[str, Any]) -> bool:
        """
        Partial update — not all repos need this.
        Default raises so you notice if you call it without implementing.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement update()"
        )