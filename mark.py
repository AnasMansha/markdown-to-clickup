import sys
import re
import json
import base64
import secrets
import html
from pathlib import Path

try:
    import win32clipboard
    import win32con
except ImportError:
    print("Missing dependency: pywin32")
    print("Install it with:")
    print("    pip install pywin32")
    sys.exit(1)


# ============================================================
# CONFIG
# ============================================================

# Header color for the first row of every table.
HEADER_COLOR = "orange"

# Total width of the table.
FULL_TABLE_WIDTH = 714


# ============================================================
# ID GENERATION
# ============================================================

def make_id(prefix="block"):
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

    return prefix + "-" + "".join(
        secrets.choice(chars)
        for _ in range(10)
    )


# ============================================================
# HTML ESCAPING
# ============================================================

def esc(text):
    return html.escape(
        text,
        quote=False
    )


# Markdown backslash escape, e.g. \~ \* \_ \| \[ \#
MD_ESCAPE = r"\\([!-/:-@\[-`{-~])"


_PLACEHOLDERS = []


def unescape_md(text):
    return re.sub(MD_ESCAPE, r"\1", text)


# ============================================================
# INLINE MARKDOWN -> HTML
# ============================================================

def inline_markdown(text):
    """
    Convert common Markdown inline formatting to HTML.

    Supports:
        **bold**
        *italic*
        _italic_
        `code`
        [links](url)
        ![images](url)
    """

    # Shared across nested calls (link labels call this
    # function recursively), so token numbers never collide.
    placeholders = _PLACEHOLDERS

    # "****" = empty bold (close + reopen), common in
    # ClickUp exports like **Bootstrap (****`x`****)**
    text = text.replace("****", "")

    # Literal <br> tags written in the Markdown
    text = re.sub(r"<br\s*/?>", "@@BR@@", text, flags=re.I)

    # --------------------------------------------------------
    # Inline code
    # --------------------------------------------------------

    def protect_code(match):
        value = match.group(1)

        token = f"@@CODE{len(placeholders)}@@"

        placeholders.append(
            f"<code>{esc(value)}</code>"
        )

        return token

    text = re.sub(
        r"`([^`]+)`",
        protect_code,
        text
    )

    # --------------------------------------------------------
    # Backslash escapes:  \~  \*  \_  \|  ->  literal char
    # (stored as placeholders so bold/italic regexes skip them)
    # --------------------------------------------------------

    def protect_escape(match):

        token = f"@@CODE{len(placeholders)}@@"

        placeholders.append(
            esc(match.group(1))
        )

        return token

    text = re.sub(
        MD_ESCAPE,
        protect_escape,
        text
    )

    # --------------------------------------------------------
    # Images
    # --------------------------------------------------------

    def image_replacement(match):

        alt = esc(
            match.group(1)
        )

        url = html.escape(
            match.group(2),
            quote=True
        )

        token = f"@@IMAGE{len(placeholders)}@@"

        placeholders.append(
            f'<img class="ql-img ql-img-smooth" '
            f'loading="lazy" '
            f'tabindex="0" '
            f'contenteditable="false" '
            f'alt="{alt}" '
            f'src="{url}" '
            f'style="max-width: 100%;">'
        )

        return token

    text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        image_replacement,
        text
    )

    # --------------------------------------------------------
    # Links
    # --------------------------------------------------------

    def link_replacement(match):

        label = inline_markdown(
            match.group(1)
        )

        url = html.escape(
            match.group(2),
            quote=True
        )

        token = f"@@LINK{len(placeholders)}@@"

        placeholders.append(
            f'<a class="ql-link" '
            f'href="{url}" '
            f'rel="noopener noreferrer" '
            f'target="_blank" '
            f'data-test="link-preview-plain">'
            f'{label}'
            f'</a>'
        )

        return token

    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        link_replacement,
        text
    )

    # --------------------------------------------------------
    # Escape remaining HTML
    # --------------------------------------------------------

    text = esc(text)

    # --------------------------------------------------------
    # Bold + italic
    # --------------------------------------------------------

    text = re.sub(
        r"\*\*\*([^*]+)\*\*\*",
        r"<strong><em>\1</em></strong>",
        text
    )

    text = re.sub(
        r"___([^_]+)___",
        r"<strong><em>\1</em></strong>",
        text
    )

    # --------------------------------------------------------
    # Bold
    # --------------------------------------------------------

    text = re.sub(
        r"\*\*([^*]+)\*\*",
        r"<strong>\1</strong>",
        text
    )

    text = re.sub(
        r"__([^_]+)__",
        r"<strong>\1</strong>",
        text
    )

    # --------------------------------------------------------
    # Italic
    # --------------------------------------------------------

    text = re.sub(
        r"(?<!\*)\*([^*]+)\*(?!\*)",
        r"<em>\1</em>",
        text
    )

    text = re.sub(
        r"(?<!_)_([^_]+)_(?!_)",
        r"<em>\1</em>",
        text
    )

    # --------------------------------------------------------
    # Restore placeholders
    # --------------------------------------------------------

    # Loop until none are left: a restored placeholder can
    # contain another one, e.g. [`agent.md`](url) -> the
    # LINK value contains @@CODE0@@.
    token_re = re.compile(r"@@(?:CODE|IMAGE|LINK)(\d+)@@")

    while token_re.search(text):

        text = token_re.sub(
            lambda m: placeholders[int(m.group(1))],
            text
        )

    text = text.replace("@@BR@@", "<br>")

    return text


