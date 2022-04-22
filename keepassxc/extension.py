"""
Search KeePassXC password databases and copy passwords to the clipboard.
"""
import logging
import os
import sys
from threading import Timer
from typing import Optional
import gi
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import (
    KeywordQueryEvent,
    ItemEnterEvent,
    PreferencesUpdateEvent,
)
from ulauncher.api.shared.action.BaseAction import BaseAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction

from .keepassxc_db import (
    KeepassxcDatabase,
    KeepassxcCliNotFoundError,
    KeepassxcFileNotFoundError,
    KeepassxcCliError,
)
from .gtk_passphrase_entry import GtkPassphraseEntryWindow
from .wmctrl import activate_window_by_class_name, WmctrlNotFoundError
from . import render

gi.require_version("Notify", "0.7")
# pylint: disable=wrong-import-order
from gi.repository import Notify  # noqa: E402


logger = logging.getLogger(__name__)


def activate_passphrase_window() -> None:
    """
    Use wmctrl to bring the passphrase window to the top

    Class name is set somewhere inside Gtk/Gdk to the "file name" + "program class"
    "Program class" is set in below
    """
    try:
        activate_window_by_class_name("main.py.KeePassXC Search")
    except WmctrlNotFoundError:
        logger.warning(
            "wmctrl not installed, unable to activate passphrase entry window"
        )


def current_script_path() -> str:
    """
    Return path to where the currently executing script is located
    """
    return os.path.abspath(os.path.dirname(sys.argv[0]))


class KeepassxcExtension(Extension):
    """ Extension class, coordinates everything """

    # REORG: break up into Keepassxc and KeepassxcExtension, like NotesNv one
    # store instances of keepassxc_db in a dict keyed by "database_id"
    # that's tied to preferences - allows for multidb support
    def __init__(self):
        super(KeepassxcExtension, self).__init__()
        self.keepassxc_db = KeepassxcDatabase()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener(self.keepassxc_db))
        self.subscribe(ItemEnterEvent, ItemEnterEventListener(self.keepassxc_db))
        self.subscribe(
            PreferencesUpdateEvent, PreferencesUpdateEventListener(self.keepassxc_db)
        )
        self.active_entry = None
        self.active_entry_search_restore = None
        self.recent_active_entries = []

    def get_db_path(self) -> str:
        """
        Normalized and expanded path to the database file
        """
        return os.path.expanduser(self.preferences["database-path"])

    def get_max_result_items(self) -> int:
        """
        Maximum number of search results to show on screen
        """
        return int(self.preferences["max-results"])

    def get_inactivity_lock_timeout(self) -> int:
        """
        How long to wait to lock the database after last user interaction
        """
        return int(self.preferences["inactivity-lock-timeout"])
    
    def get_yubikey_slot(self) -> str:
        """
        Get the YubiKey slot number to use
        """
        return self.preferences["yubikey-slot"]

    def set_active_entry(self, keyword: str, entry: str) -> None:
        """
        Save the search keyword and full name of the entry that user activated
        by selecting one of the search results
        """
        self.active_entry = (keyword, entry)

    def check_and_reset_active_entry(self, keyword: str, entry: str) -> bool:
        """
        Whether the search query is actually a request to render
        the active entry that was saved just before
        """
        is_match = self.active_entry == (keyword, entry)
        self.active_entry = None
        return is_match

    def set_active_entry_search_restore(self, entry: str, query_arg: str) -> None:
        """
        Save the search arg that we should return to if given entry
        is being erased - allows user to back out of an active entry
        by pressing Backspace
        """
        self.active_entry_search_restore = (entry, query_arg)

    def check_and_reset_search_restore(self, query_arg: str) -> Optional[str]:
        """
        Whether to re-run a search query after backing out from an active entry
        """
        if self.active_entry_search_restore:
            (prev_active_entry, prev_query_arg) = self.active_entry_search_restore
            self.active_entry_search_restore = None
            some_chars_erased = prev_active_entry.startswith(query_arg)
            return prev_query_arg if some_chars_erased else None
        return None

    def add_recent_active_entry(self, entry: str) -> None:
        """
        Add an entry to the head of the recent active entries list.
        Make sure the entry appears in the list only once.
        """
        if entry in self.recent_active_entries:
            idx = self.recent_active_entries.index(entry)
            del self.recent_active_entries[idx]
        self.recent_active_entries = [entry] + self.recent_active_entries
        max_items = self.get_max_result_items()
        self.recent_active_entries = self.recent_active_entries[:max_items]

    def database_path_changed(self) -> None:
        """
        We are now using a different database file - do something about that.
        """
        # Shouldn't be showing recent entries from another database
        self.recent_active_entries = []

        # Active entry and old search no longer valid
        self.active_entry = None
        self.active_entry_search_restore = None


