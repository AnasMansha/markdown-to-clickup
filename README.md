# Markdown → ClickUp

Paste Markdown files into ClickUp Docs with formatting intact.

ClickUp doesn't render pasted Markdown well, especially tables. This script converts a `.md` file into the rich HTML that ClickUp's editor understands and puts it on your clipboard. Then you just press `Ctrl + V` in ClickUp.

## Requirements

- Windows (it uses the Windows clipboard)
- Python 3.8+
- [pywin32](https://pypi.org/project/pywin32/)

```bash
pip install -r requirements.txt
```

## Download (no Python needed)

Download [`release/MarkdownToClickUp.exe`](release/MarkdownToClickUp.exe) and double-click it.

> Windows may show a SmartScreen warning because the exe isn't code-signed. Click **More info → Run anyway**.

## Desktop app

```bash
python app.py
```

A window opens where you can:

1. Click **Open .md file…** to load a file, or paste Markdown into the text box
2. Click **Copy for ClickUp** (or press `Ctrl + Enter`)
3. Press `Ctrl + V` in a ClickUp Doc

### Build a standalone .exe (optional)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name MarkdownToClickUp app.py
```

The app will be in `dist/MarkdownToClickUp.exe`. You can double-click it, and Python doesn't need to be installed.

## Command line

Pass the Markdown file as an argument:

```bash
python mark.py path/to/file.md
```

Or run it without arguments and it will ask for the file:

```bash
python mark.py
```

Then open a ClickUp Doc, click on an empty line, and press `Ctrl + V`.

## Configuration

Edit the values at the top of `mark.py`:

| Setting | Default | Description |
| --- | --- | --- |
| `HEADER_COLOR` | `orange` | Background color of the first row of every table |
| `FULL_TABLE_WIDTH` | `714` | Total table width in pixels, split evenly across columns |

## License

MIT
