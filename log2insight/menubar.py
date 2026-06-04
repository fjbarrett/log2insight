"""macOS menu bar app: a lightweight controller and viewer for the collection
agent. Collection itself stays in the headless launchd daemon (see agent.py);
this process just shows live status, toggles the agent, and opens the Dashboard
and Settings as native WKWebView windows.

Requires the `menubar` extra (`pip install -e ".[menubar]"`), which pulls in
rumps and PyObjC. The daemon never imports this module, so the collector stays
dependency-free.
"""

import html
import json

import rumps
from AppKit import (
    NSApp,
    NSBackingStoreBuffered,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSMakeRect, NSObject
from WebKit import WKWebView, WKWebViewConfiguration

from . import agent, dashboard, db, settings_store

_WINDOW_STYLE = (
    NSWindowStyleMaskTitled
    | NSWindowStyleMaskClosable
    | NSWindowStyleMaskResizable
    | NSWindowStyleMaskMiniaturizable
)


class _Bridge(NSObject):
    """WKScriptMessageHandler that forwards JS `postMessage` to a Python
    callback. The callback is attached after construction (`bridge.callback =`)."""

    callback = None

    def userContentController_didReceiveScriptMessage_(self, _ucc, message):
        if self.callback is not None:
            self.callback(str(message.body()))


class L2IApp(rumps.App):
    def __init__(self):
        super().__init__("log2insight", title="📊", quit_button=None)
        self._windows = {}  # key -> {"window", "webview", "bridge"}

        self.status_item = rumps.MenuItem("…")          # disabled status line
        self.last_item = rumps.MenuItem("")             # disabled "last sample"
        self.toggle_item = rumps.MenuItem(
            "Start Collection", callback=self.toggle_collection
        )
        self.menu = [
            self.status_item,
            self.last_item,
            None,
            rumps.MenuItem("Open Dashboard", callback=self.open_dashboard),
            rumps.MenuItem("Settings…", callback=self.open_settings),
            None,
            self.toggle_item,
            rumps.MenuItem("Reveal Data Folder", callback=self.reveal_data),
            None,
            rumps.MenuItem("Quit log2insight", callback=rumps.quit_application),
        ]

        self._timer = rumps.Timer(self.refresh, 6)
        self._timer.start()
        self.refresh(None)

    # --- live status -----------------------------------------------------

    def refresh(self, _timer):
        running = agent.is_loaded()
        self.toggle_item.title = "Stop Collection" if running else "Start Collection"

        total, last = 0, None
        try:
            conn = db.connect()
            try:
                total = conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0]
                row = conn.execute(
                    "SELECT ts FROM activity ORDER BY epoch DESC LIMIT 1"
                ).fetchone()
                last = row["ts"] if row else None
            finally:
                conn.close()
        except Exception:
            pass

        dot = "●" if running else "○"
        state = "Collecting" if running else "Stopped"
        self.status_item.title = f"{dot}  {state} · {total:,} samples"
        self.last_item.title = f"Last sample: {last or 'none yet'}"

        dash = self._windows.get("dashboard")
        if dash and dash["window"].isVisible():
            dash["webview"].loadHTMLString_baseURL_(
                dashboard.render(agent_running=running), None
            )

    # --- menu actions ----------------------------------------------------

    def toggle_collection(self, _sender):
        if agent.is_loaded():
            agent.uninstall()
        else:
            agent.install()
        self.refresh(None)

    def open_dashboard(self, _sender):
        page = dashboard.render(agent_running=agent.is_loaded())
        self._show_web("dashboard", "log2insight — Dashboard", page, 760, 660)

    def open_settings(self, _sender):
        self._show_web(
            "settings", "log2insight — Settings", self._settings_html(),
            480, 560, on_message=self._on_settings_saved,
        )

    def reveal_data(self, _sender):
        import subprocess
        from . import config
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(config.DATA_DIR)], check=False)

    # --- settings bridge -------------------------------------------------

    def _on_settings_saved(self, payload):
        try:
            values = json.loads(payload)
        except ValueError:
            return
        settings_store.save(values)
        ok, msg = agent.restart()
        result = json.dumps({"ok": bool(ok), "msg": msg})
        win = self._windows.get("settings")
        if win:
            win["webview"].evaluateJavaScript_completionHandler_(
                f"window.l2iSaved({result});", None
            )
        self.refresh(None)

    # --- WKWebView window plumbing --------------------------------------

    def _show_web(self, key, title, page, width, height, on_message=None):
        existing = self._windows.get(key)
        if existing is not None:
            existing["webview"].loadHTMLString_baseURL_(page, None)
            existing["window"].makeKeyAndOrderFront_(None)
            NSApp().activateIgnoringOtherApps_(True)
            return

        configuration = WKWebViewConfiguration.alloc().init()
        bridge = None
        if on_message is not None:
            bridge = _Bridge.alloc().init()
            bridge.callback = on_message
            configuration.userContentController().addScriptMessageHandler_name_(
                bridge, "l2i"
            )

        frame = NSMakeRect(0, 0, width, height)
        webview = WKWebView.alloc().initWithFrame_configuration_(frame, configuration)
        webview.loadHTMLString_baseURL_(page, None)

        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, _WINDOW_STYLE, NSBackingStoreBuffered, False
        )
        window.setTitle_(title)
        window.setContentView_(webview)
        window.setReleasedWhenClosed_(False)  # we manage the lifetime ourselves
        window.center()
        window.makeKeyAndOrderFront_(None)
        NSApp().activateIgnoringOtherApps_(True)

        self._windows[key] = {"window": window, "webview": webview, "bridge": bridge}

    # --- settings page ---------------------------------------------------

    def _settings_html(self):
        current = settings_store.load()
        rows = []
        for key, label, cast, _default, minimum, help_text in settings_store.FIELDS:
            step = "1" if cast is int else "any"
            rows.append(f"""
            <label class="row">
              <span class="lbl">{html.escape(label)}</span>
              <input type="number" data-key="{html.escape(key)}"
                     value="{current[key]}" min="{minimum}" step="{step}">
              <span class="help">{html.escape(help_text)}</span>
            </label>""")
        return _SETTINGS_HTML.replace("__ROWS__", "\n".join(rows))


