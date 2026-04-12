from __future__ import annotations

import html
import re
import webbrowser
from pathlib import Path


def render_markdown_to_html(markdown_text: str, metadata: dict | None = None) -> str:
    metadata = metadata or {}
    title = html.escape(metadata.get("title", "autodev summary"))
    meta_items = []
    for key in [
        "session_id",
        "branch_name",
        "base_branch",
        "merge_base_sha",
        "agent",
        "project_path",
        "status",
        "results_dir",
    ]:
        value = metadata.get(key)
        if value:
            meta_items.append(
                f"<li><strong>{html.escape(key.replace('_', ' ').title())}:</strong> {html.escape(str(value))}</li>"
            )

    body = _markdown_to_html(markdown_text or "")
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f3ec;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #52606d;
      --accent: #8f5b34;
      --border: #d9d2c7;
    }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #efe7dc 0%, var(--bg) 28%, #fbfaf7 100%);
      color: var(--text);
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
    }}
    main {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: 0 20px 45px rgba(31, 41, 51, 0.08);
      padding: 24px;
      margin-bottom: 20px;
    }}
    h1, h2, h3 {{ line-height: 1.2; }}
    h1 {{ margin-top: 0; }}
    .meta ul {{
      padding-left: 18px;
      margin: 0;
    }}
    .content :is(h1, h2, h3) {{
      margin-top: 1.4em;
    }}
    .content pre {{
      overflow-x: auto;
      background: #111827;
      color: #f9fafb;
      padding: 16px;
      border-radius: 12px;
    }}
    .content code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.95em;
    }}
    .content ul {{
      padding-left: 22px;
    }}
    .muted {{ color: var(--muted); }}
  </style>
</head>
<body>
  <main>
    <section class="card meta">
      <h1>{title}</h1>
      <ul>
        {''.join(meta_items)}
      </ul>
    </section>
    <section class="card content">
      {body}
    </section>
  </main>
</body>
</html>
"""


def write_html_report(html_path: Path, markdown_text: str, metadata: dict | None = None) -> Path:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_markdown_to_html(markdown_text, metadata), encoding="utf-8")
    return html_path


def open_html_report(html_path: Path) -> bool:
    return webbrowser.open(html_path.resolve().as_uri())


def _markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    parts: list[str] = []
    paragraph: list[str] = []
    in_list = False
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            parts.append(f"<p>{_inline_markup(' '.join(paragraph))}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            parts.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                parts.append("</code></pre>")
                in_code = False
            else:
                parts.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            parts.append(html.escape(line) + "\n")
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            continue

        heading_level = len(stripped) - len(stripped.lstrip("#"))
        if heading_level and stripped.startswith("#"):
            flush_paragraph()
            close_list()
            heading_text = stripped[heading_level:].strip()
            parts.append(f"<h{heading_level}>{_inline_markup(heading_text)}</h{heading_level}>")
            continue

        if stripped.startswith(("- ", "* ")):
            flush_paragraph()
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{_inline_markup(stripped[2:].strip())}</li>")
            continue

        paragraph.append(stripped)

    flush_paragraph()
    close_list()
    if in_code:
        parts.append("</code></pre>")
    return "\n".join(parts)


def _inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped
