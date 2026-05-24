"""Email parser — HTML body to ParsedEmail.

This file holds:
  - _clean_html: BeautifulSoup-based HTML normalization (Phase 3)
  - parse_email + vendor extractors (Phase 4)
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

_TRACKING_SPAN_STYLE = re.compile(r"font-size:\s*[01](pt|px|p?)?\b", re.IGNORECASE)
_WORD_REJOIN = re.compile(r"\b([A-Z])\s([a-z])")


def _clean_html(html: str) -> str:
    """Normalize raw email HTML into searchable plain text.

    Three steps:
      1. Strip <script> and <style> tags entirely.
      2. Strip zero-width / 1pt tracking spans (common email tracking technique
         that breaks plain-text extraction).
      3. Collapse whitespace and rejoin single uppercase letters that
         BeautifulSoup's get_text() splits apart.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. Remove <script> and <style> entirely
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # 2. Remove zero-width tracking spans
    for span in soup.find_all("span", style=_TRACKING_SPAN_STYLE):
        span.decompose()

    # 3. Extract text + collapse whitespace
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    # Rejoin single uppercase letters BS split apart from following lowercase
    text = _WORD_REJOIN.sub(r"\1\2", text)

    return text
