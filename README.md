# YouTube Content Dashboard

A polished, dark-themed **Windows desktop application** for managing a YouTube
video production pipeline — think Notion / Linear / Premiere Pro for your content
backlog. Paste YouTube links, let the app analyze them with **yt-dlp** (no API
key required), organize everything into work-queue categories, and track your
views/likes at a glance.

![platform](https://img.shields.io/badge/platform-Windows-blue) ![python](https://img.shields.io/badge/python-3.9%2B-green) ![no api key](https://img.shields.io/badge/YouTube_API_key-not_required-success)

---

## Table of contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick start (run from source)](#quick-start-run-from-source)
- [Building the standalone Windows .exe](#building-the-standalone-windows-exe)
- [Using the app](#using-the-app)
- [Where your data lives](#where-your-data-lives)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Batch link import** — paste many links at once (one per line, or separated
  by spaces/commas), then click **Analyze Links**. A progress bar shows batch
  progress and a single failing video never aborts the rest.
- **Automatic metadata** via yt-dlp: title, view count, like count, thumbnail,
  video ID — **no API key needed**.
- **Persistent library** — everything is stored in SQLite and saved immediately,
  so your library, categories and metadata survive restarts and crashes.
- **Categories** (`Script Writing`, `Video Editing`, `Thumbnail Design`) editable
  four ways: the edit window, a click-to-change badge in the table, the
  right-click menu, and multi-select bulk change.
- **Filtering** by category, view buckets and like buckets — all combinable —
  plus a live **search** over title and URL. Dashboard stats update to match.
- **Sorting** on Title, Category, Views, Likes and Date Added with a clear
  ascending/descending indicator.
- **Professional table** with cached thumbnail previews, colored category
  badges, humanized numbers (`1.2K`, `12.5K`, `1.3M`), truncated titles with
  full-title tooltips, and clear status states.
- **Dashboard summary cards** (Videos / Total Views / Total Likes) plus
  per-category counts, all reflecting the current filtered view.
- **Sidebar work queue** with per-category counts that filter the table on click.
- **Bulk actions** — select all, remove, change category, re-analyze (with a
  confirmation before removing).
- **Edit window** (double-click a row) with thumbnail, editable title/URL,
  category dropdown, read-only stats, and Save / Re-analyze / Open YouTube /
  Cancel. Changing the URL re-analyzes it.
- **Import** a `.txt` / `.csv` of URLs and **export** the filtered view to CSV.
- **Responsive UI** — all analysis runs on a background thread; the interface
  never freezes.
- **Empty / loading / error states** throughout.

---

## Prerequisites

You only need this to **run from source** or **build the .exe**. The finished
`.exe` itself needs nothing installed.

1. **Windows 10 / 11.**
2. **Python 3.9 or newer** — download from <https://www.python.org/downloads/>.

   > ⚠️ **Important:** during installation, tick **“Add Python to PATH”.**
   >
   > If you skip this, Windows may only expose the Microsoft Store *alias* stubs.
   > Verify a real interpreter is on your PATH by opening a **new** terminal and
   > running:
   > ```bat
   > python --version
   > ```
   > You should see something like `Python 3.12.x`. If instead you get
   > *“Python was not found; run without arguments to install from the Microsoft
   > Store”*, Python isn’t properly on your PATH — reinstall with the checkbox
   > ticked, or disable the aliases in
   > **Settings → Apps → Advanced app settings → App execution aliases**.

3. **An internet connection** (yt-dlp fetches metadata live from YouTube).

---

## Quick start (run from source)

From the project folder (`yt-dashboard`), open a terminal and run:

```bat
:: 1. (recommended) create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

:: 2. install dependencies
pip install -r requirements.txt

:: 3. launch the app
python main.py
```

That’s it — the dashboard window opens. Paste some YouTube links into the
**Add Videos** box and click **Analyze Links**.

> Not using a venv? You can skip step 1 and just run `pip install -r requirements.txt`
> followed by `python main.py`.

**Dependencies** (also in [`requirements.txt`](requirements.txt)):

| Package | Purpose |
|---------|---------|
| `customtkinter` | Modern dark-themed GUI |
| `yt-dlp` | YouTube metadata extraction (no API key) |
| `Pillow` | Thumbnail loading/resizing |

---

## Building the standalone Windows .exe

To produce a single, self-contained executable that runs on machines **without
Python installed**, just double-click **`build.bat`** or run it from a terminal:

```bat
build.bat
```

The script will:

1. Upgrade `pip`.
2. Install/update the app dependencies (`customtkinter`, `yt-dlp`, `Pillow`).
3. Install/update **PyInstaller**.
4. Build the app with:
   ```bat
   pyinstaller --onefile --windowed --collect-all customtkinter --collect-all yt_dlp main.py
   ```

**Final output:**

```
dist\YouTubeContentDashboard.exe
```

Double-click that `.exe` to run the app anywhere — no Python required. (First
launch is a little slower because a one-file build unpacks itself to a temp
folder.)

> **Build tips**
> - Run `build.bat` from the project folder so it can find `main.py`.
> - The `--collect-all` flags are essential: CustomTkinter and yt-dlp ship data
>   files that must be bundled, or the packaged app will fail to start.
> - Some antivirus tools flag PyInstaller one-file executables as suspicious
>   (a well-known false positive). If that happens, add an exclusion, or edit
>   `build.bat` to use `--onedir` instead of `--onefile`.

---

## Using the app

| I want to… | How |
|------------|-----|
| **Add videos** | Paste links into the *Add Videos* box (one per line, or comma/space separated) → **Analyze Links**. |
| **Import a file of links** | *Add Videos* panel → **Import file…** (accepts `.txt` / `.csv`). |
| **Change one video’s category** | Click its colored badge in the table, use the right-click menu, or the edit window. |
| **Change many at once** | Tick the checkboxes → the bulk bar appears → **Set Category**. |
| **Filter** | Use the Category / Views / Likes dropdowns (they combine) or click a sidebar category. |
| **Search** | Type in the search box — matches title and URL, and stacks with filters. |
| **Sort** | Click a column header; click again to reverse. |
| **Edit a video** | Double-click its row (or right-click → Edit). |
| **Re-analyze** | Right-click → Re-analyze, the edit window, or bulk re-analyze. |
| **Open on YouTube** | Right-click → Open YouTube (or the button in the edit window). |
| **Remove** | Right-click → Remove, or select several → **Remove** (asks to confirm). |
| **Export** | Toolbar → **Export CSV** (exports the current filtered view). |

Analysis statuses: **Analyzing…** → **Ready**, or **Analysis Failed** (which you
can retry via Re-analyze).

---

## Where your data lives

Everything is stored locally and saved automatically:

```
%APPDATA%\YouTubeContentDashboard\
├── library.db          (SQLite database — your videos, categories, metadata)
└── thumbnails\         (cached thumbnail images)
```

Your library, categories and metadata persist across restarts. Because every
change is committed to SQLite immediately, nothing is lost if the app is closed
or crashes mid-analysis. Deleting that folder resets the app to a clean state.

---

## Project structure

| File | Responsibility |
|------|----------------|
| [`main.py`](main.py) | Entry point; sets theme and starts the app. |
| [`app.py`](app.py) | Main window: sidebar, toolbar, summary cards, table, all behaviour. |
| [`config.py`](config.py) | Paths, theme colors, categories, number/URL formatting helpers. |
| [`database.py`](database.py) | SQLite persistence (thread-safe, commits immediately). |
| [`analyzer.py`](analyzer.py) | Background yt-dlp worker + thumbnail caching. |
| [`ui_widgets.py`](ui_widgets.py) | Reusable widgets: image cache, summary/category cards, badges, tooltips. |
| [`video_row.py`](video_row.py) | A single table row and the shared column layout. |
| [`edit_window.py`](edit_window.py) | The per-video edit dialog. |
| [`build.bat`](build.bat) | Windows build script (PyInstaller). |
| [`requirements.txt`](requirements.txt) | Python dependencies. |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Python was not found…` when running `python` or `build.bat` | Python isn’t on your PATH. Reinstall from python.org with **“Add Python to PATH”** ticked, or disable the Store aliases (see [Prerequisites](#prerequisites)). |
| App window doesn’t open / `ModuleNotFoundError` | Dependencies aren’t installed. Run `pip install -r requirements.txt`. |
| A video shows **Analysis Failed** | The video may be private/removed/age-restricted, or yt-dlp is out of date. Update it: `pip install -U yt-dlp`, then Re-analyze. YouTube changes often; keeping yt-dlp current fixes most failures. |
| Likes show `—` | Like counts aren’t always public; yt-dlp can only report what’s available. |
| Packaged `.exe` won’t start | Rebuild with the `--collect-all customtkinter --collect-all yt_dlp` flags (already in `build.bat`). |
| Antivirus flags the `.exe` | Known PyInstaller false positive — add an exclusion or build with `--onedir`. |
| First `.exe` launch is slow | Normal for `--onefile` builds (it unpacks to a temp folder on start). |
