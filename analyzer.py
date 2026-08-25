"""
YouTube analysis engine.

A single background worker thread consumes jobs from an input queue, runs yt-dlp
(no API key required) to extract metadata, downloads/caches the thumbnail, and
pushes result events onto an output queue that the UI drains via `after()`.

Design goals:
  * The GUI never blocks — all network / extraction happens off the main thread.
  * A single failing video never aborts the batch; it is reported as failed and
    the worker moves on.
"""

import os
import queue
import threading
import urllib.request

import config

try:
    import yt_dlp
except Exception:  # pragma: no cover - handled gracefully at runtime
    yt_dlp = None


# Event types placed on the output queue
EVT_STARTED = "started"     # (EVT_STARTED, pk)              -> row went into Analyzing
EVT_RESULT = "result"       # (EVT_RESULT, pk, meta_dict)    -> analysis finished (ok/fail)
EVT_BATCH = "batch"         # (EVT_BATCH, done, total)       -> progress update
EVT_IDLE = "idle"           # (EVT_IDLE,)                    -> queue drained


class _SilentLogger:
    """Swallows yt-dlp's own logging so a windowed build stays quiet."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


class AnalysisWorker:
    def __init__(self):
        self._in = queue.Queue()
        self.out = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._total = 0
        self._done = 0
        self._lock = threading.Lock()
        self._thread.start()

    # ------------------------------------------------------------------ #
    #  Public API (called from the UI thread)
    # ------------------------------------------------------------------ #
    def enqueue(self, pk: int, url: str):
        """Queue a single video (identified by its DB primary key) for analysis."""
        with self._lock:
            self._total += 1
            total, done = self._total, self._done
        self.out.put((EVT_BATCH, done, total))
        self._in.put((pk, url))

    def enqueue_many(self, items):
        """items: iterable of (pk, url)."""
        items = list(items)
        with self._lock:
            self._total += len(items)
            total, done = self._total, self._done
        self.out.put((EVT_BATCH, done, total))
        for pk, url in items:
            self._in.put((pk, url))

    def reset_progress_if_idle(self):
        """Called by the UI when the queue is empty to zero the counters."""
        with self._lock:
            if self._in.empty():
                self._total = 0
                self._done = 0

    # ------------------------------------------------------------------ #
    #  Worker loop
    # ------------------------------------------------------------------ #
    def _run(self):
        while True:
            pk, url = self._in.get()
            self.out.put((EVT_STARTED, pk))
            meta = self.analyze(url)
            self.out.put((EVT_RESULT, pk, meta))

            with self._lock:
                self._done += 1
                total, done = self._total, self._done
                idle = self._in.empty()
            self.out.put((EVT_BATCH, done, total))
            if idle:
                self.out.put((EVT_IDLE,))
            self._in.task_done()

    # ------------------------------------------------------------------ #
    #  Core extraction — safe, never raises
    # ------------------------------------------------------------------ #
    def analyze(self, url: str) -> dict:
        if yt_dlp is None:
            return {"status": config.STATUS_FAILED,
                    "error": "yt-dlp is not installed"}

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": False,
            "socket_timeout": 30,
            "logger": _SilentLogger(),
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # noqa: BLE001 - report and continue
            return {"status": config.STATUS_FAILED, "error": str(exc)}

        if not info:
            return {"status": config.STATUS_FAILED, "error": "No data returned"}

        video_id = info.get("id")
        thumb_url = self._best_thumbnail(info)
        thumb_path = self._cache_thumbnail(video_id, thumb_url)

        return {
            "status": config.STATUS_READY,
            "video_id": video_id,
            "title": info.get("title") or "(untitled)",
            "views": info.get("view_count"),
            "likes": info.get("like_count"),
            "thumbnail_url": thumb_url,
            "thumbnail_path": thumb_path,
        }

    # ------------------------------------------------------------------ #
    #  Thumbnail helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _best_thumbnail(info: dict):
        # Prefer the explicit thumbnail, then pick the highest-res candidate.
        thumbs = info.get("thumbnails") or []
        if thumbs:
            def area(t):
                return (t.get("width") or 0) * (t.get("height") or 0)
            best = max(thumbs, key=area)
            if best.get("url"):
                return best["url"]
        return info.get("thumbnail")

    @staticmethod
    def _cache_thumbnail(video_id, thumb_url):
        if not video_id or not thumb_url:
            return None
        ext = ".jpg"
        for candidate in (".jpg", ".png", ".webp"):
            if candidate in thumb_url.lower():
                ext = candidate
                break
        path = os.path.join(config.THUMB_CACHE_DIR, f"{video_id}{ext}")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        try:
            req = urllib.request.Request(
                thumb_url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if data:
                with open(path, "wb") as fh:
                    fh.write(data)
                return path
        except Exception:  # noqa: BLE001 - thumbnail is best-effort
            return None
        return None