_SETTINGS_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font: 14px/1.5 -apple-system, BlinkMacSystemFont, sans-serif;
  margin: 0; padding: 22px 26px 28px; background: Canvas; color: CanvasText; }
h1 { font-size: 17px; margin: 0 0 4px; font-weight: 650; }
.intro { color: color-mix(in srgb, CanvasText 55%, transparent);
  font-size: 13px; margin: 0 0 18px; }
.row { display: grid; grid-template-columns: 1fr 96px; gap: 4px 14px;
  align-items: center; padding: 10px 0;
  border-top: 1px solid color-mix(in srgb, CanvasText 12%, transparent); }
.lbl { font-weight: 550; }
input { font: inherit; text-align: right; padding: 5px 8px; border-radius: 7px;
  border: 1px solid color-mix(in srgb, CanvasText 25%, transparent);
  background: color-mix(in srgb, CanvasText 5%, Canvas); color: CanvasText; }
.help { grid-column: 1 / -1; font-size: 12px;
  color: color-mix(in srgb, CanvasText 50%, transparent); }
.actions { display: flex; align-items: center; gap: 14px; margin-top: 22px; }
button { font: inherit; font-weight: 600; padding: 7px 16px; border: 0;
  border-radius: 8px; background: AccentColor; color: white; cursor: pointer; }
#status { font-size: 13px; }
#status.ok { color: #34c759; } #status.err { color: #ff3b30; }
</style></head>
<body>
<h1>Settings</h1>
<p class="intro">Saving restarts the collection agent so changes take effect.</p>
<form onsubmit="l2iSave(); return false;">
__ROWS__
<div class="actions">
  <button type="submit">Save</button>
  <span id="status"></span>
</div>
</form>
<script>
function l2iSave() {
  const v = {};
  document.querySelectorAll('input[data-key]').forEach(function (i) {
    v[i.dataset.key] = parseFloat(i.value);
  });
  window.webkit.messageHandlers.l2i.postMessage(JSON.stringify(v));
}
window.l2iSaved = function (res) {
  const s = document.getElementById('status');
  s.textContent = res.ok ? 'Saved ✓ — collector reloaded' : ('Error: ' + res.msg);
  s.className = res.ok ? 'ok' : 'err';
};
</script>
</body></html>"""


def main():
    L2IApp().run()


if __name__ == "__main__":
    main()
