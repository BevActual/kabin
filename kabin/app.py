import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from . import style  # noqa: E402
from .window import MainWindow  # noqa: E402

APP_ID = "com.andrewbevington.Kabin"


class KabinApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None
        self._build_actions()

    def _build_actions(self):
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_a: self._quit_cleanly())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", lambda *_a: self.window and self.window.refresh())
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5"])

    def _quit_cleanly(self):
        # Gtk.Application.quit() does not emit close-request, so quitting
        # through the action (Ctrl+Q) would skip MainWindow's shutdown
        # entirely: window geometry unsaved, in-flight playback progress
        # never persisted, the host's HTTP socket and avahi-publish
        # subprocess left running, artwork queues never closed. Close the
        # window first so that all runs, exactly like the title bar's
        # close button.
        if self.window:
            self.window.close()
        self.quit()

    def do_activate(self):
        if not self.window:
            style.apply()
            self.window = MainWindow(application=self)
        self.window.present()


def main():
    app = KabinApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
