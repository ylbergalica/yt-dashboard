"""
The per-video edit dialog opened by double-click or the context menu.

If the URL is changed and saved, the caller is asked to re-analyze the new URL.
"""

import webbrowser

import customtkinter as ctk

import config
from ui_widgets import ImageCache


class EditWindow(ctk.CTkToplevel):
    def __init__(self, master, video, on_save, on_reanalyze):
        super().__init__(master)
        self.video = video
        self.on_save = on_save
        self.on_reanalyze = on_reanalyze
        self.image_cache = ImageCache(size=(240, 135))

        self.title("Edit Video")
        self.configure(fg_color=config.COLORS["bg"])
        self.geometry("520x640")
        self.resizable(False, False)
        self.transient(master)
        self.after(60, self._center_and_focus)

        self._build()

    def _center_and_focus(self):
        self.update_idletasks()
        try:
            self.grab_set()
        except Exception:
            pass
        self.lift()
        self.focus_force()

    # ------------------------------------------------------------------ #
    def _build(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            wrap, text="Edit Video", font=config.FONTS["title"],
            text_color=config.COLORS["text"],
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            wrap, text=f"Added {self.video.get('date_added','')}",
            font=config.FONTS["small"], text_color=config.COLORS["text_muted"],
        ).pack(anchor="w", pady=(0, 14))

        # thumbnail preview
        thumb = ctk.CTkLabel(
            wrap, text="", image=self.image_cache.get(self.video.get("thumbnail_path")),
        )
        thumb.pack(pady=(0, 16))

        # title
        self._field_label(wrap, "TITLE")
        self.title_entry = self._entry(wrap)
        self.title_entry.insert(0, self.video.get("title") or "")

        # url
        self._field_label(wrap, "YOUTUBE URL")
        self.url_entry = self._entry(wrap)
        self.url_entry.insert(0, self.video.get("url") or "")

        # category
        self._field_label(wrap, "CATEGORY")
        self.category_var = ctk.StringVar(value=self.video.get("category", config.DEFAULT_CATEGORY))
        self.category_menu = ctk.CTkOptionMenu(
            wrap, values=config.CATEGORIES, variable=self.category_var,
            fg_color=config.COLORS["panel_alt"],
            button_color=config.COLORS["accent"],
            button_hover_color=config.COLORS["accent_hover"],
            dropdown_fg_color=config.COLORS["panel_alt"],
            dropdown_hover_color=config.COLORS["accent"],
            text_color=config.COLORS["text"],
            font=config.FONTS["body"], height=36, corner_radius=8, anchor="w",
        )
        self.category_menu.pack(fill="x", pady=(4, 12))

        # read-only stats
        stats = ctk.CTkFrame(wrap, fg_color=config.COLORS["panel"], corner_radius=10)
        stats.pack(fill="x", pady=(4, 16))
        stats.grid_columnconfigure((0, 1, 2), weight=1)
        self._stat(stats, 0, "VIEWS", config.format_count(self.video.get("views")))
        self._stat(stats, 1, "LIKES", config.format_count(self.video.get("likes")))
        self._stat(stats, 2, "STATUS", self.video.get("status", ""))

        # buttons
        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(fill="x", side="bottom")
        btns.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btns, text="Save Changes", command=self._save,
            fg_color=config.COLORS["accent"], hover_color=config.COLORS["accent_hover"],
            font=config.FONTS["body_bold"], height=40, corner_radius=8,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ctk.CTkButton(
            btns, text="Re-analyze", command=self._reanalyze,
            fg_color=config.COLORS["panel_alt"], hover_color=config.COLORS["border_light"],
            font=config.FONTS["body"], height=36, corner_radius=8,
        ).grid(row=1, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            btns, text="Open YouTube", command=self._open,
            fg_color=config.COLORS["panel_alt"], hover_color=config.COLORS["border_light"],
            font=config.FONTS["body"], height=36, corner_radius=8,
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0))

        ctk.CTkButton(
            btns, text="Cancel", command=self.destroy,
            fg_color="transparent", hover_color=config.COLORS["panel_alt"],
            text_color=config.COLORS["text_muted"], font=config.FONTS["body"],
            height=32, corner_radius=8,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    # ------------------------------------------------------------------ #
    def _field_label(self, master, text):
        ctk.CTkLabel(
            master, text=text, font=config.FONTS["card_label"],
            text_color=config.COLORS["text_muted"], anchor="w",
        ).pack(anchor="w", pady=(6, 2))

    def _entry(self, master):
        e = ctk.CTkEntry(
            master, height=36, corner_radius=8,
            fg_color=config.COLORS["panel_alt"], border_color=config.COLORS["border"],
            text_color=config.COLORS["text"], font=config.FONTS["body"],
        )
        e.pack(fill="x", pady=(0, 6))
        return e

    def _stat(self, master, col, label, value):
        cell = ctk.CTkFrame(master, fg_color="transparent")
        cell.grid(row=0, column=col, sticky="ew", padx=8, pady=12)
        ctk.CTkLabel(cell, text=value, font=config.FONTS["subheading"],
                     text_color=config.COLORS["text"]).pack()
        ctk.CTkLabel(cell, text=label, font=config.FONTS["tiny"],
                     text_color=config.COLORS["text_muted"]).pack()

    # ------------------------------------------------------------------ #
    def _collect(self):
        return {
            "title": self.title_entry.get().strip(),
            "url": self.url_entry.get().strip(),
            "category": self.category_var.get(),
        }

    def _save(self):
        data = self._collect()
        url_changed = data["url"] != (self.video.get("url") or "")
        self.on_save(self.pk_or_none(), data, url_changed)
        self.destroy()

    def _reanalyze(self):
        data = self._collect()
        # persist current edits first, then re-analyze
        self.on_save(self.pk_or_none(), data, False)
        self.on_reanalyze(self.pk_or_none())
        self.destroy()

    def _open(self):
        url = self.url_entry.get().strip()
        if url:
            webbrowser.open(url)

    def pk_or_none(self):
        return self.video["id"]