# ============================================================
# MARKDOWN TABLE PARSING
# ============================================================

def split_table_row(line):
    """
    Convert:

        | A | B | C |

    into:

        ["A", "B", "C"]
    """

    line = line.strip()

    if line.startswith("|"):
        line = line[1:]

    if line.endswith("|"):
        line = line[:-1]

    result = []

    current = []

    escaped = False

    for char in line:

        if char == "|" and not escaped:

            result.append(
                "".join(current).strip()
            )

            current = []

            continue

        current.append(char)

        if char == "\\" and not escaped:
            escaped = True
        else:
            escaped = False

    result.append(
        "".join(current).strip()
    )

    return result


def is_table_separator(line):
    """
    Detect:

        |------|------|
        |:-----|-----:|
    """

    if "|" not in line:
        return False

    cells = split_table_row(line)

    if not cells:
        return False

    for cell in cells:

        cell = cell.strip()

        if not re.fullmatch(
            r":?-+:?",
            cell
        ):
            return False

    return True


# ============================================================
# CLICKUP TABLE CELL CONTENT
# ============================================================

def markdown_to_quill_content(text):
    """
    Convert Markdown inside a ClickUp table cell into
    Quill Delta-style content.

    This is important because ClickUp tables don't store
    Markdown formatting directly.

    Example:

        `3001`

    becomes:

        {
            "insert": "3001",
            "attributes": {
                "code": true
            }
        }

    Also supports:

        **bold**
        *italic*
        `code`
        [link](url)
    """

    inserts = []

    # Empty bold runs + literal <br> (line break in a cell)
    text = text.replace("****", "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)

    # --------------------------------------------------------
    # Tokenize inline Markdown
    # --------------------------------------------------------

    pattern = re.compile(
        r"""
        (`[^`]+`)                           # inline code
        |
        (\\[!-/:-@\[-`{-~])                 # backslash escape
        |
        (\*\*\*[^*]+\*\*\*)                 # bold italic
        |
        (\*\*[^*]+\*\*)                     # bold
        |
        (__[^_]+__)                         # bold
        |
        (\*[^*]+\*)                         # italic
        |
        (_[^_]+_)                           # italic
        |
        (\[[^\]]+\]\([^)]+\))               # link
        """,
        re.VERBOSE
    )

    position = 0

    for match in pattern.finditer(text):

        # ----------------------------------------------------
        # Normal text before this formatting
        # ----------------------------------------------------

        if match.start() > position:

            inserts.append({
                "insert": text[
                    position:match.start()
                ]
            })

        token = match.group(0)

        # ----------------------------------------------------
        # Inline code
        # ----------------------------------------------------

        if token.startswith("`") and token.endswith("`"):

            inserts.append({
                "insert": token[1:-1],
                "attributes": {
                    "code": True
                }
            })

            position = match.end()

            continue

        # ----------------------------------------------------
        # Backslash escape -> literal character
        # ----------------------------------------------------

        if token.startswith("\\"):

            inserts.append({
                "insert": token[1:]
            })

            position = match.end()

            continue

        # Remove escapes inside bold / italic / link text
        token = unescape_md(token)

        # ----------------------------------------------------
        # Bold + italic
        # ----------------------------------------------------

        if (
            token.startswith("***")
            and token.endswith("***")
        ):

            inserts.append({
                "insert": token[3:-3],
                "attributes": {
                    "bold": True,
                    "italic": True
                }
            })

        # ----------------------------------------------------
        # Bold **
        # ----------------------------------------------------

        elif (
            token.startswith("**")
            and token.endswith("**")
        ):

            inserts.append({
                "insert": token[2:-2],
                "attributes": {
                    "bold": True
                }
            })

        # ----------------------------------------------------
        # Bold __
        # ----------------------------------------------------

        elif (
            token.startswith("__")
            and token.endswith("__")
        ):

            inserts.append({
                "insert": token[2:-2],
                "attributes": {
                    "bold": True
                }
            })

        # ----------------------------------------------------
        # Italic *
        # ----------------------------------------------------

        elif (
            token.startswith("*")
            and token.endswith("*")
        ):

            inserts.append({
                "insert": token[1:-1],
                "attributes": {
                    "italic": True
                }
            })

        # ----------------------------------------------------
        # Italic _
        # ----------------------------------------------------

        elif (
            token.startswith("_")
            and token.endswith("_")
        ):

            inserts.append({
                "insert": token[1:-1],
                "attributes": {
                    "italic": True
                }
            })

        # ----------------------------------------------------
        # Link
        # ----------------------------------------------------

        elif token.startswith("["):

            link_match = re.match(
                r"\[([^\]]+)\]\(([^)]+)\)",
                token
            )

            if link_match:

                label = link_match.group(1)
                url = link_match.group(2)

                inserts.append({
                    "insert": label,
                    "attributes": {
                        "link": url
                    }
                })

            else:

                inserts.append({
                    "insert": token
                })

        else:

            inserts.append({
                "insert": token
            })

        position = match.end()

    # --------------------------------------------------------
    # Remaining text
    # --------------------------------------------------------

    if position < len(text):

        inserts.append({
            "insert": text[position:]
        })

    # --------------------------------------------------------
    # Empty cell
    # --------------------------------------------------------

    if not inserts:

        inserts.append({
            "insert": ""
        })

    # --------------------------------------------------------
    # ClickUp cells end with newline
    # --------------------------------------------------------

    inserts.append({
        "insert": "\n"
    })

    return inserts


# ============================================================
# CLICKUP TABLE
# ============================================================

def make_clickup_table(rows):
    """
    Create ClickUp's ql-table-embed structure.
    """

    if not rows:
        return ""

    column_count = max(
        len(row)
        for row in rows
    )

    # --------------------------------------------------------
    # Normalize rows
    # --------------------------------------------------------

    normalized = []

    for row in rows:

        row = row[:]

        while len(row) < column_count:

            row.append("")

        normalized.append(row)

    # --------------------------------------------------------
    # Rows
    # --------------------------------------------------------

    clickup_rows = []

    for _ in normalized:

        clickup_rows.append({
            "insert": {
                "id": make_id("row")
            }
        })

    # --------------------------------------------------------
    # Columns
    # --------------------------------------------------------

    column_width = max(
        100,
        FULL_TABLE_WIDTH // column_count
    )

    clickup_columns = []

    for _ in range(column_count):

        clickup_columns.append({

            "insert": {
                "id": make_id("column")
            },

            "attributes": {
                "width": str(column_width)
            }

        })

    # --------------------------------------------------------
    # Cells
    # --------------------------------------------------------

    cells = {}

    for row_number, row in enumerate(
        normalized,
        start=1
    ):

        for column_number, value in enumerate(
            row,
            start=1
        ):

            attributes = {
                "rowspan": "1",
                "colspan": "1"
            }

            # First row = header (empty HEADER_COLOR = no color)
            if row_number == 1 and HEADER_COLOR:

                attributes[
                    "cell-bg-color"
                ] = HEADER_COLOR

            cells[
                f"{row_number}:{column_number}"
            ] = {

                # IMPORTANT:
                # Use Quill Delta content instead of
                # {"insert": value}, so Markdown such as
                # `3001` is converted to code formatting.
                "content": markdown_to_quill_content(
                    value
                ),

                "attributes": attributes
            }

    # --------------------------------------------------------
    # ClickUp table JSON
    # --------------------------------------------------------

    table_data = {
        "rows": clickup_rows,
        "columns": clickup_columns,
        "cells": cells
    }

    json_data = json.dumps(
        table_data,
        separators=(",", ":"),
        ensure_ascii=False
    )

    encoded = base64.b64encode(
        json_data.encode("utf-8")
    ).decode("ascii")

    # --------------------------------------------------------
    # <colgroup>
    # --------------------------------------------------------

    colgroup = ""

    for column in clickup_columns:

        column_id = column[
            "insert"
        ]["id"]

        colgroup += (
            f'<col '
            f'data-id="{column_id}" '
            f'width="{column_width}">'
        )

    # --------------------------------------------------------
    # HTML rows
    # --------------------------------------------------------

    html_rows = []

    for row_number, row in enumerate(
        normalized,
        start=1
    ):

        row_id = clickup_rows[
            row_number - 1
        ]["insert"]["id"]

        cells_html = []

        for column_number, value in enumerate(
            row,
            start=1
        ):

            is_header = (
                row_number == 1
            )

            bg = ""

            if is_header and HEADER_COLOR:

                bg = (
                    ' data-cell-bg-color="'
                    + HEADER_COLOR
                    + '"'
                )

            rendered = inline_markdown(
                value
            )

            cell_html = (

                f'<td '

                f'data-id="{row_number}:'
                f'{column_number}" '

                f'class="ql-container ql-bubble" '

                f'colspan="1" '

                f'rowspan="1"'

                f'{bg} '

                f'style="overflow: hidden;">'

                f'<div '

                f'class="ql-editor '
                f'ql-cls-checklist '
                f'ql-reduce-empty-line-height '
                f'ql-table-embed-cell" '

                f'translate="no" '

                f'contenteditable="true">'

                f'<div class="ql-block">'

                f'{rendered}'

                f'</div>'

                f'</div>'

                f'<p style="margin-bottom: 1em;">'
                f'&nbsp;'
                f'</p>'

                f'<p style="margin-bottom: 1em;">'
                f'&nbsp;'
                f'</p>'

                f'</td>'
            )

            cells_html.append(
                cell_html
            )

        html_rows.append(

            f'<tr data-id="{row_id}">'

            + "".join(cells_html)

            + "</tr>"
        )

    # --------------------------------------------------------
    # Final ClickUp table
    # --------------------------------------------------------

    return (

        '<span '
        'class="ql-table-embed" '

        f'data-table-embed-value="{encoded}">'

        '<table class="ql-table-embed-table">'

        '<colgroup>'

        f'{colgroup}'

        '</colgroup>'

        '<tbody>'

        + "".join(html_rows)

        + '</tbody>'

        '</table>'

        '</span>'
    )


# ============================================================
# LIST PARSING
# ============================================================

def make_list(lines, start):

    first = lines[start]

    unordered = bool(
        re.match(
            r"^\s*[-*+]\s+",
            first
        )
    )

    ordered = bool(
        re.match(
            r"^\s*\d+\.\s+",
            first
        )
    )

    if not unordered and not ordered:
        return None, start

    items = []

    i = start

    while i < len(lines):

        line = lines[i]

        match = re.match(
            r"^(\s*)([-*+]|\d+\.)\s+(.*)$",
            line
        )

        if not match:
            break

        # Don't treat a horizontal rule (--- / ***) as a list
        if re.fullmatch(r"\s*([-*_])(\s*\1){2,}\s*", line):
            break

        item_tag = (
            "ol"
            if match.group(2)[0].isdigit()
            else "ul"
        )

        indent = len(
            match.group(1).replace("\t", "    ")
        )

        text = match.group(3)

        items.append(
            (
                item_tag,
                indent,
                text
            )
        )

        i += 1

    # --------------------------------------------------------
    # Flat Quill-style list
    #
    # ClickUp (Quill) does NOT support <ul> nested inside
    # <li>. Pasting nested lists creates empty bullet lines.
    # Quill's native format is a flat list where nesting is
    # expressed with class="ql-indent-N".
    # --------------------------------------------------------

    indent_stack = []

    html_parts = []

    current_tag = None

    for item_tag, indent, text in items:

        # Work out nesting level from indentation
        while indent_stack and indent < indent_stack[-1]:
            indent_stack.pop()

        if not indent_stack or indent > indent_stack[-1]:
            indent_stack.append(indent)

        level = len(indent_stack) - 1

        # Start a new list when the list type changes
        if item_tag != current_tag:

            if current_tag:
                html_parts.append(f"</{current_tag}>")

            html_parts.append(f"<{item_tag}>")

            current_tag = item_tag

        indent_class = (
            f' class="ql-indent-{level}"'
            if level > 0
            else ""
        )

        html_parts.append(
            f"<li{indent_class}>"
            f"{inline_markdown(text)}"
            f"</li>"
        )

    if current_tag:
        html_parts.append(f"</{current_tag}>")

    return (
        "".join(html_parts),
        i
    )


# ============================================================
# BLOCKQUOTE
# ============================================================

def make_blockquote(lines, start):

    quotes = []

    i = start

    while i < len(lines):

        match = re.match(
            r"^\s*>\s?(.*)$",
            lines[i]
        )

        if not match:
            break

        quotes.append(
            match.group(1)
        )

        i += 1

    if not quotes:
        return None, start

    html_quotes = []

    for quote in quotes:

        html_quotes.append(

            f'<blockquote '

            f'class="ql-quote" '

            f'data-block-id="{make_id()}">'

            f'{inline_markdown(quote)}'

            f'</blockquote>'
        )

    return (

        '<div class="ql-blockquote-container">'

        + "".join(html_quotes)

        + '</div>'
    ), i


# ============================================================
# CODE BLOCK
# ============================================================

def make_code_block(lines, start):

    if not lines[start].strip().startswith("```"):
        return None, start

    i = start + 1

    code_lines = []

    while i < len(lines):

        if lines[i].strip().startswith("```"):

            i += 1

            break

        code_lines.append(
            lines[i]
        )

        i += 1

    code = "\n".join(
        code_lines
    )

    return (

        '<pre style="margin: 0; '
        'line-height: 1.5;">'

        + esc(code)

        + '</pre>'

    ), i


# ============================================================
# MARKDOWN -> CLICKUP HTML
# ============================================================

def markdown_to_html(markdown):

    # Fresh placeholder list for each conversion
    _PLACEHOLDERS.clear()

    lines = markdown.splitlines()

    output = []

    i = 0

    paragraph = []

    def flush_paragraph():

        nonlocal paragraph

        if not paragraph:
            return

        # Convert each line separately, THEN join with <br>,
        # so the <br> isn't HTML-escaped into visible text.
        text = "<br>".join(
            inline_markdown(line)
            for line in paragraph
        )

        output.append(

            f'<div class="ql-block" '

            f'data-block-id="{make_id()}">'

            f'{text}'

            f'</div>'
        )

        paragraph = []

    while i < len(lines):

        line = lines[i]

        stripped = line.strip()

        # ----------------------------------------------------
        # Blank line
        # ----------------------------------------------------

        if not stripped:

            flush_paragraph()

            i += 1

            continue

        # ----------------------------------------------------
        # Code block
        # ----------------------------------------------------

        if stripped.startswith("```"):

            flush_paragraph()

            code_html, next_i = make_code_block(
                lines,
                i
            )

            output.append(
                code_html
            )

            i = next_i

            continue

        # ----------------------------------------------------
        # Table
        # ----------------------------------------------------

        if (

            i + 1 < len(lines)

            and "|" in line

            and is_table_separator(
                lines[i + 1]
            )

        ):

            flush_paragraph()

            rows = []

            rows.append(
                split_table_row(
                    line
                )
            )

            i += 2

            while i < len(lines):

                current = lines[i].strip()

                if (
                    not current
                    or "|" not in current
                ):
                    break

                rows.append(
                    split_table_row(
                        current
                    )
                )

                i += 1

            output.append(
                make_clickup_table(
                    rows
                )
            )

            continue

        # ----------------------------------------------------
        # Heading
        # ----------------------------------------------------

        heading = re.match(

            r"^\s*(#{1,6})\s+"
            r"(.*?)\s*#*\s*$",

            line
        )

        if heading:

            flush_paragraph()

            level = len(
                heading.group(1)
            )

            text = heading.group(2)

            extra_class = ""

            if level == 1:

                extra_class = (
                    " ql-show-draggable-anchor"
                )

            output.append(

                f'<h{level} '

                f'class="ql-heading'
                f'{extra_class}" '

                f'data-block-id="{make_id()}" '

                f'data-collapse-state="expanded">'

                f'{inline_markdown(text)}'

                f'</h{level}>'
            )

            i += 1

            continue

        # ----------------------------------------------------
        # Blockquote
        # ----------------------------------------------------

        if re.match(
            r"^\s*>\s?",
            line
        ):

            flush_paragraph()

            quote_html, next_i = make_blockquote(
                lines,
                i
            )

            output.append(
                quote_html
            )

            i = next_i

            continue

        # ----------------------------------------------------
        # Horizontal rule (must be checked BEFORE lists,
        # because "* * *" / "- - -" also look like bullets)
        # ----------------------------------------------------

        if re.fullmatch(
            r"\s*([-*_])(\s*\1){2,}\s*",
            line
        ):

            flush_paragraph()

            output.append(
                "<hr>"
            )

            i += 1

            continue

        # ----------------------------------------------------
        # Lists
        # ----------------------------------------------------

        if (

            re.match(
                r"^\s*[-*+]\s+",
                line
            )

            or

            re.match(
                r"^\s*\d+\.\s+",
                line
            )

        ):

            flush_paragraph()

            list_html, next_i = make_list(
                lines,
                i
            )

            # Safety: never get stuck on the same line
            if next_i > i:

                output.append(
                    list_html
                )

                i = next_i

                continue

        # ----------------------------------------------------
        # Normal paragraph
        # ----------------------------------------------------

        paragraph.append(
            line
        )

        i += 1

    flush_paragraph()

    # Trailing empty block so the real last paragraph is
    # fully terminated. Otherwise ClickUp merges the last
    # pasted line into the line under the cursor and can
    # mangle it.
    output.append(
        '<div class="ql-block" '
        f'data-block-id="{make_id()}"><br></div>'
    )

    # IMPORTANT:
    # Join without "\n". Whitespace text nodes between
    # blocks get pasted by ClickUp as extra empty lines,
    # which become empty bullets when next to a list.
    return "".join(
        output
    )


# ============================================================
# WINDOWS RICH HTML CLIPBOARD
# ============================================================

def copy_to_clipboard(
    html_content,
    plain_text
):

    # --------------------------------------------------------
    # Windows HTML Clipboard format
    # --------------------------------------------------------

    fragment = (

        "<html>"
        "<body>"

        "<!--StartFragment-->"

        + html_content

        + "<!--EndFragment-->"

        "</body>"
        "</html>"
    )

    header_template = (

        "Version:0.9\r\n"

        "StartHTML:{:010d}\r\n"

        "EndHTML:{:010d}\r\n"

        "StartFragment:{:010d}\r\n"

        "EndFragment:{:010d}\r\n"
    )

    dummy_header = header_template.format(
        0,
        0,
        0,
        0
    )

    start_html = len(
        dummy_header.encode("utf-8")
    )

    start_fragment = (

        start_html

        + len(
            "<html><body>"
            "<!--StartFragment-->"
            .encode("utf-8")
        )
    )

    end_fragment = (

        start_fragment

        + len(
            html_content.encode("utf-8")
        )
    )

    end_html = (

        start_html

        + len(
            fragment.encode("utf-8")
        )
    )

    header = header_template.format(

        start_html,

        end_html,

        start_fragment,

        end_fragment
    )

    clipboard_html = (

        header

        + fragment
    )

    # --------------------------------------------------------
    # Windows clipboard
    # --------------------------------------------------------

    win32clipboard.OpenClipboard()

    try:

        win32clipboard.EmptyClipboard()

        # HTML
        html_format = (
            win32clipboard.RegisterClipboardFormat(
                "HTML Format"
            )
        )

        win32clipboard.SetClipboardData(

            html_format,

            clipboard_html.encode(
                "utf-8"
            )
        )

        # Plain text fallback
        #
        # IMPORTANT:
        # This is the ORIGINAL Markdown,
        # not the generated HTML.
        win32clipboard.SetClipboardData(

            win32con.CF_UNICODETEXT,

            plain_text
        )

    finally:

        win32clipboard.CloseClipboard()


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "========================================"
    )

    print(
        " Markdown -> ClickUp Clipboard"
    )

    print(
        "========================================"
    )

    print()

    # --------------------------------------------------------
    # File argument
    # --------------------------------------------------------

    if len(sys.argv) >= 2:

        file_path = Path(
            sys.argv[1]
        )

    else:

        file_path = Path(
            input(
                "Markdown file: "
            ).strip().strip('"')
        )

    # --------------------------------------------------------
    # Check file
    # --------------------------------------------------------

    if not file_path.exists():

        print()

        print(
            f"ERROR: File does not exist:\n"
            f"{file_path}"
        )

        return

    # --------------------------------------------------------
    # Read Markdown
    # --------------------------------------------------------

    print(
        f"Reading: {file_path}"
    )

    markdown = file_path.read_text(
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Convert
    # --------------------------------------------------------

    print(
        "Converting Markdown..."
    )

    converted_html = markdown_to_html(
        markdown
    )

    # --------------------------------------------------------
    # Clipboard
    # --------------------------------------------------------

    print(
        "Copying rich HTML to clipboard..."
    )

    copy_to_clipboard(

        converted_html,

        markdown
    )

    # --------------------------------------------------------
    # Done
    # --------------------------------------------------------

    print()

    print(
        "DONE!"
    )

    print()

    print(
        "Go to ClickUp and press:"
    )

    print()

    print(
        "    Ctrl + V"
    )

    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()