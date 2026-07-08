"""Phase A: HTML content extraction skips chrome; tags stay clean."""

from app.api.v1 import vault

SAMPLE_HTML = b"""
<html>
  <head><title>Volume-weighted average price - Wikipedia</title>
  <meta name="description" content="VWAP is a trading benchmark."></head>
  <body>
    <nav id="site-navigation">Jump to content Main menu Random article</nav>
    <header class="masthead">Donate Create account Log in</header>
    <div class="mw-parser-output">
      <p>VWAP is the ratio of the value of a security traded to total volume
      over a session.[2] Some traders use crossings of price through the VWAP
      line as entry signals.[8]</p>
      <h2>Algorithmic execution [edit]</h2>
      <p>Trading algorithms that target VWAP are volume participation.</p>
    </div>
    <footer class="site-footer">Privacy policy Terms of use Cookie</footer>
  </body>
</html>
"""


def test_extraction_prefers_main_content_and_strips_chrome() -> None:
    imported = vault._html_import(SAMPLE_HTML, "https://en.wikipedia.org/wiki/VWAP", "text/html")
    body = imported.body.lower()
    # Real article content is present...
    assert "vwap is the ratio" in body
    assert "entry signals" in body
    # ...and the navigation/footer chrome is gone.
    assert "jump to content" not in body
    assert "main menu" not in body
    assert "privacy policy" not in body
    assert "log in" not in body


def test_citation_and_edit_markers_are_stripped() -> None:
    imported = vault._html_import(SAMPLE_HTML, "https://en.wikipedia.org/wiki/VWAP", "text/html")
    assert "[2]" not in imported.body
    assert "[8]" not in imported.body
    assert "[edit]" not in imported.body.lower()


def test_tags_drop_domain_and_noise_and_are_capped() -> None:
    imported = vault._html_import(SAMPLE_HTML, "https://en.wikipedia.org/wiki/VWAP", "text/html")
    assert len(imported.tags) <= vault.MAX_TAGS
    for tag in imported.tags:
        assert "." not in tag  # no domain tags like en.wikipedia.org
        assert tag not in {"trade", "journal", "paper", "article"}


def test_clean_text_removes_citation_markers() -> None:
    assert vault._clean_text("price crosses VWAP[12] on volume") == "price crosses VWAP on volume"
    assert vault._clean_text("Section [ edit ] header") == "Section header"
