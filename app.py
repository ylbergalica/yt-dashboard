"""
Main application window for the YouTube Content Dashboard.

Layout
------
+----------+-------------------------------------------------------------+
| Sidebar  |  Add-videos panel                                            |
|          |  Summary cards + category cards                              |
|          |  Filter / search toolbar                                     |
|          |  (bulk action bar)                                           |
|          |  Table header                                                |
|          |  Scrollable video table  /  empty state                     |
+----------+-------------------------------------------------------------+
"""

import csv
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser

import customtkinter as ctk

import config
from database import Database
from analyzer import (AnalysisWorker, EVT_STARTED, EVT_RESULT, EVT_BATCH, EVT_IDLE)
from ui_widgets import ImageCache, SummaryCard, CategoryCard
from video_row import VideoRow, COLUMNS, configure_columns
from edit_window import EditWindow


SORT_KEYS = {
    "title": lambda v: (v.get("title") or v.get("url") or "").lower(),
    "category": lambda v: config.CATEGORIES.index(v["category"]) if v["category"] in config.CATEGORIES else 99,
    "views": lambda v: v.get("views") if v.get("views") is not None else -1,
    "likes": lambda v: v.get("likes") if v.get("likes") is not None else -1,
    "date_added": lambda v: v.get("date_added") or "",
}


