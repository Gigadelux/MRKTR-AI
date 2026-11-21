import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "streamlit"))

import orb  # noqa: E402


def test_orb_is_self_contained():
    html = orb.orb_html()
    assert 'src="three.min.js"' not in html  # three.js is inlined
    assert "THREE.WebGLRenderer" in html
    assert "http://" not in html.replace("http://www.w3.org", "").split("<script>", 1)[0]
    assert "https://" not in html.split("<script>", 1)[0]  # no network needed by the page itself
