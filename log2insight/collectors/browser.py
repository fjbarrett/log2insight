"""Active browser tab URL, queried only when a known browser is frontmost.
Requires Automation permission for that browser (prompts once)."""

from ..config import BROWSER_SCRIPTS
from ..util import osa


def browser_url(frontmost_app_name):
    spec = BROWSER_SCRIPTS.get(frontmost_app_name or "")
    if not spec:
        return None
    app, tab_expr = spec
    url = osa(f'tell application "{app}" to get URL of {tab_expr}')
    return url or None
