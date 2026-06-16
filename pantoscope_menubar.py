#!/usr/bin/env python3
import rumps
import subprocess
import os
import webbrowser
from pathlib import Path

APP_DIR = Path(__file__).parent / "sales-command-center"
CLOUDFLARED = "/opt/homebrew/bin/cloudflared"
PORT = "5050"

class PantoscopeMenuBar(rumps.App):
    def __init__(self):
        super().__init__("🔴", quit_button=None)
        self.flask_proc = None
        self.tunnel_proc = None
        self.status_item = rumps.MenuItem("Status: Offline")
        self.start_item = rumps.MenuItem("Start", callback=self.start)
        self.stop_item = rumps.MenuItem("Stop")
        self.menu = [
            self.status_item,
            None,
            self.start_item,
            self.stop_item,
            None,
            rumps.MenuItem("Open pantoscope.org", callback=self.open_site),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]
        # Hide dock icon once the run loop starts
        t = rumps.Timer(self._hide_dock, 0.1)
        t.start()

    def _hide_dock(self, sender):
        from AppKit import NSApp, NSApplicationActivationPolicyAccessory
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        sender.stop()

    def start(self, _):
        env = os.environ.copy()
        env["PORT"] = PORT
        self.flask_proc = subprocess.Popen(
            ["/opt/homebrew/bin/python3", "shell/app.py"],
            cwd=str(APP_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.tunnel_proc = subprocess.Popen(
            [CLOUDFLARED, "tunnel", "run", "pantoscope"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.title = "🟢"
        self.status_item.title = "Status: Running"
        self.start_item.set_callback(None)
        self.stop_item.set_callback(self.stop)

    def stop(self, _):
        if self.flask_proc:
            self.flask_proc.terminate()
            self.flask_proc = None
        if self.tunnel_proc:
            self.tunnel_proc.terminate()
            self.tunnel_proc = None
        self.title = "🔴"
        self.status_item.title = "Status: Offline"
        self.start_item.set_callback(self.start)
        self.stop_item.set_callback(None)

    def open_site(self, _):
        webbrowser.open("https://pantoscope.org")

    def quit_app(self, _):
        self.stop(None)
        rumps.quit_application()

if __name__ == "__main__":
    PantoscopeMenuBar().run()
