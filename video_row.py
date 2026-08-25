"""
A single row in the video table. Rows are kept in a registry (pk -> VideoRow) by
the main window so that live analysis updates can patch one row in place without
rebuilding the whole list.
"""

import tkinter as tk

import customtkinter as ctk

import config
from ui_widgets import CategoryBadge, Tooltip


# Shared column layout — used by both the header and every row so they align.
#   key, weight, minsize (px), anchor
COLUMNS = [
    ("select", 0, 34,  "center"),
    ("thumb",  0, 112, "center"),
    ("title",  1, 240, "w"),
    ("category", 0, 132, "center"),
    ("views",  0, 92,  "e"),
    ("likes",  0, 92,  "e"),
    ("date",   0, 118, "center"),
    ("status", 0, 132, "center"),
]


def configure_columns(frame):
    for i, (_key, weight, minsize, _anchor) in enumerate(COLUMNS):
        frame.grid_columnconfigure(i, weight=weight, minsize=minsize)


def truncate(text, limit=52):
    if text and len(text) > limit:
        return text[: limit - 1] + "…"
    return text


class VideoRow(ctk.CTkFrame):
    def __init__(self, master, video, image_cache, callbacks):
        super().__init__(
            master,
            fg_color=config.COLORS["row"],
            corner_radius=10,
            height=68,
        )
        self.video = video
        self.pk = video["id"]
        self.image_cache = image_cache
        self.cb = callbacks           # dict of callbacks provided by the app
        self.selected = False
        self.grid_propagate(False)

        configure_columns(self)

        # --- selection checkbox ------------------------------------------- #
        self.sel_var = tk.BooleanVar(value=False)
        self.check = ctk.CTkCheckBox(
            self, text="", variable=self.sel_var, width=24,
            checkbox_width=18, checkbox_height=18,
            corner_radius=5, border_width=2,
            fg_color=config.COLORS["accent"],
            hover_color=config.COLORS["accent_hover"],
            border_color=config.COLORS["border_light"],
            command=self._on_check,
        )
        self.check.grid(row=0, column=0, padx=(6, 0), pady=8)

        # --- thumbnail ---------------------------------------------------- #
        self.thumb_lbl = ctk.CTkLabel(
            self, text="", image=self.image_cache.get(video.get("thumbnail_path")),
        )
        self.thumb_lbl.grid(row=0, column=1, padx=4, pady=8)

        # --- title -------------------------------------------------------- #
        self.title_lbl = ctk.CTkLabel(
            self, text=self._title_text(), anchor="w",
            font=config.FONTS["body_bold"], text_color=config.COLORS["text"],
            justify="left",
        )
        self.title_lbl.grid(row=0, column=2, sticky="ew", padx=(6, 10), pady=8)
        Tooltip(self.title_lbl, lambda: self.video.get("title") or self.video.get("url"))

        # --- category badge ----------------------------------------------- #
        self.badge = CategoryBadge(
            self, video["category"],
            on_change=lambda c: self.cb["set_category"](self.pk, c),
        )
        self.badge.grid(row=0, column=3, padx=4, pady=8)

        # --- views / likes ------------------------------------------------ #
        self.views_lbl = ctk.CTkLabel(
            self, text=config.format_count(video.get("views")), anchor="e",
            font=config.FONTS["body"], text_color=config.COLORS["text"], width=80,
        )
        self.views_lbl.grid(row=0, column=4, sticky="e", padx=6, pady=8)

        self.likes_lbl = ctk.CTkLabel(
            self, text=config.format_count(video.get("likes")), anchor="e",
            font=config.FONTS["body"], text_color=config.COLORS["text"], width=80,
        )
        self.likes_lbl.grid(row=0, column=5, sticky="e", padx=6, pady=8)

        # --- date --------------------------------------------------------- #
        self.date_lbl = ctk.CTkLabel(
            self, text=video.get("date_added", ""), anchor="center",
            font=config.FONTS["small"], text_color=config.COLORS["text_muted"],
        )
        self.date_lbl.grid(row=0, column=6, padx=4, pady=8)

        # --- status ------------------------------------------------------- #
        self.status_lbl = ctk.CTkLabel(
            self, text="", anchor="center", font=config.FONTS["small"],
        )
        self.status_lbl.grid(row=0, column=7, padx=4, pady=8)
        self._render_status()

        # --- interactions ------------------------------------------------- #
        self._bind_all_children()

    # ------------------------------------------------------------------ #
    #  Rendering helpers
    # ------------------------------------------------------------------ #
    def _title_text(self):
        status = self.video.get("status")
        if status == config.STATUS_ANALYZING and not self.video.get("title"):
            return "Analyzing…"
        title = self.video.get("title") or self.video.get("url") or "(untitled)"
        return truncate(title)

    def _render_status(self):
        status = self.video.get("status", config.STATUS_READY)
        color = config.STATUS_COLORS.get(status, config.COLORS["text_muted"])
        dot = {"Ready": "●  ", "Analyzing...": "◐  ", "Analysis Failed": "▲  "}.get(status, "● ")
        self.status_lbl.configure(text=dot + status, text_color=color)

    # ------------------------------------------------------------------ #
    #  Live in-place updates
    # ------------------------------------------------------------------ #
    def refresh(self, video):
        self.video = video
        self.thumb_lbl.configure(image=self.image_cache.get(video.get("thumbnail_path")))
        self.title_lbl.configure(text=self._title_text())
        self.badge.set_category(video["category"])
        self.views_lbl.configure(text=config.format_count(video.get("views")))
        self.likes_lbl.configure(text=config.format_count(video.get("likes")))
        self.date_lbl.configure(text=video.get("date_added", ""))
        self._render_status()

    # ------------------------------------------------------------------ #
    #  Selection
    # ------------------------------------------------------------------ #
    def set_selected(self, value, silent=False):
        self.selected = value
        self.sel_var.set(value)
        self.configure(
            fg_color=config.COLORS["row_selected"] if value else config.COLORS["row"]
        )

    def _on_check(self):
        self.selected = self.sel_var.get()
        self.configure(
            fg_color=config.COLORS["row_selected"] if self.selected else config.COLORS["row"]
        )
        self.cb["selection_changed"]()

    # ------------------------------------------------------------------ #
    #  Mouse / hover / context menu
    # ------------------------------------------------------------------ #
    def _bind_all_children(self):
        targets = [self, self.thumb_lbl, self.title_lbl, self.views_lbl,
                   self.likes_lbl, self.date_lbl, self.status_lbl]
        for w in targets:
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<Double-Button-1>", self._on_double, add="+")
            w.bind("<Button-3>", self._on_right, add="+")

    def _on_enter(self, _e):
        if not self.selected:
            self.configure(fg_color=config.COLORS["row_hover"])

    def _on_leave(self, _e):
        if not self.selected:
            self.configure(fg_color=config.COLORS["row"])

    def _on_double(self, _e):
        self.cb["edit"](self.pk)

    def _on_right(self, event):
        self.cb["context_menu"](self.pk, event.x_root, event.y_root)
