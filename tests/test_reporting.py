from unittest.mock import patch

from autodev_cli.reporting import open_html_report, render_markdown_to_html


def test_render_markdown_to_html_escapes_and_renders_code(tmp_path):
    markdown = "# Informe\n\n- item 1\n\n```py\nprint('<x> & y')\n```\n"

    html = render_markdown_to_html(
        markdown,
        {
            "title": "demo",
            "branch_name": "feature/x",
            "status": "completed",
        },
    )

    assert "<h1>Informe</h1>" in html
    assert "<pre><code>" in html
    assert "&lt;x&gt;" in html
    assert "feature/x" in html


def test_open_html_report_returns_webbrowser_result(tmp_path):
    html_path = tmp_path / "report.html"
    html_path.write_text("ok", encoding="utf-8")

    with patch("autodev_cli.reporting.webbrowser.open", return_value=False) as mock_open:
        assert open_html_report(html_path) is False

    mock_open.assert_called_once()
