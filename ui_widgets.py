"""
Reusable UI building blocks: thumbnail image cache, summary cards, category
badges and tooltips. Kept separate from the main window so app.py stays focused
on layout and behaviour.
"""

import tkinter as tk

import customtkinter as ctk

import config

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None


THUMB_SIZE = (96, 54)   # 16:9 preview used in the table


# --------------------------------------------------------------------------- #
#  Whole-widget interaction helper
# --------------------------------------------------------------------------- #
def _iter_descendants(widget):
    """Yield the widget and every widget nested inside it."""
    yield widget
    for child in widget.winfo_children():
        yield from _iter_descendants(child)


def _pointer_inside(widget) -> bool:
    """True if the mouse pointer is currently over `widget` or any descendant."""
    try:
        x, y = widget.winfo_pointerxy()
        under = widget.winfo_containing(x, y)
    except Exception:
        return False
    while under is not None:
        if under == widget:
            return True
        under = getattr(under, "master", None)
    return False


def bind_card(widget, on_enter=None, on_leave=None, on_click=None):
    """
    Make an entire composite widget behave as one hover/click target.

    Binding only the container is unreliable in Tk: <Leave> fires the moment the
    pointer crosses onto a child window. We bind every descendant and gate the
    real leave behind a pointer-containment check, so hover/click cover the
    whole visible area exactly.
    """
    def handle_enter(_e):
        if on_enter:
            on_enter()

    def handle_leave(_e):
        if on_leave and not _pointer_inside(widget):
            on_leave()

    def handle_click(_e):
        if on_click:
            on_click()

    for w in _iter_descendants(widget):
        w.bind("<Enter>", handle_enter, add="+")
        w.bind("<Leave>", handle_leave, add="+")
        if on_click:
            w.bind("<Button-1>", handle_click, add="+")


# --------------------------------------------------------------------------- #
#  Thumbnail image cache
# --------------------------------------------------------------------------- #
class ImageCache:
    """Loads, resizes and caches thumbnails as CTkImage objects."""

    def __init__(self, size=THUMB_SIZE):
        self.size = size
        self._cache = {}
        self._placeholder = None

    def placeholder(self):
        if self._placeholder is None:
            self._placeholder = self._make_placeholder()
        return self._placeholder

    def _make_placeholder(self):
        if Image is None:
            return None
        w, h = self.size
        img = Image.new("RGB", (w, h), self._hex(config.COLORS["panel_alt"]))
        if ImageDraw is not None:
            d = ImageDraw.Draw(img)
            # a subtle play triangle
            cx, cy = w // 2, h // 2
            r = min(w, h) // 5
            d.polygon(
                [(cx - r, cy - r), (cx - r, cy + r), (cx + r, cy)],
                fill=self._hex(config.COLORS["text_faint"]),
            )
        return ctk.CTkImage(light_image=img, dark_image=img, size=self.size)

    def get(self, path):
        if not path:
            return self.placeholder()
        if path in self._cache:
            return self._cache[path]
        if Image is None:
            return self.placeholder()
        try:
            img = Image.open(path).convert("RGB")
            img = self._fit_crop(img, self.size)
            ck = ctk.CTkImage(light_image=img, dark_image=img, size=self.size)
            self._cache[path] = ck
            return ck
        except Exception:  # noqa: BLE001
            return self.placeholder()

    @staticmethod
    def _fit_crop(img, size):
        tw, th = size
        w, h = img.size
        scale = max(tw / w, th / h)
        nw, nh = int(w * scale), int(h * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - tw) // 2
        top = (nh - th) // 2
        return img.crop((left, top, left + tw, top + th))

    @staticmethod
    def _hex(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# --------------------------------------------------------------------------- #
#  Summary card
# --------------------------------------------------------------------------- #
class SummaryCard(ctk.CTkFrame):
    """A large stat card: big number + label, used for the dashboard summary."""

    def __init__(self, master, label, accent=None, **kw):
        super().__init__(
            master,
            fg_color=config.COLORS["panel"],
            corner_radius=14,
            border_width=1,
            border_color=config.COLORS["border"],
            **kw,
        )
        accent = accent or config.COLORS["accent"]

        strip = ctk.CTkFrame(self, fg_color=accent, corner_radius=8, width=4)
        strip.place(relx=0.0, rely=0.22, relheight=0.56, x=10)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=(24, 18), pady=16)

        self.value_lbl = ctk.CTkLabel(
            inner, text="0", font=config.FONTS["card_num"],
            text_color=config.COLORS["text"], anchor="w",
        )
        self.value_lbl.pack(anchor="w")

        ctk.CTkLabel(
            inner, text=label.upper(), font=config.FONTS["card_label"],
            text_color=config.COLORS["text_muted"], anchor="w",
        ).pack(anchor="w", pady=(2, 0))

    def set_value(self, text):
        self.value_lbl.configure(text=text)


