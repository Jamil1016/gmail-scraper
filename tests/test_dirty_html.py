from ci_email_scraper.parser import _clean_html


class TestHiddenSpanRemoval:
    def test_strips_zero_width_tracking_span(self) -> None:
        html = """
        <p>Build status: <span style="font-size:0">tracker_abc123</span>success</p>
        """
        cleaned = _clean_html(html)
        assert "tracker_abc123" not in cleaned
        assert "success" in cleaned

    def test_strips_one_pt_tracking_span(self) -> None:
        html = '<p>Status: <span style="font-size: 1pt">hidden</span>success</p>'
        cleaned = _clean_html(html)
        assert "hidden" not in cleaned
        assert "success" in cleaned

    def test_keeps_normal_spans(self) -> None:
        html = '<p>Status: <span style="color: red">success</span></p>'
        cleaned = _clean_html(html)
        assert "success" in cleaned


class TestWordRejoin:
    def test_rejoins_split_uppercase_letter(self) -> None:
        # BeautifulSoup get_text(" ") splits "Construction" → "C onstruction"
        # when a tracking span sits between "C" and "onstruction".
        # _clean_html should rejoin them.
        html = '<p><span style="font-size:0">x</span>C<span style="font-size:0">y</span>onstruction Engineer</p>'
        cleaned = _clean_html(html)
        assert "Construction Engineer" in cleaned
        assert "C onstruction" not in cleaned

    def test_does_not_merge_unrelated_words(self) -> None:
        html = "<p>Hello World</p>"
        cleaned = _clean_html(html)
        assert "Hello World" in cleaned


class TestScriptStyleStripping:
    def test_strips_script_tags(self) -> None:
        html = "<p>Visible</p><script>alert('x')</script>"
        cleaned = _clean_html(html)
        assert "Visible" in cleaned
        assert "alert" not in cleaned

    def test_strips_style_tags(self) -> None:
        html = "<p>Visible</p><style>body { color: red; }</style>"
        cleaned = _clean_html(html)
        assert "Visible" in cleaned
        assert "color: red" not in cleaned
