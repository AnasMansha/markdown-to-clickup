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

## Usage

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
