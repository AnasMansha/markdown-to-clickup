"""
Markdown -> ClickUp desktop app.

Pick a .md file or paste Markdown, click "Copy for ClickUp",
then press Ctrl + V in a ClickUp Doc.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import mark
from mark import copy_to_clipboard, markdown_to_html


# Table header colors offered in the dropdown.
# You can also type any other color name ClickUp accepts.
HEADER_COLORS = [
    "orange",
    "red",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "gray",
    "None",
]


class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Markdown → ClickUp")
        self.geometry("720x520")
        self.minsize(480, 320)

        # ----------------------------------------------------
        # Top bar
        # ----------------------------------------------------

        top = ttk.Frame(self, padding=(10, 10, 10, 0))
        top.pack(fill="x")

        ttk.Button(
            top,
            text="Open .md file…",
            command=self.open_file
        ).pack(side="left")

        ttk.Button(
            top,
            text="Clear",
            command=self.clear
        ).pack(side="left", padx=(6, 0))

        self.file_label = ttk.Label(
            top,
            text="…or paste Markdown below",
            foreground="gray"
        )
        self.file_label.pack(side="left", padx=10)

        # ----------------------------------------------------
        # Markdown text area
        # ----------------------------------------------------

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(body)
        scrollbar.pack(side="right", fill="y")

        self.text = tk.Text(
            body,
            wrap="word",
            undo=True,
            font=("Consolas", 10),
            yscrollcommand=scrollbar.set
        )
        self.text.pack(fill="both", expand=True)

        scrollbar.config(command=self.text.yview)

        # ----------------------------------------------------
        # Bottom bar
        # ----------------------------------------------------

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")

        self.status = ttk.Label(bottom, text="")
        self.status.pack(side="left")

        ttk.Button(
            bottom,
            text="Copy for ClickUp",
            command=self.convert
        ).pack(side="right")

        # Table header color
        self.header_color = tk.StringVar(
            value=mark.HEADER_COLOR or "None"
        )

        ttk.Combobox(
            bottom,
            textvariable=self.header_color,
            values=HEADER_COLORS,
            width=10
        ).pack(side="right", padx=(0, 12))

        ttk.Label(
            bottom,
            text="Table header color:"
        ).pack(side="right", padx=(0, 4))

        # Ctrl+Enter = convert
        self.bind("<Control-Return>", lambda e: self.convert())

        self.text.focus_set()

    # --------------------------------------------------------
    # Actions
    # --------------------------------------------------------

    def open_file(self):

        path = filedialog.askopenfilename(
            title="Select a Markdown file",
            filetypes=[
                ("Markdown", "*.md *.markdown"),
                ("All files", "*.*")
            ]
        )

        if not path:
            return

        try:
            content = Path(path).read_text(encoding="utf-8")
        except Exception as error:
            messagebox.showerror("Could not read file", str(error))
            return

        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)

        self.file_label.config(
            text=Path(path).name,
            foreground=""
        )

        self.set_status("")

    def clear(self):

        self.text.delete("1.0", "end")

        self.file_label.config(
            text="…or paste Markdown below",
            foreground="gray"
        )

        self.set_status("")

    def convert(self):

        markdown = self.text.get("1.0", "end-1c")

        if not markdown.strip():
            self.set_status("Nothing to convert.", "red")
            return

        color = self.header_color.get().strip()

        mark.HEADER_COLOR = (
            ""
            if color.lower() in ("", "none")
            else color
        )

        try:
            html = markdown_to_html(markdown)
            copy_to_clipboard(html, markdown)
        except Exception as error:
            messagebox.showerror("Conversion failed", str(error))
            return

        self.set_status(
            "✓ Copied! Now press Ctrl + V in ClickUp.",
            "green"
        )

    def set_status(self, message, color=""):
        self.status.config(text=message, foreground=color)


if __name__ == "__main__":
    App().mainloop()
