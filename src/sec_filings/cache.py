"""SQLite-based caching for SEC filings to reduce redundant API calls."""

import sqlite3
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class FilingCache:
    """SQLite cache for storing downloaded SEC filings.

    This cache reduces the number of API calls to the SEC by storing
    previously downloaded filings locally. Useful for development,
    testing, and repeated searches.

    Example:
        >>> cache = FilingCache()
        >>> # Store a filing
        >>> cache.set("0000320193-23-000077", "<html>...</html>")
        >>> # Retrieve it later
        >>> content = cache.get("0000320193-23-000077")
    """

    def __init__(self, cache_dir: Optional[Path] = None, ttl_days: int = 30):
        """Initialize the filing cache.

        Args:
            cache_dir: Directory to store the cache database.
                      Defaults to ~/.sec_filings_cache/
            ttl_days: Time-to-live in days. Entries older than this
                     will be considered expired. Default: 30 days
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".sec_filings_cache"

        cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = cache_dir / "filings.db"
        self.ttl_seconds = ttl_days * 24 * 60 * 60

        self._init_database()

    def _init_database(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS filings (
                    accession_number TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    download_timestamp INTEGER NOT NULL,
                    file_size INTEGER NOT NULL
                )
            """)

            # Create index on timestamp for efficient cleanup
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON filings(download_timestamp)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def get(self, accession_number: str) -> Optional[str]:
        """Retrieve a filing from cache if it exists and isn't expired.

        Args:
            accession_number: SEC accession number (e.g., "0000320193-23-000077")

        Returns:
            Filing content as string, or None if not cached or expired
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT content, download_timestamp
                FROM filings
                WHERE accession_number = ?
                """,
                (accession_number,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            content, timestamp = row

            # Check if expired
            if self._is_expired(timestamp):
                # Delete expired entry
                conn.execute(
                    "DELETE FROM filings WHERE accession_number = ?",
                    (accession_number,)
                )
                conn.commit()
                return None

            return content

    def set(self, accession_number: str, content: str):
        """Store a filing in the cache.

        Args:
            accession_number: SEC accession number
            content: Full filing content (HTML/XML)
        """
        timestamp = int(time.time())
        file_size = len(content)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO filings
                (accession_number, content, download_timestamp, file_size)
                VALUES (?, ?, ?, ?)
                """,
                (accession_number, content, timestamp, file_size)
            )
            conn.commit()

    def _is_expired(self, timestamp: int) -> bool:
        """Check if a timestamp is expired based on TTL.

        Args:
            timestamp: Unix timestamp

        Returns:
            True if expired, False otherwise
        """
        current_time = int(time.time())
        return (current_time - timestamp) > self.ttl_seconds

    def clear_expired(self) -> int:
        """Remove all expired entries from the cache.

        Returns:
            Number of entries removed
        """
        cutoff_time = int(time.time()) - self.ttl_seconds

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM filings WHERE download_timestamp < ?",
                (cutoff_time,)
            )
            conn.commit()
            return cursor.rowcount

    def clear_all(self) -> int:
        """Remove all entries from the cache.

        Returns:
            Number of entries removed
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM filings")
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics:
            - total_entries: Total number of cached filings
            - total_size_mb: Total size of cached content in MB
            - oldest_entry_days: Age of oldest entry in days
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as count,
                    SUM(file_size) as total_size,
                    MIN(download_timestamp) as oldest
                FROM filings
            """)
            row = cursor.fetchone()

            count, total_size, oldest = row
            count = count or 0
            total_size = total_size or 0

            # Calculate age of oldest entry
            oldest_days = None
            if oldest:
                age_seconds = int(time.time()) - oldest
                oldest_days = age_seconds / (24 * 60 * 60)

            return {
                "total_entries": count,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_entry_days": round(oldest_days, 1) if oldest_days else None
            }

    def has(self, accession_number: str) -> bool:
        """Check if a filing exists in cache (and isn't expired).

        Args:
            accession_number: SEC accession number

        Returns:
            True if filing is cached and not expired, False otherwise
        """
        return self.get(accession_number) is not None
