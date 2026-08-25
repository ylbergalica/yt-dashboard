"""
Central configuration: paths, theme colors, categories and formatting helpers.

Everything the rest of the application needs to stay visually and behaviourally
consistent lives here so there is a single source of truth.
"""

import os
import re
import sys
import math


# --------------------------------------------------------------------------- #
#  Application identity
# --------------------------------------------------------------------------- #
APP_NAME = "YouTube Content Dashboard"
APP_ID = "YouTubeContentDashboard"


# --------------------------------------------------------------------------- #
#  Persistent storage locations
#
#  Data is stored in the user's %APPDATA% directory so that it survives across
#  application updates and works correctly for a packaged, read-only .exe.
# --------------------------------------------------------------------------- #
def _data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_ID)
    os.makedirs(path, exist_ok=True)
    return path


DATA_DIR = _data_dir()
DB_PATH = os.path.join(DATA_DIR, "library.db")
THUMB_CACHE_DIR = os.path.join(DATA_DIR, "thumbnails")
os.makedirs(THUMB_CACHE_DIR, exist_ok=True)


def resource_path(relative: str) -> str:
    """Resolve a bundled resource path (works for PyInstaller onefile)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


# --------------------------------------------------------------------------- #
#  Categories
# --------------------------------------------------------------------------- #
CAT_SCRIPT = "Script Writing"
CAT_EDIT = "Video Editing"
CAT_THUMB = "Thumbnail Design"

CATEGORIES = [CAT_SCRIPT, CAT_EDIT, CAT_THUMB]
DEFAULT_CATEGORY = CAT_SCRIPT


# --------------------------------------------------------------------------- #
#  Analysis status values
# --------------------------------------------------------------------------- #
STATUS_ANALYZING = "Analyzing..."
STATUS_READY = "Ready"
STATUS_FAILED = "Analysis Failed"


# --------------------------------------------------------------------------- #
#  Colour palette  (Linear / Notion inspired dark theme)
# --------------------------------------------------------------------------- #
COLORS = {
    "bg":            "#0e1013",   # window background
    "sidebar":       "#14171d",   # sidebar background
    "panel":         "#181b22",   # cards / panels
    "panel_alt":     "#1f232c",   # slightly raised surfaces
    "row":           "#161920",   # table row
    "row_hover":     "#1e222b",   # table row hover
    "row_selected":  "#232a3a",   # selected row tint
    "border":        "#262b35",   # subtle borders
    "border_light":  "#313846",
    "text":          "#e7ebf2",   # primary text
    "text_muted":    "#8b93a3",   # secondary text
    "text_faint":    "#5c6473",   # tertiary text
    "accent":        "#5b6cff",   # primary accent (indigo)
    "accent_hover":  "#6f7dff",
    "accent_dim":    "#2a2f52",
    "success":       "#34d399",
    "warning":       "#fbbf24",
    "danger":        "#f87171",
    "danger_hover":  "#ef4444",
}

# Category badge colours: (text/border colour, translucent-ish fill)
CATEGORY_COLORS = {
    CAT_SCRIPT: {"fg": "#60a5fa", "bg": "#17233b"},   # blue
    CAT_EDIT:   {"fg": "#a78bfa", "bg": "#241b3a"},   # purple
    CAT_THUMB:  {"fg": "#fbbf24", "bg": "#332812"},   # amber
}

STATUS_COLORS = {
    STATUS_READY:     "#34d399",
    STATUS_ANALYZING: "#fbbf24",
    STATUS_FAILED:    "#f87171",
}


# --------------------------------------------------------------------------- #
#  Typography
# --------------------------------------------------------------------------- #
FONT_FAMILY = "Segoe UI"

FONTS = {
    "title":     (FONT_FAMILY, 20, "bold"),
    "heading":   (FONT_FAMILY, 15, "bold"),
    "subheading":(FONT_FAMILY, 12, "bold"),
    "card_num":  (FONT_FAMILY, 26, "bold"),
    "card_label":(FONT_FAMILY, 11, "bold"),
    "body":      (FONT_FAMILY, 12),
    "body_bold": (FONT_FAMILY, 12, "bold"),
    "small":     (FONT_FAMILY, 11),
    "tiny":      (FONT_FAMILY, 10),
    "badge":     (FONT_FAMILY, 10, "bold"),
}


# --------------------------------------------------------------------------- #
#  Performance / like filter buckets
# --------------------------------------------------------------------------- #
VIEW_FILTERS = {
    "All":          None,
    "0–1K":         (0, 1_000),
    "1K–10K":       (1_000, 10_000),
    "10K–100K":     (10_000, 100_000),
    "100K–1M":      (100_000, 1_000_000),
    "1M+":          (1_000_000, None),
}

LIKE_FILTERS = {
    "All":     None,
    "0–100":   (0, 100),
    "100–1K":  (100, 1_000),
    "1K–10K":  (1_000, 10_000),
    "10K+":    (10_000, None),
}


# --------------------------------------------------------------------------- #
#  Number formatting
# --------------------------------------------------------------------------- #
def format_count(value) -> str:
    """
    Format a count intelligently:
        1200      -> 1.2K
        12500     -> 12.5K
        1250000   -> 1.3M
    Uses round-half-up so 1.25M renders as 1.3M.
    """
    if value is None:
        return "—"
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "—"

    if n < 0:
        return "—"
    if n < 1_000:
        return str(n)

    def _fmt(x: float, suffix: str) -> str:
        r = math.floor(x * 10 + 0.5) / 10.0        # round half up to 1 decimal
        s = f"{r:.1f}".rstrip("0").rstrip(".")
        return f"{s}{suffix}"

    if n < 1_000_000:
        return _fmt(n / 1_000.0, "K")
    if n < 1_000_000_000:
        return _fmt(n / 1_000_000.0, "M")
    return _fmt(n / 1_000_000_000.0, "B")


def in_range(value, bucket) -> bool:
    """Return True if value falls inside a (low, high] style filter bucket."""
    if bucket is None:
        return True
    if value is None:
        value = 0
    low, high = bucket
    if low is not None and value < low:
        return False
    if high is not None and value >= high:
        return False
    return True


# --------------------------------------------------------------------------- #
#  YouTube URL parsing
# --------------------------------------------------------------------------- #
_YT_ID_RE = re.compile(
    r"(?:v=|/shorts/|/embed/|/live/|youtu\.be/|/v/)([A-Za-z0-9_-]{11})"
)
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(text: str):
    """Extract an 11-character YouTube video id from a URL or bare id."""
    if not text:
        return None
    text = text.strip()
    m = _YT_ID_RE.search(text)
    if m:
        return m.group(1)
    if _BARE_ID_RE.match(text):
        return text
    return None


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def parse_links(raw: str):
    """
    Parse a blob of text into a de-duplicated list of (video_id, url) tuples.

    Accepts links separated by newlines, spaces or commas. Tokens that are not
    recognisable YouTube links are ignored.
    """
    if not raw:
        return []
    tokens = re.split(r"[\s,]+", raw.strip())
    seen = set()
    result = []
    for tok in tokens:
        if not tok:
            continue
        vid = extract_video_id(tok)
        if not vid or vid in seen:
            continue
        seen.add(vid)
        # keep the original url if it looked like a url, else canonical
        url = tok if tok.lower().startswith("http") else canonical_url(vid)
        result.append((vid, url))
    return result
