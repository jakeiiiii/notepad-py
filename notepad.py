#!/usr/bin/env python3
"""Notepad - a Python/Tkinter clone of Windows Notepad.

Single file, standard library only. Runs on macOS, Windows and Linux:

    python3 notepad.py [file]
"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import tkinter as tk
import urllib.parse
import webbrowser
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

APP_NAME = "Notepad"
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# Tk modifier name / label shown in menus
MOD = "Command" if IS_MAC else "Control"
MOD_LABEL = "Command" if IS_MAC else "Ctrl"

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".notepad_py.json")

# (name shown to the user, codec, byte-order mark written at the start of the file)
ENCODINGS = [
    ("ANSI", "cp1252", b""),
    ("UTF-16 LE", "utf-16-le", b"\xff\xfe"),
    ("UTF-16 BE", "utf-16-be", b"\xfe\xff"),
    ("UTF-8", "utf-8", b""),
    ("UTF-8 with BOM", "utf-8", b"\xef\xbb\xbf"),
]
LINE_ENDINGS = {
    "\r\n": "Windows (CRLF)",
    "\n": "Unix (LF)",
    "\r": "Macintosh (CR)",
}
DEFAULT_EOL = "\r\n" if IS_WIN else "\n"

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 10, 500, 10
FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
FONT_STYLES = ["Regular", "Italic", "Bold", "Bold Italic"]
PAPER_SIZES = {"Letter": (8.5, 11.0), "A4": (8.27, 11.69), "Legal": (8.5, 14.0)}

DEFAULT_SETTINGS = {
    "font_family": "Menlo" if IS_MAC else "Consolas" if IS_WIN else "DejaVu Sans Mono",
    "font_size": 12 if IS_MAC else 11,
    "font_style": "Regular",
    "word_wrap": False,
    "status_bar": True,
    "geometry": "900x600",
    "header": "&f",
    "footer": "Page &p",
    "paper": "Letter",
    "orientation": "Portrait",
    "margins": [0.75, 0.75, 1.0, 1.0],  # left, right, top, bottom (inches)
}


# ── Files: encodings and line endings ────────────────────────────


def decode_bytes(data: bytes) -> tuple[str, str]:
    """Returns (text, encoding name), detecting the encoding like Notepad does."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace"), "UTF-8 with BOM"
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16-le", errors="replace"), "UTF-16 LE"
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be", errors="replace"), "UTF-16 BE"
    try:
        return data.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "ANSI"


def encode_text(text: str, encoding_name: str) -> bytes:
    for name, codec, bom in ENCODINGS:
        if name == encoding_name:
            return bom + text.encode(codec, errors="replace")
    raise ValueError(f"Unknown encoding: {encoding_name}")


