"""
Wrapper that launches the extension
"""
import gi

gi.require_version("Notify", "0.7")
gi.require_version("Gdk", "3.0")
from gi.repository import Notify, Gdk  # pylint: disable=wrong-import-position
from keepassxc.extension import (  # pylint: disable=wrong-import-position
    KeepassxcExtension,
)

if __name__ == "__main__":
    Gdk.set_program_class("KeePassXC Search")
    Notify.init("ulauncher-keepassxc")
    KeepassxcExtension().run()
    Notify.uninit()
