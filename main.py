"""
Entry point for the YouTube Content Dashboard.

Run directly with:  python main.py
Or build a standalone Windows executable with build.bat.
"""

import customtkinter as ctk

import config
from app import DashboardApp


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    app = DashboardApp()

    # Set a nicer default scaling on high-DPI Windows displays.
    try:
        app.tk.call("tk", "scaling", 1.25)
    except Exception:
        pass

    app.mainloop()


if __name__ == "__main__":
    main()