def detect_eol(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    if "\n" in text:
        return "\n"
    return DEFAULT_EOL


def normalize_eol(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def time_date_string(now: datetime.datetime | None = None) -> str:
    """Same format as Notepad's F5: 1:05 PM 9/20/2026"""
    now = now or datetime.datetime.now()
    hour = now.hour % 12 or 12
    return f"{hour}:{now:%M} {now:%p} {now.month}/{now.day}/{now.year}"


# ── Printing: Notepad-style header/footer codes and pagination ───


def expand_header(template: str, filename: str, page: int, width: int) -> str:
    """Expands &f &p &d &t && and the alignment codes &l &c &r into one line."""
    now = datetime.datetime.now()
    parts = {"l": "", "c": "", "r": ""}
    align = "c"
    i = 0
    while i < len(template):
        ch = template[i]
        if ch == "&" and i + 1 < len(template):
            code = template[i + 1]
            i += 2
            if code.lower() in parts:
                align = code.lower()
            elif code.lower() == "f":
                parts[align] += filename
            elif code.lower() == "p":
                parts[align] += str(page)
            elif code.lower() == "d":
                parts[align] += f"{now.month}/{now.day}/{now.year}"
            elif code.lower() == "t":
                parts[align] += time_date_string(now).rsplit(" ", 1)[0]
            elif code == "&":
                parts[align] += "&"
            continue
        parts[align] += ch
        i += 1

    line = list(" " * width)
    center_start = max(0, (width - len(parts["c"])) // 2)
    for start, s in (
        (0, parts["l"]),
        (center_start, parts["c"]),
        (max(0, width - len(parts["r"])), parts["r"]),
    ):
        for offset, c in enumerate(s[: width - start]):
            line[start + offset] = c
    return "".join(line).rstrip()


def paginate(text: str, filename: str, settings: dict, cpi=10, lpi=6) -> str:
    """Lays the document out in fixed-pitch pages separated by form feeds."""
    paper_w, paper_h = PAPER_SIZES.get(settings["paper"], PAPER_SIZES["Letter"])
    if settings["orientation"] == "Landscape":
        paper_w, paper_h = paper_h, paper_w
    left, right, top, bottom = settings["margins"]
    cols = max(20, int((paper_w - left - right) * cpi))
    rows = max(10, int((paper_h - top - bottom) * lpi) - 1)

    header, footer = settings["header"], settings["footer"]
    body_rows = rows - (2 if header else 0) - (2 if footer else 0)

    lines = []
    for line in text.split("\n"):
        line = line.expandtabs(8)
        while len(line) > cols:
            lines.append(line[:cols])
            line = line[cols:]
        lines.append(line)

    pages = []
    for page_no, start in enumerate(range(0, max(len(lines), 1), body_rows), 1):
        body = lines[start : start + body_rows]
        out = []
        if header:
            out += [expand_header(header, filename, page_no, cols), ""]
        out += body
        if footer:
            out += [""] * (body_rows - len(body))
            out += ["", expand_header(footer, filename, page_no, cols)]
        pages.append("\n".join(out))
    return "\f".join(pages)


def list_printers() -> tuple[list[str], str | None]:
    """CUPS printers (macOS/Linux). Returns (names, default name)."""
    names, default = [], None
    try:
        out = subprocess.run(
            ["lpstat", "-a"], capture_output=True, text=True, timeout=5
        ).stdout
        names = [line.split()[0] for line in out.splitlines() if line.strip()]
        out = subprocess.run(
            ["lpstat", "-d"], capture_output=True, text=True, timeout=5
        ).stdout
        if ":" in out:
            default = out.split(":", 1)[1].strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    return names, default


# ── Dialogs ──────────────────────────────────────────────────────


class Dialog(tk.Toplevel):
    """Base for the small fixed-size dialogs."""

    def __init__(self, app, title, modal=False):
        super().__init__(app.root)
        self.app = app
        self.title(title)
        self.resizable(False, False)
        self.transient(app.root)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda e: self.close())
        self.body = ttk.Frame(self, padding=12)
        self.body.pack(fill=tk.BOTH, expand=True)
        self._modal = modal

    def show(self):
        self.update_idletasks()
        root = self.app.root
        x = root.winfo_rootx() + 60
        y = root.winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")
        if self._modal:
            self.grab_set()
            self.wait_window()

    def close(self):
        self.destroy()


class FindDialog(Dialog):
    """Find, or Find + Replace when replace=True. Non-modal, like Notepad."""

    def __init__(self, app, replace=False):
        super().__init__(app, "Replace" if replace else "Find")
        self.replace_mode = replace
        body = self.body

        ttk.Label(body, text="Find what:").grid(row=0, column=0, sticky="w", pady=3)
        self.find_var = tk.StringVar(value=app.find_term)
        self.find_entry = ttk.Entry(body, textvariable=self.find_var, width=32)
        self.find_entry.grid(row=0, column=1, columnspan=2, sticky="we", padx=6)

        self.replace_var = tk.StringVar(value=app.replace_term)
        if replace:
            ttk.Label(body, text="Replace with:").grid(row=1, column=0, sticky="w", pady=3)
            ttk.Entry(body, textvariable=self.replace_var, width=32).grid(
                row=1, column=1, columnspan=2, sticky="we", padx=6
            )

        self.case_var = tk.BooleanVar(value=app.find_match_case)
        self.wrap_var = tk.BooleanVar(value=app.find_wrap)
        self.down_var = tk.BooleanVar(value=app.find_down)
        options = ttk.Frame(body)
        options.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(options, text="Match case", variable=self.case_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Wrap around", variable=self.wrap_var).pack(anchor="w")

        if not replace:
            direction = ttk.LabelFrame(body, text="Direction", padding=(8, 2))
            direction.grid(row=2, column=2, sticky="e", pady=(8, 0))
            ttk.Radiobutton(direction, text="Up", variable=self.down_var, value=False).pack(
                side=tk.LEFT
            )
            ttk.Radiobutton(direction, text="Down", variable=self.down_var, value=True).pack(
                side=tk.LEFT, padx=(8, 0)
            )

        buttons = ttk.Frame(body)
        buttons.grid(row=0, column=3, rowspan=4, sticky="n", padx=(6, 0))
        self.action_buttons = [
            ttk.Button(buttons, text="Find Next", command=self.find_next, default="active")
        ]
        if replace:
            self.action_buttons += [
                ttk.Button(buttons, text="Replace", command=self.replace),
                ttk.Button(buttons, text="Replace All", command=self.replace_all),
            ]
        for button in self.action_buttons:
            button.pack(fill=tk.X, pady=2)
        ttk.Button(buttons, text="Cancel", command=self.close).pack(fill=tk.X, pady=2)

        self.bind("<Return>", lambda e: self.find_next())
        self.find_var.trace_add("write", lambda *a: self._update_buttons())
        self._update_buttons()
        self.find_entry.focus_set()
        self.find_entry.select_range(0, tk.END)
        self.show()

    def _update_buttons(self):
        state = "normal" if self.find_var.get() else "disabled"
        for button in self.action_buttons:
            button.config(state=state)

    def _sync(self):
        app = self.app
        app.find_term = self.find_var.get()
        app.replace_term = self.replace_var.get()
        app.find_match_case = self.case_var.get()
        app.find_wrap = self.wrap_var.get()
        app.find_down = True if self.replace_mode else self.down_var.get()

    def find_next(self):
        if self.find_var.get():
            self._sync()
            self.app.find(self.app.find_down, parent=self)

    def replace(self):
        self._sync()
        self.app.replace_selection(parent=self)

    def replace_all(self):
        self._sync()
        self.app.replace_all()

    def close(self):
        self._sync()
        self.app.find_dialog = None
        self.destroy()
        self.app.text.focus_set()


class GoToDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Go To Line", modal=True)
        ttk.Label(self.body, text="Line number:").pack(anchor="w")
        current_line = app.text.index(tk.INSERT).split(".")[0]
        self.var = tk.StringVar(value=current_line)
        validate = (self.register(lambda s: s == "" or s.isdigit()), "%P")
        entry = ttk.Entry(
            self.body, textvariable=self.var, width=30, validate="key", validatecommand=validate
        )
        entry.pack(fill=tk.X, pady=(4, 12))
        buttons = ttk.Frame(self.body)
        buttons.pack(anchor="e")
        ttk.Button(buttons, text="Go To", command=self.go, default="active").pack(side=tk.LEFT)
        ttk.Button(buttons, text="Cancel", command=self.close).pack(side=tk.LEFT, padx=(6, 0))
        self.bind("<Return>", lambda e: self.go())
        entry.focus_set()
        entry.select_range(0, tk.END)
        self.show()

    def go(self):
        text = self.app.text
        total = int(text.index("end-1c").split(".")[0])
        line = int(self.var.get() or 0)
        if line < 1 or line > total:
            messagebox.showinfo(
                f"{APP_NAME} - Goto Line",
                "The line number is beyond the total number of lines",
                parent=self,
            )
            return
        text.tag_remove(tk.SEL, "1.0", tk.END)
        text.mark_set(tk.INSERT, f"{line}.0")
        text.see(tk.INSERT)
        self.close()
        self.app.update_status()


class FontDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Font", modal=True)
        self.result = None
        settings = app.settings
        families = sorted(
            {f for f in tkfont.families(app.root) if not f.startswith("@")}, key=str.lower
        )
        columns = [
            ("Font:", families, settings["font_family"], 28),
            ("Font style:", FONT_STYLES, settings["font_style"], 14),
            ("Size:", [str(s) for s in FONT_SIZES], str(settings["font_size"]), 6),
        ]
        self.vars, self.lists = [], []
        for col, (label, values, current, width) in enumerate(columns):
            frame = ttk.Frame(self.body)
            frame.grid(row=0, column=col, padx=4, sticky="n")
            ttk.Label(frame, text=label).pack(anchor="w")
            var = tk.StringVar(value=current)
            ttk.Entry(frame, textvariable=var, width=width).pack(fill=tk.X)
            box = ttk.Frame(frame)
            box.pack()
            listbox = tk.Listbox(box, height=7, width=width, exportselection=False)
            scroll = ttk.Scrollbar(box, command=listbox.yview)
            listbox.config(yscrollcommand=scroll.set)
            listbox.pack(side=tk.LEFT)
            scroll.pack(side=tk.LEFT, fill=tk.Y)
            listbox.insert(tk.END, *values)
            if current in values:
                index = values.index(current)
                listbox.selection_set(index)
                listbox.see(index)
            listbox.bind(
                "<<ListboxSelect>>",
                lambda e, lb=listbox, v=var: lb.curselection() and v.set(lb.get(lb.curselection()[0])),
            )
            var.trace_add("write", lambda *a: self._update_sample())
            self.vars.append(var)
            self.lists.append(listbox)

        sample_frame = ttk.LabelFrame(self.body, text="Sample", padding=8)
        sample_frame.grid(row=1, column=0, columnspan=3, sticky="we", padx=4, pady=10)
        self.sample_font = tkfont.Font(root=app.root)
        holder = tk.Frame(sample_frame, height=70, width=380)
        holder.pack_propagate(False)
        holder.pack()
        tk.Label(holder, text="AaBbYyZz", font=self.sample_font).pack(expand=True)

        buttons = ttk.Frame(self.body)
        buttons.grid(row=2, column=0, columnspan=3, sticky="e")
        ttk.Button(buttons, text="OK", command=self.ok, default="active").pack(side=tk.LEFT)
        ttk.Button(buttons, text="Cancel", command=self.close).pack(side=tk.LEFT, padx=(6, 0))
        self.bind("<Return>", lambda e: self.ok())
        self._update_sample()
        self.show()

    def _values(self):
        family, style, size = (v.get().strip() for v in self.vars)
        size = int(size) if size.isdigit() and 1 <= int(size) <= 400 else None
        return family, style if style in FONT_STYLES else "Regular", size

    def _update_sample(self):
        family, style, size = self._values()
        if family and size:
            self.sample_font.configure(
                family=family,
                size=min(size, 36),
                weight="bold" if "Bold" in style else "normal",
                slant="italic" if "Italic" in style else "roman",
            )

    def ok(self):
        family, style, size = self._values()
        if not family or not size:
            messagebox.showinfo(APP_NAME, "Size must be a number.", parent=self)
            return
        self.result = (family, style, size)
        self.close()


class PageSetupDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Page Setup", modal=True)
        s = app.settings
        body = self.body

        paper = ttk.LabelFrame(body, text="Paper", padding=8)
        paper.grid(row=0, column=0, columnspan=2, sticky="we")
        ttk.Label(paper, text="Size:").grid(row=0, column=0, sticky="w")
        self.paper_var = tk.StringVar(value=s["paper"])
        ttk.Combobox(
            paper, textvariable=self.paper_var, values=list(PAPER_SIZES), state="readonly", width=20
        ).grid(row=0, column=1, padx=6)

        orientation = ttk.LabelFrame(body, text="Orientation", padding=8)
        orientation.grid(row=1, column=0, sticky="nswe", pady=8)
        self.orientation_var = tk.StringVar(value=s["orientation"])
        for value in ("Portrait", "Landscape"):
            ttk.Radiobutton(orientation, text=value, variable=self.orientation_var, value=value).pack(
                anchor="w"
            )

        margins = ttk.LabelFrame(body, text="Margins (inches)", padding=8)
        margins.grid(row=1, column=1, sticky="nswe", pady=8, padx=(8, 0))
        self.margin_vars = []
        for i, label in enumerate(("Left:", "Right:", "Top:", "Bottom:")):
            ttk.Label(margins, text=label).grid(row=i // 2, column=(i % 2) * 2, sticky="w", pady=2)
            var = tk.StringVar(value=str(s["margins"][i]))
            ttk.Entry(margins, textvariable=var, width=6).grid(
                row=i // 2, column=(i % 2) * 2 + 1, padx=(4, 10)
            )
            self.margin_vars.append(var)

        self.header_var = tk.StringVar(value=s["header"])
        self.footer_var = tk.StringVar(value=s["footer"])
        for row, (label, var) in enumerate(
            (("Header:", self.header_var), ("Footer:", self.footer_var)), start=2
        ):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(body, textvariable=var, width=30).grid(row=row, column=1, sticky="we", padx=(8, 0))
        ttk.Label(
            body,
            text="Codes: &f file name, &p page, &d date, &t time,\n&l &c &r align left/center/right, && ampersand",
            foreground="#666666",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 10))

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="OK", command=self.ok, default="active").pack(side=tk.LEFT)
        ttk.Button(buttons, text="Cancel", command=self.close).pack(side=tk.LEFT, padx=(6, 0))
        self.bind("<Return>", lambda e: self.ok())
        self.show()

    def ok(self):
        try:
            margins = [float(v.get()) for v in self.margin_vars]
            if any(m < 0 or m > 4 for m in margins):
                raise ValueError
        except ValueError:
            messagebox.showinfo(APP_NAME, "Margins must be numbers between 0 and 4.", parent=self)
            return
        self.app.settings.update(
            paper=self.paper_var.get(),
            orientation=self.orientation_var.get(),
            margins=margins,
            header=self.header_var.get(),
            footer=self.footer_var.get(),
        )
        self.close()


class ChoiceDialog(Dialog):
    """A label, a drop-down and OK/Cancel. Used for the encoding and the printer."""

    def __init__(self, app, title, label, values, current, ok_text="OK", copies=False):
        super().__init__(app, title, modal=True)
        self.result = None
        self.copies = 1
        ttk.Label(self.body, text=label).grid(row=0, column=0, sticky="w")
        self.var = tk.StringVar(value=current)
        ttk.Combobox(self.body, textvariable=self.var, values=values, state="readonly", width=28).grid(
            row=0, column=1, padx=(8, 0)
        )
        self.copies_var = tk.StringVar(value="1")
        if copies:
            ttk.Label(self.body, text="Copies:").grid(row=1, column=0, sticky="w", pady=(8, 0))
            ttk.Spinbox(self.body, from_=1, to=99, textvariable=self.copies_var, width=5).grid(
                row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
            )
        buttons = ttk.Frame(self.body)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text=ok_text, command=self.ok, default="active").pack(side=tk.LEFT)
        ttk.Button(buttons, text="Cancel", command=self.close).pack(side=tk.LEFT, padx=(6, 0))
        self.bind("<Return>", lambda e: self.ok())
        self.show()

    def ok(self):
        self.result = self.var.get()
        copies = self.copies_var.get()
        self.copies = int(copies) if copies.isdigit() and int(copies) > 0 else 1
        self.close()


# ── Main window ──────────────────────────────────────────────────


class Notepad:
    def __init__(self, root: tk.Tk, path: str | None = None):
        self.root = root
        self.settings = self._load_settings()

        self.path: str | None = None
        self.encoding = "UTF-8"
        self.eol = DEFAULT_EOL
        self.zoom = 100

        self.find_term = ""
        self.replace_term = ""
        self.find_match_case = False
        self.find_wrap = False
        self.find_down = True
        self.find_dialog: FindDialog | None = None

        self._build_text()
        self._build_status_bar()
        self._build_menus()
        self._bind_keys()
        self._apply_font()
        self._apply_word_wrap()
        self._apply_status_bar()
        self._update_title()
        self.update_status()

        root.geometry(self.settings["geometry"])
        root.protocol("WM_DELETE_WINDOW", self.exit)
        if IS_MAC:
            root.createcommand("tk::mac::Quit", self.exit)
            root.createcommand("tk::mac::OpenDocument", self._mac_open_document)
            root.createcommand("tkAboutDialog", self.about)

        if path:
            self._open_from_command_line(path)
        self.text.focus_set()

    # ── Settings ─────────────────────────────────────────────────

    def _load_settings(self) -> dict:
        settings = dict(DEFAULT_SETTINGS)
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
        except (OSError, ValueError):
            pass
        return settings

    def _save_settings(self):
        if self.root.state() == "normal":
            self.settings["geometry"] = self.root.geometry()
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except OSError:
            pass

    # ── UI construction ──────────────────────────────────────────

    def _build_text(self):
        self.text_frame = frame = tk.Frame(self.root)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.font = tkfont.Font(root=self.root)
        self.text = tk.Text(
            frame,
            font=self.font,
            undo=True,
            maxundo=-1,
            autoseparators=True,
            borderwidth=0,
            highlightthickness=0,
            padx=4,
            pady=2,
            wrap=tk.NONE,
        )
        # Keep the selection visible while the Find dialog has the focus
        self.text.config(inactiveselectbackground=self.text.cget("selectbackground"))
        self.vscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.text.yview)
        self.hscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.config(yscrollcommand=self.vscroll.set, xscrollcommand=self.hscroll.set)
        self.text.grid(row=0, column=0, sticky="nswe")
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.hscroll.grid(row=1, column=0, sticky="we")

        self.text.bind("<<Modified>>", self._on_modified)
        for event in ("<KeyRelease>", "<ButtonRelease-1>", "<B1-Motion>"):
            self.text.bind(event, lambda e: self.update_status(), add="+")

        context_events = ("<Button-2>", "<Control-Button-1>") if IS_MAC else ("<Button-3>",)
        for event in context_events:
            self.text.bind(event, self._show_context_menu)

    def _build_status_bar(self):
        self.status_bar = ttk.Frame(self.root)
        self.status_labels = {}
        # Packed from the right edge, like Notepad's status bar
        for key, width in (("encoding", 18), ("eol", 18), ("zoom", 7), ("position", 20)):
            label = ttk.Label(self.status_bar, width=width, anchor="w", padding=(8, 2))
            label.pack(side=tk.RIGHT)
            ttk.Separator(self.status_bar, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y, pady=2)
            self.status_labels[key] = label

    def _build_menus(self):
        menubar = tk.Menu(self.root)

        if IS_MAC:
            app_menu = tk.Menu(menubar, name="apple", tearoff=False)
            app_menu.add_command(label=f"About {APP_NAME}", command=self.about)
            menubar.add_cascade(menu=app_menu)

        file_menu = tk.Menu(menubar, tearoff=False)
        self._add(file_menu, "New", self.new, "n")
        self._add(file_menu, "New Window", self.new_window, "n", shift=True)
        self._add(file_menu, "Open...", self.open, "o")
        self._add(file_menu, "Save", self.save, "s")
        self._add(file_menu, "Save As...", self.save_as, "s", shift=True)
        file_menu.add_separator()
        file_menu.add_command(label="Page Setup...", command=self.page_setup)
        self._add(file_menu, "Print...", self.print, "p")
        if not IS_MAC:  # macOS provides Quit in the application menu
            file_menu.add_separator()
            file_menu.add_command(label="Exit", command=self.exit)
        menubar.add_cascade(label="File", menu=file_menu)

        self.edit_menu = edit = tk.Menu(menubar, tearoff=False, postcommand=self._update_edit_menu)
        self._add(edit, "Undo", self.undo, "z")
        if IS_MAC:
            self._add(edit, "Redo", self.redo, "z", shift=True)
        else:
            self._add(edit, "Redo", self.redo, "y")
        edit.add_separator()
        self._add(edit, "Cut", self.cut, "x")
        self._add(edit, "Copy", self.copy, "c")
        self._add(edit, "Paste", self.paste, "v")
        edit.add_command(label="Delete", command=self.delete, accelerator="Del")
        edit.add_separator()
        self._add(edit, "Search with Bing...", self.search_with_bing, "e")
        self._add(edit, "Find...", self.show_find, "f")
        edit.add_command(label="Find Next", command=self.find_next, accelerator="F3")
        edit.add_command(label="Find Previous", command=self.find_previous, accelerator="Shift+F3")
        if IS_MAC:  # Command+H hides the app on macOS
            edit.add_command(
                label="Replace...", command=self.show_replace, accelerator="Command+Option+F"
            )
            self._add(edit, "Go To...", self.go_to, "l")
        else:
            self._add(edit, "Replace...", self.show_replace, "h")
            self._add(edit, "Go To...", self.go_to, "g")
        edit.add_separator()
        self._add(edit, "Select All", self.select_all, "a")
        edit.add_command(label="Time/Date", command=self.insert_time_date, accelerator="F5")
        menubar.add_cascade(label="Edit", menu=edit)

        format_menu = tk.Menu(menubar, tearoff=False)
        self.wrap_var = tk.BooleanVar(value=self.settings["word_wrap"])
        format_menu.add_checkbutton(
            label="Word Wrap", variable=self.wrap_var, command=self._toggle_word_wrap
        )
        format_menu.add_command(label="Font...", command=self.choose_font)
        menubar.add_cascade(label="Format", menu=format_menu)

        view_menu = tk.Menu(menubar, tearoff=False)
        zoom_menu = tk.Menu(view_menu, tearoff=False)
        zoom_menu.add_command(
            label="Zoom In", command=self.zoom_in, accelerator=f"{MOD_LABEL}+Plus"
        )
        zoom_menu.add_command(
            label="Zoom Out", command=self.zoom_out, accelerator=f"{MOD_LABEL}+Minus"
        )
        zoom_menu.add_command(
            label="Restore Default Zoom", command=self.zoom_reset, accelerator=f"{MOD_LABEL}+0"
        )
        view_menu.add_cascade(label="Zoom", menu=zoom_menu)
        self.status_var = tk.BooleanVar(value=self.settings["status_bar"])
        view_menu.add_checkbutton(
            label="Status Bar", variable=self.status_var, command=self._toggle_status_bar
        )
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, name="help", tearoff=False)
        help_menu.add_command(label="View Help", command=self.view_help)
        if not IS_MAC:
            help_menu.add_separator()
            help_menu.add_command(label=f"About {APP_NAME}", command=self.about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _add(self, menu, label, command, key, shift=False):
        accelerator = f"{MOD_LABEL}+{'Shift+' if shift else ''}{key.upper()}"
        menu.add_command(label=label, command=command, accelerator=accelerator)

    def _bind_keys(self):
        plain = {
            "n": self.new,
            "o": self.open,
            "s": self.save,
            "p": self.print,
            "e": self.search_with_bing,
            "f": self.show_find,
            "a": self.select_all,
        }
        shifted = {"n": self.new_window, "s": self.save_as}
        if IS_MAC:
            plain.update({"l": self.go_to, "g": self.find_next})
            shifted.update({"g": self.find_previous, "z": self.redo})
            self._bind(f"<{MOD}-Option-f>", self.show_replace)
        else:
            plain.update({"h": self.show_replace, "g": self.go_to, "y": self.redo})
        plain["z"] = self.undo

        # Bind both cases so the shortcuts also work with Caps Lock on
        for key, func in plain.items():
            self._bind(f"<{MOD}-{key}>", func)
            self._bind(f"<{MOD}-{key.upper()}>", func)
        for key, func in shifted.items():
            self._bind(f"<{MOD}-Shift-{key}>", func)
            self._bind(f"<{MOD}-Shift-{key.upper()}>", func)

        self._bind("<F3>", self.find_next)
        self._bind("<Shift-F3>", self.find_previous)
        self._bind("<F5>", self.insert_time_date)
        for key in ("plus", "equal", "KP_Add"):
            self._bind(f"<{MOD}-{key}>", self.zoom_in)
        for key in ("minus", "KP_Subtract"):
            self._bind(f"<{MOD}-{key}>", self.zoom_out)
        for key in ("0", "KP_0"):
            self._bind(f"<{MOD}-{key}>", self.zoom_reset)

        self.text.bind(f"<{MOD}-MouseWheel>", self._on_zoom_wheel)
        self.text.bind(f"<{MOD}-Button-4>", lambda e: self._bind_result(self.zoom_in))
        self.text.bind(f"<{MOD}-Button-5>", lambda e: self._bind_result(self.zoom_out))

    def _bind(self, sequence, func):
        # "break" stops Tk's built-in Text bindings (e.g. Ctrl+O inserts a newline)
        self.text.bind(sequence, lambda e: self._bind_result(func))

    @staticmethod
    def _bind_result(func):
        func()
        return "break"

    # ── Title / status ───────────────────────────────────────────

    @property
    def display_name(self) -> str:
        return os.path.basename(self.path) if self.path else "Untitled"

    @property
    def modified(self) -> bool:
        return bool(self.text.edit_modified())

    def _update_title(self):
        self.root.title(f"{'*' if self.modified else ''}{self.display_name} - {APP_NAME}")

    def _on_modified(self, _event=None):
        self._update_title()
        self.update_status()

    def update_status(self):
        line, col = self.text.index(tk.INSERT).split(".")
        self.status_labels["position"].config(text=f"Ln {line}, Col {int(col) + 1}")
        self.status_labels["zoom"].config(text=f"{self.zoom}%")
        self.status_labels["eol"].config(text=LINE_ENDINGS[self.eol])
        self.status_labels["encoding"].config(text=self.encoding)

    # ── File menu ────────────────────────────────────────────────

    def _confirm_discard(self) -> bool:
        """Offers to save unsaved changes. Returns False if the user cancelled."""
        if not self.modified:
            return True
        name = self.path or "Untitled"
        answer = messagebox.askyesnocancel(
            APP_NAME, f"Do you want to save changes to {name}?", parent=self.root
        )
        if answer is None:
            return False
        return self.save() if answer else True

    def _set_document(self, text: str, path: str | None, encoding: str, eol: str):
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", text)
        self.text.mark_set(tk.INSERT, "1.0")
        self.text.see("1.0")
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.path, self.encoding, self.eol = path, encoding, eol
        self._update_title()
        self.update_status()

    def new(self):
        if self._confirm_discard():
            self._set_document("", None, "UTF-8", DEFAULT_EOL)

    def new_window(self):
        subprocess.Popen([sys.executable, os.path.abspath(__file__)])

    def _filetypes(self):
        return [("Text Documents", "*.txt"), ("All Files", "*" if IS_MAC else "*.*")]

    def open(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self.root, filetypes=self._filetypes())
        if path:
            self.load(path)

    def load(self, path: str) -> bool:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            messagebox.showerror(APP_NAME, f"Cannot open file:\n\n{e}", parent=self.root)
            return False
        raw, encoding = decode_bytes(data)
        self._set_document(normalize_eol(raw), os.path.abspath(path), encoding, detect_eol(raw))

        # Notepad's log feature: files starting with .LOG get a timestamp on open
        if raw.startswith(".LOG"):
            self.text.insert(tk.END, f"\n{time_date_string()}\n")
            self.text.mark_set(tk.INSERT, tk.END)
            self.text.see(tk.INSERT)
            self.update_status()
        return True

    def _open_from_command_line(self, path: str):
        if os.path.exists(path):
            self.load(path)
            return
        create = messagebox.askyesnocancel(
            APP_NAME,
            f"Cannot find the {path} file.\n\nDo you want to create a new file?",
            parent=self.root,
        )
        if create:
            try:
                open(path, "w").close()
                self.load(path)
            except OSError as e:
                messagebox.showerror(APP_NAME, str(e), parent=self.root)

    def _mac_open_document(self, *paths):
        if paths and self._confirm_discard():
            self.load(paths[0])

    def save(self) -> bool:
        if not self.path:
            return self.save_as()
        return self._write(self.path, self.encoding)

    def save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".txt",
            filetypes=self._filetypes(),
            initialfile=self.display_name if self.path else "*.txt" if IS_WIN else "Untitled.txt",
            initialdir=os.path.dirname(self.path) if self.path else None,
        )
        if not path:
            return False
        # Tk's native save panel has no room for Notepad's Encoding drop-down
        dialog = ChoiceDialog(
            self, "Save As", "Encoding:", [e[0] for e in ENCODINGS], self.encoding, ok_text="Save"
        )
        if dialog.result is None:
            return False
        return self._write(path, dialog.result)

    def _write(self, path: str, encoding: str) -> bool:
        text = self.text.get("1.0", "end-1c")
        if encoding == "ANSI":
            try:
                text.encode("cp1252")
            except UnicodeEncodeError:
                ok = messagebox.askokcancel(
                    APP_NAME,
                    "This file contains characters in Unicode format which will be lost "
                    "if you save this file as an ANSI encoded text file. To keep the "
                    "Unicode information, click Cancel below and then select one of the "
                    "Unicode options from the Encoding drop down list. Continue?",
                    parent=self.root,
                )
                if not ok:
                    return False
        try:
            with open(path, "wb") as f:
                f.write(encode_text(text.replace("\n", self.eol), encoding))
        except OSError as e:
            messagebox.showerror(APP_NAME, f"Cannot save file:\n\n{e}", parent=self.root)
            return False
        self.path, self.encoding = os.path.abspath(path), encoding
        self.text.edit_modified(False)
        self._update_title()
        self.update_status()
        return True

    def page_setup(self):
        PageSetupDialog(self)

    def print(self):
        text = self.text.get("1.0", "end-1c")
        if IS_WIN:
            # Hand the text to the registered .txt print handler
            directory = tempfile.mkdtemp(prefix="notepad_py_")
            name = self.display_name if self.display_name.endswith(".txt") else "Untitled.txt"
            path = os.path.join(directory, name)
            with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
                f.write(text)
            try:
                os.startfile(path, "print")
            except OSError as e:
                messagebox.showerror(APP_NAME, f"Cannot print:\n\n{e}", parent=self.root)
            return

        printers, default = list_printers()
        if not printers:
            messagebox.showerror(
                APP_NAME,
                "No printers found.\n\nAdd one in System Settings > Printers & Scanners.",
                parent=self.root,
            )
            return
        dialog = ChoiceDialog(
            self, "Print", "Printer:", printers, default or printers[0], ok_text="Print", copies=True
        )
        if dialog.result is None:
            return

        left, right, top, bottom = (round(m * 72) for m in self.settings["margins"])
        paper = {"Letter": "Letter", "A4": "A4", "Legal": "Legal"}[self.settings["paper"]]
        command = [
            "lpr", "-P", dialog.result, "-#", str(dialog.copies), "-T", self.display_name,
            "-o", f"media={paper}", "-o", "cpi=10", "-o", "lpi=6",
            "-o", f"page-left={left}", "-o", f"page-right={right}",
            "-o", f"page-top={top}", "-o", f"page-bottom={bottom}",
        ]  # fmt: skip
        if self.settings["orientation"] == "Landscape":
            command += ["-o", "landscape"]
        try:
            subprocess.run(
                command,
                input=paginate(text, self.display_name, self.settings).encode("utf-8"),
                check=True,
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as e:
            detail = getattr(e, "stderr", b"") or str(e).encode()
            messagebox.showerror(
                APP_NAME, f"Cannot print:\n\n{detail.decode(errors='replace')}", parent=self.root
            )

    def exit(self):
        if self._confirm_discard():
            self._save_settings()
            self.root.destroy()

    # ── Edit menu ────────────────────────────────────────────────

    def _has_selection(self) -> bool:
        return bool(self.text.tag_ranges(tk.SEL))

    def _selected_text(self) -> str:
        return self.text.get(tk.SEL_FIRST, tk.SEL_LAST) if self._has_selection() else ""

    def _can(self, what: str) -> bool:
        try:
            return bool(self.text.tk.call(self.text._w, "edit", what))
        except tk.TclError:  # Tk older than 8.6.9
            return True

    def _clipboard_has_text(self) -> bool:
        try:
            return bool(self.root.clipboard_get())
        except tk.TclError:
            return False

    def _edit_states(self) -> dict:
        has_selection = self._has_selection()
        has_text = self.text.compare("end-1c", "!=", "1.0")
        return {
            "Undo": self._can("canundo"),
            "Redo": self._can("canredo"),
            "Cut": has_selection,
            "Copy": has_selection,
            "Paste": self._clipboard_has_text(),
            "Delete": has_selection,
            "Search with Bing...": has_selection,
            "Find...": has_text,
            "Find Next": has_text,
            "Find Previous": has_text,
        }

    def _update_edit_menu(self):
        for label, enabled in self._edit_states().items():
            self.edit_menu.entryconfig(label, state=tk.NORMAL if enabled else tk.DISABLED)

    def _show_context_menu(self, event):
        self.text.focus_set()
        states = self._edit_states()
        menu = tk.Menu(self.root, tearoff=False)
        for label, command in (
            ("Undo", self.undo),
            (None, None),
            ("Cut", self.cut),
            ("Copy", self.copy),
            ("Paste", self.paste),
            ("Delete", self.delete),
            (None, None),
            ("Select All", self.select_all),
            (None, None),
            ("Search with Bing...", self.search_with_bing),
        ):
            if label is None:
                menu.add_separator()
            else:
                enabled = states.get(label, True)
                menu.add_command(
                    label=label, command=command, state=tk.NORMAL if enabled else tk.DISABLED
                )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def undo(self):
        try:
            self.text.edit_undo()
        except tk.TclError:
            pass
        self.update_status()

    def redo(self):
        try:
            self.text.edit_redo()
        except tk.TclError:
            pass
        self.update_status()

    def cut(self):
        self.text.event_generate("<<Cut>>")

    def copy(self):
        self.text.event_generate("<<Copy>>")

    def paste(self):
        self.text.event_generate("<<Paste>>")
        self.text.see(tk.INSERT)

    def delete(self):
        if self._has_selection():
            self.text.delete(tk.SEL_FIRST, tk.SEL_LAST)

    def select_all(self):
        self.text.tag_add(tk.SEL, "1.0", "end-1c")
        self.text.mark_set(tk.INSERT, "end-1c")
        self.text.see(tk.INSERT)
        self.update_status()

    def insert_time_date(self):
        self.delete()
        self.text.insert(tk.INSERT, time_date_string())
        self.text.see(tk.INSERT)

    def search_with_bing(self):
        query = self._selected_text().strip()
        if query:
            webbrowser.open("https://www.bing.com/search?q=" + urllib.parse.quote_plus(query))

    def go_to(self):
        GoToDialog(self)

    # ── Find / Replace ───────────────────────────────────────────

    def _show_find_dialog(self, replace: bool):
        if self.find_dialog is not None:
            if self.find_dialog.replace_mode == replace:
                self.find_dialog.lift()
                self.find_dialog.find_entry.focus_set()
                return
            self.find_dialog.close()
        selection = self._selected_text()
        if selection and "\n" not in selection:
            self.find_term = selection
        self.find_dialog = FindDialog(self, replace=replace)

    def show_find(self):
        if self.text.compare("end-1c", "!=", "1.0"):
            self._show_find_dialog(replace=False)

    def show_replace(self):
        self._show_find_dialog(replace=True)

    def find_next(self):
        if self.find_term:
            self.find(down=True)
        else:
            self.show_find()

    def find_previous(self):
        if self.find_term:
            self.find(down=False)
        else:
            self.show_find()

    def find(self, down: bool, parent=None, quiet=False) -> bool:
        text = self.text
        if self._has_selection():
            start = text.index(tk.SEL_LAST if down else tk.SEL_FIRST)
        else:
            start = text.index(tk.INSERT)
        stop = None if self.find_wrap else ("end-1c" if down else "1.0")
        count = tk.IntVar()
        index = text.search(
            self.find_term,
            start,
            stopindex=stop,
            forwards=down,
            backwards=not down,
            nocase=not self.find_match_case,
            count=count,
        )
        if not index:
            if not quiet:
                messagebox.showinfo(
                    APP_NAME, f'Cannot find "{self.find_term}"', parent=parent or self.root
                )
            return False
        end = f"{index}+{count.get()}c"
        text.tag_remove(tk.SEL, "1.0", tk.END)
        text.tag_add(tk.SEL, index, end)
        text.mark_set(tk.INSERT, end if down else index)
        text.see(index)
        self.update_status()
        return True

    def _selection_matches(self) -> bool:
        selected, term = self._selected_text(), self.find_term
        if self.find_match_case:
            return selected == term
        return selected.lower() == term.lower() and bool(term)

    def replace_selection(self, parent=None):
        if self._selection_matches():
            start = self.text.index(tk.SEL_FIRST)
            self.text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.text.insert(start, self.replace_term)
            self.text.mark_set(tk.INSERT, f"{start}+{len(self.replace_term)}c")
        self.find(down=True, parent=parent)

    def replace_all(self) -> int:
        text = self.text
        replaced = 0
        index = "1.0"
        count = tk.IntVar()
        text.config(autoseparators=False)
        text.edit_separator()
        while True:
            index = text.search(
                self.find_term, index, stopindex=tk.END,
                nocase=not self.find_match_case, count=count,
            )  # fmt: skip
            if not index or count.get() == 0:
                break
            text.delete(index, f"{index}+{count.get()}c")
            text.insert(index, self.replace_term)
            index = f"{index}+{len(self.replace_term)}c"
            replaced += 1
        text.edit_separator()
        text.config(autoseparators=True)
        self.update_status()
        return replaced

    # ── Format menu ──────────────────────────────────────────────

    def _apply_font(self):
        style = self.settings["font_style"]
        self.font.configure(
            family=self.settings["font_family"],
            size=max(1, round(self.settings["font_size"] * self.zoom / 100)),
            weight="bold" if "Bold" in style else "normal",
            slant="italic" if "Italic" in style else "roman",
        )
        self.text.config(tabs=(self.font.measure("0" * 8),))  # 8-column tab stops
        self.update_status()

    def choose_font(self):
        dialog = FontDialog(self)
        if dialog.result:
            family, style, size = dialog.result
            self.settings.update(font_family=family, font_style=style, font_size=size)
            self._apply_font()

    def _toggle_word_wrap(self):
        self.settings["word_wrap"] = self.wrap_var.get()
        self._apply_word_wrap()

    def _apply_word_wrap(self):
        if self.settings["word_wrap"]:
            self.text.config(wrap=tk.WORD)
            self.hscroll.grid_remove()
        else:
            self.text.config(wrap=tk.NONE)
            self.hscroll.grid()

    # ── View menu ────────────────────────────────────────────────

    def _set_zoom(self, zoom: int):
        self.zoom = min(max(zoom, ZOOM_MIN), ZOOM_MAX)
        self._apply_font()

    def zoom_in(self):
        self._set_zoom(self.zoom + ZOOM_STEP)

    def zoom_out(self):
        self._set_zoom(self.zoom - ZOOM_STEP)

    def zoom_reset(self):
        self._set_zoom(100)

    def _on_zoom_wheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        elif event.delta < 0:
            self.zoom_out()
        return "break"

    def _toggle_status_bar(self):
        self.settings["status_bar"] = self.status_var.get()
        self._apply_status_bar()

    def _apply_status_bar(self):
        if self.settings["status_bar"]:
            # Packed before the text so it keeps its height in a small window
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, before=self.text_frame)
        else:
            self.status_bar.pack_forget()

    # ── Help menu ────────────────────────────────────────────────

    def view_help(self):
        webbrowser.open("https://www.bing.com/search?q=get+help+with+notepad+in+windows")

    def about(self):
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME}\n\nA Python/Tkinter clone of Windows Notepad.\n"
            f"Python {sys.version.split()[0]}, Tk {self.root.tk.call('info', 'patchlevel')}",
            parent=self.root,
        )


def main():
    if IS_WIN:
        try:  # sharp text on high-DPI displays
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    root.option_add("*tearOff", False)
    Notepad(root, sys.argv[1] if len(sys.argv) > 1 else None)
    root.mainloop()


if __name__ == "__main__":
    main()
