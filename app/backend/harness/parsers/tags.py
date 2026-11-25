"""Expression tags: ``<e:name>`` in the agent's reply -> at most one sticker.

The first tag with a known name wins; unknown names give no sticker. Every tag is removed from
the text. Tags never trigger audio. Works on a whole reply (no streaming yet).
"""

from __future__ import annotations

import re

TAG = re.compile(r"<e:([A-Za-z0-9_-]{1,32})>")
ANY_TAG = re.compile(r"<e:[^>\n]{0,64}>")  # also strip malformed names


def parse_reply(text: str, sticker_names: set[str] | frozenset[str]) -> tuple[str, str | None]:
    sticker = next((m.group(1) for m in TAG.finditer(text) if m.group(1) in sticker_names), None)
    clean = ANY_TAG.sub("", text)
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = "\n".join(line.strip() for line in clean.splitlines()).strip()
    return clean, sticker
