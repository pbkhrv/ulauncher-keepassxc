"""
Simple passphrase entry Gtk window
"""
from typing import Optional, Callable
import gi

gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-order
from gi.repository import Gtk, Gdk  # noqa: E402


class GtkPassphraseEntryWindow(Gtk.Window):
    """
    Gtk window with one masked text input field
    """

    def __init__(
        self,
        verify_passphrase_fn: Optional[Callable[[str], bool]] = None,
        icon_file: Optional[str] = None,
    ) -> None:
        Gtk.Window.__init__(self, title="Enter Passphrase")

        self.verify_passphrase_fn = verify_passphrase_fn

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        self.passphrase = ""
        self.entry = Gtk.Entry()
        self.entry.set_text("")
        self.entry.set_editable(True)
        self.entry.set_visibility(False)
        self.entry.props.max_width_chars = 50
        self.entry.connect("activate", self.enter_pressed)
        self.entry.connect("key-press-event", self.key_pressed)
        vbox.pack_start(self.entry, True, True, 0)

        self.label = Gtk.Label("")
        vbox.pack_start(self.label, True, True, 0)

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        if icon_file:
            self.set_default_icon_from_file(icon_file)

    def close_window(self) -> None:
        """
        Stop it
        """
        self.destroy()
        Gtk.main_quit()

    def enter_pressed(self, entry: Gtk.Entry) -> None:
        """
        When Enter pressed, verify the passphrase (if able),
        close the window and return entered passphrase
        """
        passphrase = entry.get_text()
        if self.verify_passphrase_fn:
            self.show_verifying_passphrase()
            if self.verify_passphrase_fn(passphrase):
                self.passphrase = passphrase
                self.close_window()
            else:
                self.show_incorrect_passphrase()
        else:
            self.passphrase = passphrase
            self.close_window()

    def key_pressed(self, _, event) -> None:
        """
        When Esc pressed, close the window
        """
        if event.hardware_keycode == 9:
            self.passphrase = ""
            self.close_window()

    def show_verifying_passphrase(self) -> None:
        """
        Tell the user that we are busy verifying the passphrase
        """
        self.label.set_text("Verifying passphrase...")

    def show_incorrect_passphrase(self) -> None:
        """
        Tell the user that the passphrase failed verification
        """
        self.label.set_markup(
            '<span foreground="red">Incorrect passphrase. Please try again.</span>'
        )
        self.entry.set_text("")

    def read_passphrase(self) -> str:
        """
        Show the window and wait for user to enter passphrase
        """
        self.connect("destroy", Gtk.main_quit)
        self.show_all()
        Gtk.main()
        return self.passphrase


if __name__ == "__main__":
    Gdk.set_program_class("KeePassXC search")
    # pylint: disable=invalid-name
    window = GtkPassphraseEntryWindow(icon_file="images/keepassxc-search.svg")
    print(window.read_passphrase())