class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.worker = AnalysisWorker()
        self.image_cache = ImageCache()

        self.videos = self.db.all_videos()
        self.rows = {}                     # pk -> VideoRow

        # filter / sort / search state
        self.filter_category = ctk.StringVar(value="All")
        self.filter_views = ctk.StringVar(value="All")
        self.filter_likes = ctk.StringVar(value="All")
        self.search_var = ctk.StringVar(value="")
        self.sort_key = "date_added"
        self.sort_desc = True

        self._build_window()
        self._build_sidebar()
        self._build_main()

        self.refresh_all()
        self.after(80, self._poll_worker)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================== #
    #  Window chrome
    # ================================================================== #
    def _build_window(self):
        self.title(config.APP_NAME)
        self.configure(fg_color=config.COLORS["bg"])
        self.geometry("1340x830")
        self.minsize(1180, 720)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    # ================================================================== #
    #  Sidebar
    # ================================================================== #
    def _build_sidebar(self):
        bar = ctk.CTkFrame(self, fg_color=config.COLORS["sidebar"], corner_radius=0, width=248)
        bar.grid(row=0, column=0, sticky="nsew")
        bar.grid_propagate(False)

        # brand
        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(22, 18))
        ctk.CTkLabel(brand, text="▶", font=(config.FONT_FAMILY, 20, "bold"),
                     text_color=config.COLORS["accent"]).pack(side="left", padx=(0, 8))
        title_col = ctk.CTkFrame(brand, fg_color="transparent")
        title_col.pack(side="left")
        ctk.CTkLabel(title_col, text="YouTube", font=(config.FONT_FAMILY, 14, "bold"),
                     text_color=config.COLORS["text"], anchor="w").pack(anchor="w")
        ctk.CTkLabel(title_col, text="Content Dashboard", font=config.FONTS["small"],
                     text_color=config.COLORS["text_muted"], anchor="w").pack(anchor="w")

        # Dashboard nav (All videos)
        self.nav_all = self._nav_item(bar, "  ▦   Dashboard", "All",
                                      is_all=True)

        ctk.CTkLabel(bar, text="WORK QUEUE", font=config.FONTS["tiny"],
                     text_color=config.COLORS["text_faint"], anchor="w"
                     ).pack(fill="x", padx=24, pady=(20, 6))

        self.nav_items = {}
        for cat in config.CATEGORIES:
            self.nav_items[cat] = self._nav_item(bar, cat, cat)

        # All videos count row
        ctk.CTkFrame(bar, fg_color=config.COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=(14, 8))
        self.nav_allvideos = self._nav_item(bar, "All Videos", "All")

        # footer
        footer = ctk.CTkFrame(bar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=16)
        ctk.CTkLabel(footer, text="Local library · auto-saved",
                     font=config.FONTS["tiny"], text_color=config.COLORS["text_faint"],
                     anchor="w").pack(anchor="w")

    def _nav_item(self, master, label, category, is_all=False):
        row = ctk.CTkFrame(master, fg_color="transparent", corner_radius=8, height=40)
        row.pack(fill="x", padx=12, pady=2)
        row.pack_propagate(False)

        name = ctk.CTkLabel(row, text=label, font=config.FONTS["body"],
                            text_color=config.COLORS["text_muted"], anchor="w")
        name.pack(side="left", padx=12)

        count = ctk.CTkLabel(row, text="", font=config.FONTS["small"],
                             text_color=config.COLORS["text_faint"])
        count.pack(side="right", padx=14)

        def enter(_e):
            if self.filter_category.get() != category or is_all:
                row.configure(fg_color=config.COLORS["panel_alt"])

        def leave(_e):
            self._restyle_nav()

        def click(_e):
            self.filter_category.set(category)
            self.cat_filter_menu.set(category if category in config.CATEGORIES else "All")
            self.refresh_all()

        for w in (row, name, count):
            w.bind("<Enter>", enter, add="+")
            w.bind("<Leave>", leave, add="+")
            w.bind("<Button-1>", click, add="+")

        row._name = name
        row._count = count
        row._category = category
        return row

    def _restyle_nav(self):
        active = self.filter_category.get()
        all_navs = [self.nav_all, self.nav_allvideos] + list(self.nav_items.values())
        for row in all_navs:
            is_active = (row._category == active)
            # "All" nav items only active when filter is All
            if row._category == "All":
                is_active = (active == "All")
            row.configure(fg_color=config.COLORS["accent_dim"] if is_active else "transparent")
            row._name.configure(
                text_color=config.COLORS["text"] if is_active else config.COLORS["text_muted"])

    # ================================================================== #
    #  Main area
    # ================================================================== #
    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=22, pady=18)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(5, weight=1)   # table row expands

        self._build_add_panel(main)
        self._build_summary(main)
        self._build_toolbar(main)
        self._build_bulk_bar(main)
        self._build_table_header(main)
        self._build_table(main)

    # ---- Add videos panel -------------------------------------------- #
    def _build_add_panel(self, master):
        panel = ctk.CTkFrame(master, fg_color=config.COLORS["panel"], corner_radius=14,
                             border_width=1, border_color=config.COLORS["border"])
        panel.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        panel.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 4))
        ctk.CTkLabel(head, text="Add Videos", font=config.FONTS["heading"],
                     text_color=config.COLORS["text"]).pack(side="left")
        ctk.CTkLabel(head, text="Paste YouTube links — one per line, or separated by spaces/commas",
                     font=config.FONTS["small"], text_color=config.COLORS["text_muted"]
                     ).pack(side="left", padx=12)

        body = ctk.CTkFrame(panel, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        body.grid_columnconfigure(0, weight=1)

        self.link_box = ctk.CTkTextbox(
            body, height=70, corner_radius=8, fg_color=config.COLORS["panel_alt"],
            border_width=1, border_color=config.COLORS["border"],
            text_color=config.COLORS["text"], font=config.FONTS["body"],
        )
        self.link_box.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        btncol = ctk.CTkFrame(body, fg_color="transparent")
        btncol.grid(row=0, column=1, sticky="ns")
        ctk.CTkButton(btncol, text="Analyze Links", command=self._on_analyze_clicked,
                      fg_color=config.COLORS["accent"], hover_color=config.COLORS["accent_hover"],
                      font=config.FONTS["body_bold"], height=40, width=140, corner_radius=8
                      ).pack(pady=(0, 6))
        ctk.CTkButton(btncol, text="Import file…", command=self._import_file,
                      fg_color=config.COLORS["panel_alt"], hover_color=config.COLORS["border_light"],
                      font=config.FONTS["body"], height=30, width=140, corner_radius=8
                      ).pack()

        # progress row (hidden unless a batch is running)
        self.progress_row = ctk.CTkFrame(panel, fg_color="transparent")
        self.progress_row.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        self.progress_row.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(self.progress_row, height=8, corner_radius=4,
                                           progress_color=config.COLORS["accent"],
                                           fg_color=config.COLORS["panel_alt"])
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.progress_lbl = ctk.CTkLabel(self.progress_row, text="", font=config.FONTS["small"],
                                         text_color=config.COLORS["text_muted"])
        self.progress_lbl.grid(row=0, column=1)
        self.progress_row.grid_remove()

    # ---- Summary cards ----------------------------------------------- #
    def _build_summary(self, master):
        wrap = ctk.CTkFrame(master, fg_color="transparent")
        wrap.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for i in range(6):
            wrap.grid_columnconfigure(i, weight=1, uniform="cards")

        self.card_videos = SummaryCard(wrap, "Videos", accent=config.COLORS["accent"])
        self.card_videos.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.card_views = SummaryCard(wrap, "Total Views", accent=config.COLORS["success"])
        self.card_views.grid(row=0, column=1, sticky="ew", padx=8)
        self.card_likes = SummaryCard(wrap, "Total Likes", accent=config.COLORS["danger"])
        self.card_likes.grid(row=0, column=2, sticky="ew", padx=8)

        self.cat_cards = {}
        for idx, cat in enumerate(config.CATEGORIES):
            card = CategoryCard(wrap, cat, on_click=self._filter_to_category)
            card.grid(row=0, column=3 + idx, sticky="ew",
                      padx=(8 if idx else 8, 0 if idx == 2 else 8))
            self.cat_cards[cat] = card

    # ---- Filter / search toolbar ------------------------------------- #
    def _build_toolbar(self, master):
        bar = ctk.CTkFrame(master, fg_color=config.COLORS["panel"], corner_radius=12,
                           border_width=1, border_color=config.COLORS["border"])
        bar.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        # search
        search = ctk.CTkEntry(inner, placeholder_text="Search title or URL…",
                              textvariable=self.search_var, width=240, height=34,
                              corner_radius=8, fg_color=config.COLORS["panel_alt"],
                              border_color=config.COLORS["border"],
                              text_color=config.COLORS["text"], font=config.FONTS["body"])
        search.pack(side="left", padx=(0, 14))
        self.search_var.trace_add("write", lambda *_: self.refresh_table())

        self.cat_filter_menu = self._filter_menu(
            inner, "Category", ["All"] + config.CATEGORIES, self.filter_category)
        self.view_filter_menu = self._filter_menu(
            inner, "Views", list(config.VIEW_FILTERS.keys()), self.filter_views)
        self.like_filter_menu = self._filter_menu(
            inner, "Likes", list(config.LIKE_FILTERS.keys()), self.filter_likes)

        ctk.CTkButton(inner, text="Clear", command=self._clear_filters, width=64, height=34,
                      fg_color="transparent", hover_color=config.COLORS["panel_alt"],
                      text_color=config.COLORS["text_muted"], font=config.FONTS["small"],
                      corner_radius=8).pack(side="left", padx=(6, 0))

        # right side: export
        ctk.CTkButton(inner, text="⇩  Export CSV", command=self._export_csv, width=120, height=34,
                      fg_color=config.COLORS["panel_alt"], hover_color=config.COLORS["border_light"],
                      text_color=config.COLORS["text"], font=config.FONTS["body"],
                      corner_radius=8).pack(side="right")

    def _filter_menu(self, master, label, values, variable):
        col = ctk.CTkFrame(master, fg_color="transparent")
        col.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(col, text=label, font=config.FONTS["tiny"],
                     text_color=config.COLORS["text_faint"], anchor="w").pack(anchor="w")
        menu = ctk.CTkOptionMenu(
            col, values=values, variable=variable, width=128, height=30,
            command=lambda *_: self._on_filter_menu_change(),
            fg_color=config.COLORS["panel_alt"], button_color=config.COLORS["border_light"],
            button_hover_color=config.COLORS["accent"],
            dropdown_fg_color=config.COLORS["panel_alt"],
            dropdown_hover_color=config.COLORS["accent"],
            text_color=config.COLORS["text"], font=config.FONTS["small"],
            corner_radius=8, anchor="w")
        menu.pack()
        return menu

    def _on_filter_menu_change(self):
        self._restyle_nav()
        self.refresh_table()
        self.refresh_summary()

    # ---- Bulk action bar --------------------------------------------- #
    def _build_bulk_bar(self, master):
        self.bulk_bar = ctk.CTkFrame(master, fg_color=config.COLORS["accent_dim"],
                                     corner_radius=10)
        # gridded/removed dynamically in row 3
        self.bulk_bar.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        inner = ctk.CTkFrame(self.bulk_bar, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=8)

        self.bulk_label = ctk.CTkLabel(inner, text="0 selected", font=config.FONTS["body_bold"],
                                       text_color=config.COLORS["text"])
        self.bulk_label.pack(side="left", padx=(0, 16))

        ctk.CTkButton(inner, text="Set Category ▾", command=self._bulk_category_menu,
                      width=130, height=32, corner_radius=8,
                      fg_color=config.COLORS["accent"], hover_color=config.COLORS["accent_hover"],
                      font=config.FONTS["small"]).pack(side="left", padx=4)
        ctk.CTkButton(inner, text="Re-analyze", command=self._bulk_reanalyze,
                      width=110, height=32, corner_radius=8,
                      fg_color=config.COLORS["panel_alt"], hover_color=config.COLORS["border_light"],
                      font=config.FONTS["small"]).pack(side="left", padx=4)
        ctk.CTkButton(inner, text="Remove", command=self._bulk_remove,
                      width=100, height=32, corner_radius=8,
                      fg_color=config.COLORS["danger"], hover_color=config.COLORS["danger_hover"],
                      font=config.FONTS["small"]).pack(side="left", padx=4)
        ctk.CTkButton(inner, text="Deselect all", command=lambda: self._select_all(False),
                      width=110, height=32, corner_radius=8,
                      fg_color="transparent", hover_color=config.COLORS["panel_alt"],
                      text_color=config.COLORS["text_muted"], font=config.FONTS["small"]
                      ).pack(side="right")
        self.bulk_bar.grid_remove()

    # ---- Table header ------------------------------------------------ #
    def _build_table_header(self, master):
        header = ctk.CTkFrame(master, fg_color="transparent", height=34)
        header.grid(row=4, column=0, sticky="ew", pady=(0, 4), padx=(2, 16))
        configure_columns(header)

        # select-all checkbox
        self.selectall_var = tk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(header, text="", variable=self.selectall_var, width=24,
                              checkbox_width=18, checkbox_height=18, corner_radius=5,
                              border_width=2, fg_color=config.COLORS["accent"],
                              hover_color=config.COLORS["accent_hover"],
                              border_color=config.COLORS["border_light"],
                              command=lambda: self._select_all(self.selectall_var.get()))
        chk.grid(row=0, column=0, padx=(6, 0))

        self._header_labels = {}
        specs = [
            (1, "", None),
            (2, "TITLE", "title"),
            (3, "CATEGORY", "category"),
            (4, "VIEWS", "views"),
            (5, "LIKES", "likes"),
            (6, "DATE ADDED", "date_added"),
            (7, "STATUS", None),
        ]
        for col, text, key in specs:
            anchor = COLUMNS[col][3]
            if key:
                btn = ctk.CTkButton(
                    header, text=text, command=lambda k=key: self._sort_by(k),
                    fg_color="transparent", hover_color=config.COLORS["panel_alt"],
                    text_color=config.COLORS["text_muted"], font=config.FONTS["tiny"],
                    height=26, corner_radius=6, anchor="w")
                btn.grid(row=0, column=col, sticky="ew", padx=2)
                self._header_labels[key] = btn
            elif text:
                ctk.CTkLabel(header, text=text, font=config.FONTS["tiny"],
                             text_color=config.COLORS["text_muted"], anchor="center"
                             ).grid(row=0, column=col, sticky="ew")
        self._update_sort_indicators()

    # ---- Scrollable table + empty state ------------------------------ #
    def _build_table(self, master):
        container = ctk.CTkFrame(master, fg_color=config.COLORS["panel"], corner_radius=14,
                                 border_width=1, border_color=config.COLORS["border"])
        container.grid(row=5, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.table = ctk.CTkScrollableFrame(container, fg_color="transparent",
                                            corner_radius=12)
        self.table.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # empty state (built once, shown/hidden)
        self.empty_state = ctk.CTkFrame(container, fg_color="transparent")
        es = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        es.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(es, text="▤", font=(config.FONT_FAMILY, 44),
                     text_color=config.COLORS["text_faint"]).pack(pady=(0, 8))
        self.empty_title = ctk.CTkLabel(es, text="No videos yet",
                                        font=config.FONTS["heading"],
                                        text_color=config.COLORS["text"])
        self.empty_title.pack()
        self.empty_sub = ctk.CTkLabel(
            es, text="Paste your YouTube links above to start building your content library.",
            font=config.FONTS["body"], text_color=config.COLORS["text_muted"])
        self.empty_sub.pack(pady=(4, 14))
        self.empty_btn = ctk.CTkButton(
            es, text="Add YouTube Videos", command=lambda: self.link_box.focus_set(),
            fg_color=config.COLORS["accent"], hover_color=config.COLORS["accent_hover"],
            font=config.FONTS["body_bold"], height=40, width=190, corner_radius=8)
        self.empty_btn.pack()
        self._table_container = container

    # ================================================================== #
    #  Rendering
    # ================================================================== #
    def refresh_all(self):
        self._restyle_nav()
        self.refresh_table()
        self.refresh_summary()
        self.refresh_sidebar_counts()

    def visible_videos(self):
        cat = self.filter_category.get()
        vb = config.VIEW_FILTERS.get(self.filter_views.get())
        lb = config.LIKE_FILTERS.get(self.filter_likes.get())
        q = self.search_var.get().strip().lower()

        out = []
        for v in self.videos:
            if cat != "All" and v["category"] != cat:
                continue
            if not config.in_range(v.get("views"), vb):
                continue
            if not config.in_range(v.get("likes"), lb):
                continue
            if q:
                hay = f"{v.get('title') or ''} {v.get('url') or ''}".lower()
                if q not in hay:
                    continue
            out.append(v)

        keyfn = SORT_KEYS.get(self.sort_key, SORT_KEYS["date_added"])
        out.sort(key=keyfn, reverse=self.sort_desc)
        return out

    def refresh_table(self):
        # clear existing rows
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()

        vids = self.visible_videos()

        if not self.videos:
            self.table.grid_remove()
            self.empty_title.configure(text="No videos yet")
            self.empty_sub.configure(
                text="Paste your YouTube links above to start building your content library.")
            self.empty_state.grid(row=0, column=0, sticky="nsew")
            self.refresh_summary()
            return

        if not vids:
            self.table.grid_remove()
            self.empty_title.configure(text="No matching videos")
            self.empty_sub.configure(text="Try adjusting your filters or search terms.")
            self.empty_state.grid(row=0, column=0, sticky="nsew")
            self.refresh_summary()
            return

        self.empty_state.grid_remove()
        self.table.grid()

        callbacks = {
            "set_category": self._set_category_single,
            "selection_changed": self._on_selection_changed,
            "edit": self.open_edit,
            "context_menu": self._show_context_menu,
        }
        for v in vids:
            row = VideoRow(self.table, v, self.image_cache, callbacks)
            row.pack(fill="x", pady=3, padx=2)
            self.rows[v["id"]] = row

        self.selectall_var.set(False)
        self._on_selection_changed()
        self.refresh_summary()

    def refresh_summary(self):
        vids = self.visible_videos()
        total_views = sum(v.get("views") or 0 for v in vids)
        total_likes = sum(v.get("likes") or 0 for v in vids)
        self.card_videos.set_value(str(len(vids)))
        self.card_views.set_value(config.format_count(total_views))
        self.card_likes.set_value(config.format_count(total_likes))

        counts = {c: 0 for c in config.CATEGORIES}
        for v in vids:
            if v["category"] in counts:
                counts[v["category"]] += 1
        for cat, card in self.cat_cards.items():
            card.set_count(counts[cat])

    def refresh_sidebar_counts(self):
        counts = self.db.category_counts()
        self.nav_all._count.configure(text=str(counts["__all__"]))
        self.nav_allvideos._count.configure(text=str(counts["__all__"]))
        for cat, row in self.nav_items.items():
            row._count.configure(text=str(counts.get(cat, 0)))

    # ---- sorting ----------------------------------------------------- #
    def _sort_by(self, key):
        if self.sort_key == key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key = key
            self.sort_desc = key in ("views", "likes", "date_added")
        self._update_sort_indicators()
        self.refresh_table()

    def _update_sort_indicators(self):
        labels = {"title": "TITLE", "category": "CATEGORY", "views": "VIEWS",
                  "likes": "LIKES", "date_added": "DATE ADDED"}
        for key, btn in self._header_labels.items():
            base = labels[key]
            if key == self.sort_key:
                arrow = "  ▼" if self.sort_desc else "  ▲"
                btn.configure(text=base + arrow, text_color=config.COLORS["accent"])
            else:
                btn.configure(text=base, text_color=config.COLORS["text_muted"])

    def _clear_filters(self):
        self.filter_category.set("All")
        self.filter_views.set("All")
        self.filter_likes.set("All")
        self.search_var.set("")
        self.cat_filter_menu.set("All")
        self._restyle_nav()
        self.refresh_all()

    def _filter_to_category(self, category):
        self.filter_category.set(category)
        self.cat_filter_menu.set(category)
        self._restyle_nav()
        self.refresh_table()
        self.refresh_summary()

    # ================================================================== #
    #  Selection & bulk actions
    # ================================================================== #
    def selected_pks(self):
        return [pk for pk, row in self.rows.items() if row.selected]

    def _on_selection_changed(self):
        pks = self.selected_pks()
        n = len(pks)
        if n:
            self.bulk_bar.grid()
            self.bulk_label.configure(text=f"{n} selected")
        else:
            self.bulk_bar.grid_remove()
        total = len(self.rows)
        self.selectall_var.set(n == total and total > 0)

    def _select_all(self, value):
        for row in self.rows.values():
            row.set_selected(value)
        self._on_selection_changed()

    def _bulk_category_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=config.COLORS["panel_alt"],
                       fg=config.COLORS["text"], activebackground=config.COLORS["accent"],
                       activeforeground="white", bd=0)
        for cat in config.CATEGORIES:
            menu.add_command(label=cat, command=lambda c=cat: self._apply_bulk_category(c))
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        menu.tk_popup(x, y)

    def _apply_bulk_category(self, category):
        pks = self.selected_pks()
        if not pks:
            return
        self.db.set_category_bulk(pks, category)
        for pk in pks:
            self._update_local_video(pk, category=category)
        self.refresh_all()

    def _bulk_reanalyze(self):
        pks = self.selected_pks()
        if not pks:
            return
        items = []
        for pk in pks:
            v = self._get_local_video(pk)
            if v:
                self.db.set_status(pk, config.STATUS_ANALYZING)
                self._update_local_video(pk, status=config.STATUS_ANALYZING)
                items.append((pk, v["url"]))
        self._patch_visible_statuses(pks)
        self.worker.enqueue_many(items)
        self._show_progress()

    def _bulk_remove(self):
        pks = self.selected_pks()
        if not pks:
            return
        if not messagebox.askyesno(
                "Remove videos",
                f"Remove {len(pks)} selected video(s) from your library?\n"
                "This cannot be undone.", parent=self):
            return
        self.db.delete_many(pks)
        self.videos = [v for v in self.videos if v["id"] not in pks]
        self.refresh_all()

    # ================================================================== #
    #  Context menu
    # ================================================================== #
    def _show_context_menu(self, pk, x, y):
        menu = tk.Menu(self, tearoff=0, bg=config.COLORS["panel_alt"],
                       fg=config.COLORS["text"], activebackground=config.COLORS["accent"],
                       activeforeground="white", bd=0)
        menu.add_command(label="Edit", command=lambda: self.open_edit(pk))
        menu.add_command(label="Open YouTube", command=lambda: self._open_youtube(pk))
        menu.add_command(label="Re-analyze", command=lambda: self._reanalyze(pk))
        menu.add_separator()

        sub = tk.Menu(menu, tearoff=0, bg=config.COLORS["panel_alt"], fg=config.COLORS["text"],
                      activebackground=config.COLORS["accent"], activeforeground="white", bd=0)
        for cat in config.CATEGORIES:
            sub.add_command(label=cat, command=lambda c=cat: self._set_category_single(pk, c))
        menu.add_cascade(label="Set Category", menu=sub)
        menu.add_separator()
        menu.add_command(label="Remove", command=lambda: self._remove_single(pk))
        menu.tk_popup(x, y)

    # ================================================================== #
    #  Single-video operations
    # ================================================================== #
    def _get_local_video(self, pk):
        for v in self.videos:
            if v["id"] == pk:
                return v
        return None

    def _update_local_video(self, pk, **fields):
        v = self._get_local_video(pk)
        if v:
            v.update(fields)
        return v

    def _replace_local_video(self, video):
        for i, v in enumerate(self.videos):
            if v["id"] == video["id"]:
                self.videos[i] = video
                return
        self.videos.insert(0, video)

    def _set_category_single(self, pk, category):
        self.db.set_category(pk, category)
        self._update_local_video(pk, category=category)
        if pk in self.rows:
            self.rows[pk].refresh(self._get_local_video(pk))
        self.refresh_summary()
        self.refresh_sidebar_counts()

    def _remove_single(self, pk):
        v = self._get_local_video(pk)
        title = (v.get("title") if v else None) or "this video"
        if not messagebox.askyesno("Remove video",
                                    f"Remove “{title[:60]}” from your library?", parent=self):
            return
        self.db.delete(pk)
        self.videos = [x for x in self.videos if x["id"] != pk]
        self.refresh_all()

    def _open_youtube(self, pk):
        v = self._get_local_video(pk)
        if v and v.get("url"):
            webbrowser.open(v["url"])

    def _reanalyze(self, pk):
        v = self._get_local_video(pk)
        if not v:
            return
        self.db.set_status(pk, config.STATUS_ANALYZING)
        self._update_local_video(pk, status=config.STATUS_ANALYZING)
        if pk in self.rows:
            self.rows[pk].refresh(v)
        self.worker.enqueue(pk, v["url"])
        self._show_progress()

    def open_edit(self, pk):
        v = self._get_local_video(pk)
        if not v:
            return
        EditWindow(self, dict(v), on_save=self._save_edit, on_reanalyze=self._reanalyze)

    def _save_edit(self, pk, data, url_changed):
        self.db.update_fields(pk, title=data["title"], url=data["url"],
                              category=data["category"])
        self._update_local_video(pk, title=data["title"], url=data["url"],
                                 category=data["category"])
        if pk in self.rows:
            self.rows[pk].refresh(self._get_local_video(pk))
        self.refresh_summary()
        self.refresh_sidebar_counts()
        if url_changed:
            self._reanalyze(pk)

    def _patch_visible_statuses(self, pks):
        for pk in pks:
            if pk in self.rows:
                self.rows[pk].refresh(self._get_local_video(pk))

    # ================================================================== #
    #  Add / analyze flow
    # ================================================================== #
    def _on_analyze_clicked(self):
        raw = self.link_box.get("1.0", "end")
        links = config.parse_links(raw)
        if not links:
            messagebox.showinfo("No links found",
                                "Paste one or more valid YouTube links first.", parent=self)
            return
        self.link_box.delete("1.0", "end")
        self._start_batch(links)

    def _start_batch(self, links):
        added = []
        skipped = 0
        for video_id, url in links:
            if self.db.exists_video_id(video_id):
                skipped += 1
                continue
            pk = self.db.add_pending(video_id, url)
            row = self.db.get(pk)
            self._replace_local_video(row)
            added.append((pk, url))

        self.refresh_all()
        if added:
            self.worker.enqueue_many(added)
            self._show_progress()
        if skipped and not added:
            messagebox.showinfo("Already in library",
                                f"{skipped} link(s) are already in your library.", parent=self)

    def _import_file(self):
        path = filedialog.askopenfilename(
            title="Import YouTube links",
            filetypes=[("Text/CSV", "*.txt *.csv"), ("All files", "*.*")], parent=self)
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        links = config.parse_links(content)
        if not links:
            messagebox.showinfo("No links found",
                                "That file didn't contain any recognizable YouTube links.",
                                parent=self)
            return
        self._start_batch(links)

    # ---- progress ---------------------------------------------------- #
    def _show_progress(self):
        self.progress_row.grid()

    def _hide_progress(self):
        self.progress_row.grid_remove()
        self.worker.reset_progress_if_idle()

    # ================================================================== #
    #  Worker polling (keeps the GUI responsive)
    # ================================================================== #
    def _poll_worker(self):
        try:
            while True:
                evt = self.worker.out.get_nowait()
                self._handle_event(evt)
        except Exception:
            pass
        self.after(80, self._poll_worker)

    def _handle_event(self, evt):
        kind = evt[0]
        if kind == EVT_BATCH:
            _, done, total = evt
            if total > 0:
                self.progress.set(done / total)
                self.progress_lbl.configure(text=f"Analyzing {done}/{total}")
                self._show_progress()
        elif kind == EVT_STARTED:
            pass
        elif kind == EVT_RESULT:
            _, pk, meta = evt
            self.db.apply_metadata(pk, meta)
            fresh = self.db.get(pk)
            if fresh:
                self._replace_local_video(fresh)
                if pk in self.rows:
                    self.rows[pk].refresh(fresh)
            self.refresh_summary()
            self.refresh_sidebar_counts()
        elif kind == EVT_IDLE:
            self.progress.set(1)
            self.progress_lbl.configure(text="Done")
            self.after(1200, self._hide_progress)
            # a final full refresh so newly analyzed rows re-sort/filter correctly
            self.after(60, self.refresh_table)

    # ================================================================== #
    #  Export
    # ================================================================== #
    def _export_csv(self):
        vids = self.visible_videos()
        if not vids:
            messagebox.showinfo("Nothing to export",
                                "There are no videos in the current view.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="Export filtered videos", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="youtube_library.csv", parent=self)
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Title", "URL", "Category", "Views", "Likes",
                                 "Date Added", "Status"])
                for v in vids:
                    writer.writerow([
                        v.get("title") or "", v.get("url") or "", v.get("category") or "",
                        v.get("views") if v.get("views") is not None else "",
                        v.get("likes") if v.get("likes") is not None else "",
                        v.get("date_added") or "", v.get("status") or "",
                    ])
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        messagebox.showinfo("Export complete",
                            f"Exported {len(vids)} video(s) to:\n{path}", parent=self)

    # ================================================================== #
    def _on_close(self):
        try:
            self.db.close()
        except Exception:
            pass
        self.destroy()