class KeywordQueryEventListener(EventListener):
    """ KeywordQueryEventListener class used to manage user input """

    # REORG: move these into Keepassxc

    def __init__(self, keepassxc_db):
        self.keepassxc_db = keepassxc_db

    def on_event(self, event, extension) -> BaseAction:
        try:
            self.keepassxc_db.initialize(
                extension.get_db_path(), extension.get_inactivity_lock_timeout(), extension.get_yubikey_slot()
            )

            if self.keepassxc_db.is_passphrase_needed():
                return render.ask_to_enter_passphrase(extension.get_db_path())
            return self.process_keyword_query(event, extension)
        except KeepassxcCliNotFoundError:
            return render.cli_not_found_error()
        except KeepassxcFileNotFoundError:
            return render.db_file_not_found_error()
        except KeepassxcCliError as exc:
            return render.keepassxc_cli_error(exc.message)

    def process_keyword_query(self, event, extension) -> BaseAction:
        """
        Handle a search query entered by user
        """
        query_keyword = event.get_keyword()
        query_arg = event.get_argument()

        if not query_arg:
            if extension.recent_active_entries:
                return render.search_results(
                    query_keyword,
                    "",
                    extension.recent_active_entries,
                    extension.get_max_result_items(),
                )
            return render.ask_to_enter_query()

        if extension.check_and_reset_active_entry(query_keyword, query_arg):
            details = self.keepassxc_db.get_entry_details(query_arg)
            return render.active_entry(details)

        prev_query_arg = extension.check_and_reset_search_restore(query_arg)
        if prev_query_arg:
            return SetUserQueryAction("{} {}".format(query_keyword, prev_query_arg))

        entries = self.keepassxc_db.search(query_arg)
        return render.search_results(
            query_keyword, query_arg, entries, extension.get_max_result_items()
        )


class ItemEnterEventListener(EventListener):
    """ KeywordQueryEventListener class used to manage user input """

    def __init__(self, keepassxc_db):
        self.keepassxc_db = keepassxc_db

    # FUTURE replace with CallObjectMethodEventListener
    def on_event(self, event, extension) -> BaseAction:
        try:
            data = event.get_data()
            action = data.get("action", None)
            if action == "read_passphrase":
                self.read_verify_passphrase()
                return DoNothingAction()
            if action == "activate_entry":
                keyword = data.get("keyword", None)
                entry = data.get("entry", None)
                extension.set_active_entry(keyword, entry)
                prev_query_arg = data.get("prev_query_arg", None)
                extension.set_active_entry_search_restore(entry, prev_query_arg)
                extension.add_recent_active_entry(entry)
                return SetUserQueryAction("{} {}".format(keyword, entry))
            if action == "show_notification":
                Notify.Notification.new(data.get("summary")).show()
        except KeepassxcCliNotFoundError:
            return render.cli_not_found_error()
        except KeepassxcFileNotFoundError:
            return render.db_file_not_found_error()
        except KeepassxcCliError as exc:
            return render.keepassxc_cli_error(exc.message)
        return DoNothingAction()

    def read_verify_passphrase(self) -> None:
        """
        Create a passphrase entry window and get the passphrase, or not
        """
        win = GtkPassphraseEntryWindow(
            verify_passphrase_fn=self.keepassxc_db.verify_and_set_passphrase,
            icon_file=os.path.join(
                current_script_path(), "images/keepassxc-search.svg"
            ),
        )

        # Activate the passphrase entry window from a separate thread
        Timer(0.5, activate_passphrase_window).start()

        win.read_passphrase()
        if not self.keepassxc_db.is_passphrase_needed():
            Notify.Notification.new("KeePassXC database unlocked.").show()


# pylint: disable=too-few-public-methods
class PreferencesUpdateEventListener(EventListener):
    """ Handle preferences updates """

    def __init__(self, keepassxc_db):
        self.keepassxc_db = keepassxc_db

    def on_event(self, event, extension) -> None:
        if event.new_value != event.old_value:
            if event.id == "database-path":
                # REORG: only call keepassxc
                # Pass "database_id" that will allow us to add multiple dbs
                # keepassxc would store databases in a dict
                self.keepassxc_db.change_path(event.new_value)
                extension.database_path_changed()
            elif event.id == "inactivity-lock-timeout":
                self.keepassxc_db.change_inactivity_lock_timeout(int(event.new_value))
