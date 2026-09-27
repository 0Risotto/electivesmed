"""DAO layer: direct communication with the local SQLite data store."""

from .dao import Dao
from .sqlite import SqliteDao

__all__ = ["Dao", "SqliteDao"]
