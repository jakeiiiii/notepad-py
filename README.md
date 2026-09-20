# Notepad.py

A clone of Windows Notepad in a single Python file. It uses only the standard
library (Tkinter), so it runs on macOS, Windows and Linux with nothing to install.

```bash
python3 notepad.py [file]
```

## Features

- **File**: New, New Window, Open, Save, Save As, Page Setup, Print, Exit, with the
  unsaved-changes prompt and `*` in the title bar
- **Edit**: multi-level Undo/Redo, Cut, Copy, Paste, Delete, Search with Bing, Find,
  Find Next/Previous, Replace, Replace All, Go To, Select All, Time/Date, right-click menu
- **Format**: Word Wrap, Font dialog (family, style, size, live sample)
- **View**: Zoom 10–500% (keyboard or modifier + mouse wheel), Status Bar with
  line/column, zoom, line ending and encoding
- **Encodings**: ANSI, UTF-8, UTF-8 with BOM, UTF-16 LE/BE, detected on open
- **Line endings**: CRLF, LF and CR are detected and preserved
- `.LOG` files get a timestamp appended when opened
- Settings are remembered in `~/.notepad_py.json`

## Shortcuts

Windows/Linux use `Ctrl`, macOS uses `Command`.

| Action | Windows / Linux | macOS |
|---|---|---|
| New / New Window | Ctrl+N / Ctrl+Shift+N | ⌘N / ⇧⌘N |
| Open / Save / Save As | Ctrl+O / Ctrl+S / Ctrl+Shift+S | ⌘O / ⌘S / ⇧⌘S |
| Print | Ctrl+P | ⌘P |
| Find / Find Next / Find Previous | Ctrl+F / F3 / Shift+F3 | ⌘F / ⌘G or F3 / ⇧⌘G or ⇧F3 |
| Replace | Ctrl+H | ⌥⌘F (⌘H is reserved by macOS) |
| Go To | Ctrl+G | ⌘L |
| Redo | Ctrl+Y | ⇧⌘Z |
| Time/Date | F5 | F5 |
| Zoom in / out / reset | Ctrl+Plus / Ctrl+Minus / Ctrl+0 | ⌘+ / ⌘− / ⌘0 |

## Requirements

Python 3.10+ with Tk 8.6.

On macOS use Python from [python.org](https://www.python.org/downloads/) or Homebrew
(`brew install python-tk`). The `/usr/bin/python3` that ships with macOS uses an old Tk
that has display bugs.

## Notes

- Printing on macOS/Linux goes through CUPS (`lpr`) and honours the Page Setup margins,
  orientation and header/footer codes (`&f` file name, `&p` page, `&d` date, `&t` time,
  `&l` `&c` `&r` alignment). On Windows it uses the system's `.txt` print handler.
- The encoding is chosen in a small dialog after the Save As panel, because the native
  save panel cannot host Notepad's Encoding drop-down.
- Dragging a file onto the window is not supported (Tkinter has no drag-and-drop in the
  standard library).
