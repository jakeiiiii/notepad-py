# NotepadClone

<img src="assets/icon.png" width="96" align="right" alt="NotepadClone icon">

A clone of Windows Notepad, with tabs, in a single Python file. It uses only the standard
library (Tkinter), so it runs on macOS, Windows and Linux with nothing to install.

```bash
python3 notepadClone.py [file ...]
```

## Features

- **Tabs**: edit several files at once. `+` or double-click the tab bar for a new tab,
  `×` or middle-click to close, right-click for *Close Other Tabs* / *Close Tabs to the
  Right*. A `●` on the tab marks unsaved changes. Opening a file that is already open
  switches to its tab.
- **Session restore**: closing the window never asks about unsaved work. Every tab comes
  back next time exactly as it was, including Untitled tabs and unsaved edits, with the
  cursor where you left it. The session is also snapshotted a moment after each edit,
  so a crash or power cut does not lose text. Switch it off with
  *File > Reopen Tabs from Last Session* to get the classic "Do you want to save?" prompt.
- **File**: New Tab, New Window, Open (multiple files), Save, Save As, Save All, Page Setup,
  Print, Close Tab, Close Window
- **Edit**: multi-level Undo/Redo, Cut, Copy, Paste, Delete, Search with Bing, Find,
  Find Next/Previous, Replace, Replace All, Go To, Select All, Time/Date, right-click menu
- **Format**: Word Wrap, Font dialog (family, style, size, live sample)
- **View**: Zoom 10–500% (keyboard or modifier + mouse wheel), Status Bar with
  line/column, zoom, line ending and encoding
- **Encodings**: ANSI, UTF-8, UTF-8 with BOM, UTF-16 LE/BE, detected on open
- **Line endings**: CRLF, LF and CR are detected and preserved
- `.LOG` files get a timestamp appended when opened
- Settings and the session live in `~/.notepadclone/`

## Shortcuts

Windows/Linux use `Ctrl`, macOS uses `Command`.

| Action | Windows / Linux | macOS |
|---|---|---|
| New Tab / New Window | Ctrl+N or Ctrl+T / Ctrl+Shift+N | ⌘N or ⌘T / ⇧⌘N |
| Close Tab / Close Window | Ctrl+W / Ctrl+Shift+W | ⌘W / ⇧⌘W |
| Next / Previous Tab | Ctrl+Tab / Ctrl+Shift+Tab | ⌃Tab or ⇧⌘] / ⌃⇧Tab or ⇧⌘[ |
| Open / Save / Save As / Save All | Ctrl+O / Ctrl+S / Ctrl+Shift+S / Ctrl+Alt+S | ⌘O / ⌘S / ⇧⌘S / ⌥⌘S |
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

## Packaged apps

GitHub Actions ([build.yml](.github/workflows/build.yml)) builds a standalone app with
PyInstaller, so Python is not needed to run it:

| Download | For |
|---|---|
| `NotepadClone-macOS-AppleSilicon.zip` | Macs with an M-series chip |
| `NotepadClone-macOS-Intel.zip` | Intel Macs |
| `NotepadClone-Windows.zip` | Windows 10/11 (64-bit) |

- Every push to `main` builds all three; they are under the run's **Artifacts** on the
  [Actions](../../actions) tab (GitHub sign-in required, kept for 90 days).
- Pushing a version tag publishes them on the [Releases](../../releases) page:

  ```bash
  git tag v1.0.0 && git push origin v1.0.0
  ```

The apps are not code-signed. On macOS, right-click `NotepadClone.app` and choose **Open** the
first time (or run `xattr -dr com.apple.quarantine NotepadClone.app`). On Windows, choose
**More info → Run anyway** if SmartScreen appears.

To build locally: `pip install pyinstaller`, then
`pyinstaller --windowed --name NotepadClone --icon assets/icon.icns notepadClone.py`
(on Windows use `assets/icon.ico` and add `--onefile`).

The icon is drawn by `tools/make_icon.py` (needs Pillow), which writes `assets/icon.png`,
`.ico`, `.icns` and the small copy embedded in the script for the window and Dock icon.

## Notes

- Printing on macOS/Linux goes through CUPS (`lpr`) and honours the Page Setup margins,
  orientation and header/footer codes (`&f` file name, `&p` page, `&d` date, `&t` time,
  `&l` `&c` `&r` alignment). On Windows it uses the system's `.txt` print handler.
- The encoding is chosen in a small dialog after the Save As panel, because the native
  save panel cannot host Notepad's Encoding drop-down.
- A window opened with *New Window* (or a second copy of the app) is independent: it does
  not restore or save the session, and asks about unsaved changes when it closes.
- Dragging a file onto the window is not supported (Tkinter has no drag-and-drop in the
  standard library).