# --------------------------------------------------------------------------- #
#  Category summary card (smaller, clickable)
# --------------------------------------------------------------------------- #
class CategoryCard(ctk.CTkFrame):
    def __init__(self, master, category, on_click=None, **kw):
        super().__init__(
            master,
            fg_color=config.COLORS["panel"],
            corner_radius=12,
            border_width=1,
            border_color=config.COLORS["border"],
            **kw,
        )
        self.category = category
        self.on_click = on_click
        colors = config.CATEGORY_COLORS[category]

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        dot = ctk.CTkLabel(
            inner, text="●", font=(config.FONT_FAMILY, 13),
            text_color=colors["fg"], width=14,
        )
        dot.pack(side="left", padx=(0, 8))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_col, text=category, font=config.FONTS["small"],
            text_color=config.COLORS["text_muted"], anchor="w",
        ).pack(anchor="w")

        self.count_lbl = ctk.CTkLabel(
            text_col, text="0", font=config.FONTS["heading"],
            text_color=config.COLORS["text"], anchor="w",
        )
        self.count_lbl.pack(anchor="w")

        self._accent = colors["fg"]
        bind_card(
            self,
            on_enter=lambda: self.configure(border_color=self._accent),
            on_leave=lambda: self.configure(border_color=config.COLORS["border"]),
            on_click=self._clicked,
        )

    def _clicked(self):
        if self.on_click:
            self.on_click(self.category)

    def set_count(self, n):
        self.count_lbl.configure(text=str(n))


# --------------------------------------------------------------------------- #
#  Category badge (small coloured pill, optionally clickable to change)
# --------------------------------------------------------------------------- #
class CategoryBadge(ctk.CTkButton):
    def __init__(self, master, category, on_change=None, **kw):
        self.category = category
        self.on_change = on_change
        colors = config.CATEGORY_COLORS.get(category, config.CATEGORY_COLORS[config.CAT_SCRIPT])
        super().__init__(
            master,
            text=category,
            font=config.FONTS["badge"],
            fg_color=colors["bg"],
            hover_color=colors["bg"],
            text_color=colors["fg"],
            corner_radius=8,
            height=24,
            width=110,
            command=self._open_menu,
            **kw,
        )
        self._menu = None

    def _open_menu(self):
        if not self.on_change:
            return
        menu = tk.Menu(self, tearoff=0, bg=config.COLORS["panel_alt"],
                       fg=config.COLORS["text"],
                       activebackground=config.COLORS["accent"],
                       activeforeground="white", bd=0)
        for cat in config.CATEGORIES:
            menu.add_command(label=cat,
                             command=lambda c=cat: self.on_change(c))
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        menu.tk_popup(x, y)

    def set_category(self, category):
        self.category = category
        colors = config.CATEGORY_COLORS.get(category, config.CATEGORY_COLORS[config.CAT_SCRIPT])
        self.configure(text=category, fg_color=colors["bg"],
                       hover_color=colors["bg"], text_color=colors["fg"])


# --------------------------------------------------------------------------- #
#  Tooltip
# --------------------------------------------------------------------------- #
class Tooltip:
    """A lightweight hover tooltip for showing full titles."""

    def __init__(self, widget, text_provider):
        self.widget = widget
        self.text_provider = text_provider
        self.tip = None
        self._after = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._cancel()
        self._after = self.widget.after(600, self._show)

    def _cancel(self):
        if self._after:
            self.widget.after_cancel(self._after)
            self._after = None

    def _show(self):
        text = self.text_provider() if callable(self.text_provider) else self.text_provider
        if not text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(self.tip, bg=config.COLORS["border_light"], bd=0)
        frame.pack()
        tk.Label(
            frame, text=text, justify="left",
            bg=config.COLORS["panel_alt"], fg=config.COLORS["text"],
            font=config.FONTS["small"], wraplength=460,
            padx=10, pady=6, bd=0,
        ).pack(padx=1, pady=1)

    def _hide(self, _e=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None
