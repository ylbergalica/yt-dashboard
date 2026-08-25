"""
SQLite persistence layer for the video library.

The database is opened with check_same_thread=False and guarded by a lock so it
can be safely written from the background analysis worker and read from the UI
thread. Every mutation is committed immediately, which satisfies the data-safety
requirement: nothing is lost if the app is closed or crashes mid-batch.
"""

import sqlite3
import threading
import time
from datetime import datetime

import config


_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id      TEXT,
    url           TEXT NOT NULL,
    title         TEXT,
    views         INTEGER,
    likes         INTEGER,
    thumbnail_url TEXT,
    thumbnail_path TEXT,
    category      TEXT NOT NULL,
    status        TEXT NOT NULL,
    date_added    TEXT NOT NULL,
    sort_order    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_videos_category ON videos(category);
CREATE INDEX IF NOT EXISTS idx_videos_video_id ON videos(video_id);
"""


class Database:
    def __init__(self, path: str = config.DB_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _row_to_dict(row) -> dict:
        return dict(row) if row is not None else None

    # ------------------------------------------------------------------ #
    #  Reads
    # ------------------------------------------------------------------ #
    def all_videos(self):
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM videos ORDER BY COALESCE(sort_order, id) DESC"
            )
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def get(self, vid_pk: int):
        with self._lock:
            cur = self._conn.execute("SELECT * FROM videos WHERE id=?", (vid_pk,))
            return self._row_to_dict(cur.fetchone())

    def exists_video_id(self, video_id: str):
        """Return the primary key of an existing row with this youtube id, or None."""
        if not video_id:
            return None
        with self._lock:
            cur = self._conn.execute(
                "SELECT id FROM videos WHERE video_id=? LIMIT 1", (video_id,)
            )
            row = cur.fetchone()
            return row["id"] if row else None

    def category_counts(self) -> dict:
        with self._lock:
            cur = self._conn.execute(
                "SELECT category, COUNT(*) AS n FROM videos GROUP BY category"
            )
            counts = {c: 0 for c in config.CATEGORIES}
            total = 0
            for r in cur.fetchall():
                counts[r["category"]] = r["n"]
                total += r["n"]
            counts["__all__"] = total
            return counts

    # ------------------------------------------------------------------ #
    #  Writes
    # ------------------------------------------------------------------ #
    def add_pending(self, video_id: str, url: str,
                    category: str = config.DEFAULT_CATEGORY) -> int:
        """Insert a placeholder row in the 'Analyzing...' state and return its pk."""
        with self._lock:
            order = int(time.time() * 1000)
            cur = self._conn.execute(
                """INSERT INTO videos
                   (video_id, url, title, views, likes, thumbnail_url,
                    thumbnail_path, category, status, date_added, sort_order)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (video_id, url, None, None, None, None, None,
                 category, config.STATUS_ANALYZING, self._now(), order),
            )
            self._conn.commit()
            return cur.lastrowid

    def update_fields(self, vid_pk: int, **fields):
        if not fields:
            return
        with self._lock:
            cols = ", ".join(f"{k}=?" for k in fields)
            params = list(fields.values()) + [vid_pk]
            self._conn.execute(f"UPDATE videos SET {cols} WHERE id=?", params)
            self._conn.commit()

    def set_category(self, vid_pk: int, category: str):
        self.update_fields(vid_pk, category=category)

    def set_category_bulk(self, pks, category: str):
        with self._lock:
            self._conn.executemany(
                "UPDATE videos SET category=? WHERE id=?",
                [(category, pk) for pk in pks],
            )
            self._conn.commit()

    def set_status(self, vid_pk: int, status: str):
        self.update_fields(vid_pk, status=status)

    def apply_metadata(self, vid_pk: int, meta: dict):
        """Write analysis results (or a failed status) back to a row."""
        with self._lock:
            self.update_fields(
                vid_pk,
                video_id=meta.get("video_id"),
                title=meta.get("title"),
                views=meta.get("views"),
                likes=meta.get("likes"),
                thumbnail_url=meta.get("thumbnail_url"),
                thumbnail_path=meta.get("thumbnail_path"),
                status=meta.get("status", config.STATUS_READY),
            )

    def delete(self, vid_pk: int):
        with self._lock:
            self._conn.execute("DELETE FROM videos WHERE id=?", (vid_pk,))
            self._conn.commit()

    def delete_many(self, pks):
        with self._lock:
            self._conn.executemany(
                "DELETE FROM videos WHERE id=?", [(pk,) for pk in pks]
            )
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()
