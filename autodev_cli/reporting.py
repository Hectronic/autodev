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


def render_sectioned_markdown_to_html(sections: list[dict], metadata: dict | None = None) -> str:
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

    navigation_items = []
    rendered_sections = []
    for section in sections:
        section_id = _slugify_html_id(section.get("id") or section.get("title") or "section")
        section_title = html.escape(section.get("title") or section_id)
        navigation_items.append(f'<a href="#{section_id}">{section_title}</a>')
        rendered_sections.append(
            f"""
            <article class="section-card" id="{section_id}">
              <div class="section-header">
                <h2>{section_title}</h2>
                <a class="back-to-top" href="#top">Volver arriba</a>
              </div>
              <div class="section-body">
                {_markdown_to_html(section.get("markdown") or "")}
              </div>
            </article>
            """.strip()
        )

    nav_html = "".join(navigation_items) or '<span class="muted">Sin secciones</span>'
    sections_html = "\n".join(rendered_sections) or '<article class="section-card"><p>Sin contenido disponible.</p></article>'
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4efe7;
      --panel: #fffdf8;
      --panel-strong: #ffffff;
      --text: #1e2933;
      --muted: #61707c;
      --accent: #8b5e34;
      --accent-2: #365c7d;
      --border: #ddd3c5;
      --shadow: 0 18px 44px rgba(30, 41, 51, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(139, 94, 52, 0.12), transparent 24%),
        radial-gradient(circle at top right, rgba(54, 92, 125, 0.10), transparent 20%),
        linear-gradient(180deg, #efe4d5 0%, var(--bg) 24%, #fbf8f2 100%);
      color: var(--text);
      font-family: Inter, "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      line-height: 1.6;
    }}
    a {{ color: var(--accent-2); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 18px 56px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,250,244,0.96));
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 28px;
      margin-bottom: 18px;
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: clamp(2rem, 3vw, 3.2rem);
      letter-spacing: -0.03em;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1fr 300px;
      gap: 18px;
      align-items: start;
    }}
    .meta, .toc {{
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 10px 22px rgba(30, 41, 51, 0.06);
      padding: 18px;
    }}
    .meta ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .toc {{
      position: sticky;
      top: 16px;
    }}
    .toc h2, .meta h2 {{
      margin-top: 0;
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}
    .toc nav {{
      display: grid;
      gap: 8px;
    }}
    .toc a {{
      display: block;
      padding: 9px 12px;
      border-radius: 12px;
      background: #faf6ef;
      border: 1px solid transparent;
    }}
    .toc a:hover {{
      border-color: var(--border);
      background: #fff;
      text-decoration: none;
    }}
    .content {{
      display: grid;
      gap: 18px;
    }}
    .section-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 24px;
      scroll-margin-top: 18px;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: baseline;
      border-bottom: 1px solid rgba(221, 211, 197, 0.8);
      margin-bottom: 18px;
      padding-bottom: 12px;
    }}
    .section-header h2 {{
      margin: 0;
      font-size: 1.35rem;
      letter-spacing: -0.02em;
    }}
    .back-to-top {{
      font-size: 0.92rem;
      white-space: nowrap;
    }}
    .section-body :is(h1, h2, h3) {{
      margin-top: 1.4em;
    }}
    .section-body pre {{
      overflow-x: auto;
      background: #111827;
      color: #f9fafb;
      padding: 16px;
      border-radius: 14px;
    }}
    .section-body code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.95em;
    }}
    .section-body ul {{
      padding-left: 22px;
    }}
    .muted {{ color: var(--muted); }}
    @media (max-width: 960px) {{
      .hero-grid {{
        grid-template-columns: 1fr;
      }}
      .toc {{
        position: static;
      }}
    }}
  </style>
</head>
<body>
  <main id="top">
    <section class="hero">
      <h1>{title}</h1>
      <div class="hero-grid">
        <div class="meta">
          <h2>Metadatos</h2>
          <ul>
            {''.join(meta_items)}
          </ul>
        </div>
        <aside class="toc">
          <h2>Indice</h2>
          <nav>
            {nav_html}
          </nav>
        </aside>
      </div>
    </section>
    <section class="content">
      {sections_html}
    </section>
  </main>
</body>
</html>
"""


def write_html_report(html_path: Path, markdown_text: str, metadata: dict | None = None) -> Path:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_markdown_to_html(markdown_text, metadata), encoding="utf-8")
    return html_path


def write_sectioned_html_report(html_path: Path, sections: list[dict], metadata: dict | None = None) -> Path:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_sectioned_markdown_to_html(sections, metadata), encoding="utf-8")
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


def _slugify_html_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"
