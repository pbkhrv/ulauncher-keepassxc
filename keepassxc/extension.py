"""
Search KeePassXC password databases and copy passwords to the clipboard.
"""
import logging
import os
import sys
from threading import Timer
import gi
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import (
    KeywordQueryEvent,
    ItemEnterEvent,
    PreferencesUpdateEvent,
)
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.ActionList import ActionList
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from .keepassxc_db import (
    KeepassxcDatabase,
    KeepassxcCliNotFoundError,
    KeepassxcFileNotFoundError,
    KeepassxcCliError,
)
from .gtk_passphrase_entry import GtkPassphraseEntryWindow
from .wmctrl import activate_window_by_class_name, WmctrlNotFoundError

gi.require_version("Notify", "0.7")
# pylint: disable=wrong-import-order
from gi.repository import Notify  # noqa: E402


logger = logging.getLogger(__name__)

SEARCH_ICON = "images/keepassxc-search.svg"
UNLOCK_ICON = "images/keepassxc-search-locked.svg"
EMPTY_ICON = "images/empty.png"
ERROR_ICON = "images/error.svg"
ITEM_ICON = "images/key.svg"
COPY_ICON = "images/copy.svg"
NOT_FOUND_ICON = "images/not_found.svg"

KEEPASSXC_CLI_NOT_FOUND_ITEM = ExtensionResultItem(
    icon=ERROR_ICON,
    name="Cannot find or execute keepassxc-cli",
    description="Please make sure that keepassxc-cli is installed and accessible",
    on_enter=DoNothingAction(),
)

KEEPASSXC_DB_NOT_FOUND_ITEM = ExtensionResultItem(
    icon=ERROR_ICON,
    name="Cannot find the database file",
    description="Please verify the database file path in extension preferences",
    on_enter=DoNothingAction(),
)

NEED_PASSPHRASE_ITEM = ExtensionResultItem(
    icon=UNLOCK_ICON,
    name="Unlock KeePassXC database",
    description="Enter passphrase to unlock the KeePassXC database",
    on_enter=ExtensionCustomAction({"action": "read_passphrase"}),
)

ENTER_QUERY_ITEM = ExtensionResultItem(
    icon=SEARCH_ICON,
    name="Enter search query...",
    description="Please enter your search query",
    on_enter=DoNothingAction(),
)

NO_SEARCH_RESULTS_ITEM = ExtensionResultItem(
    icon=NOT_FOUND_ICON,
    name="No matching entries found...",
    description="Please check spelling or make the query less specific",
    on_enter=DoNothingAction(),
)


def more_results_available_item(cnt):
    """
    Item showing how many more results are available
    """
    return ExtensionSmallResultItem(
        icon=EMPTY_ICON,
        name="...{} more results available, please refine the search query...".format(
            cnt
        ),
        on_enter=DoNothingAction(),
    )


def keepassxc_cli_error_item(message):
    """
    Error message from attempting to call keepassxc CLI
    """
    return ExtensionResultItem(
        icon=ERROR_ICON,
        name="Error while calling keepassxc CLI",
        description=message,
        on_enter=DoNothingAction(),
    )


def activate_passphrase_window():
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


def current_script_path():
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

    def get_db_path(self):
        """
        Normalized and expanded path to the database file
        """
        return os.path.expanduser(self.preferences["database-path"])

    def get_max_result_items(self):
        """
        Maximum number of search results to show on screen
        """
        return int(self.preferences["max-results"])

    def get_inactivity_lock_timeout(self):
        """
        How long to wait to lock the database after last user interaction
        """
        return int(self.preferences["inactivity-lock-timeout"])

    def set_active_entry(self, keyword, entry):
        """
        Save the search keyword and full name of the entry that user activated
        by selecting one of the search results
        """
        self.active_entry = (keyword, entry)

    def check_and_reset_active_entry(self, keyword, entry):
        """
        Whether the search query is actually a request to render
        the active entry that was saved just before
        """
        entry = self.active_entry == (keyword, entry)
        self.active_entry = None
        return entry

    def set_active_entry_search_restore(self, entry, query_arg):
        """
        Save the search arg that we should return to if given entry
        is being erased - allows user to back out of an active entry
        by pressing Backspace
        """
        self.active_entry_search_restore = (entry, query_arg)

    def check_and_reset_search_restore(self, query_arg):
        """
        Whether to re-run a search query after backing out from an active entry
        """
        if self.active_entry_search_restore:
            (prev_active_entry, prev_query_arg) = self.active_entry_search_restore
            self.active_entry_search_restore = None
            some_chars_erased = prev_active_entry.startswith(query_arg)
            return prev_query_arg if some_chars_erased else None
        return None

    def add_recent_active_entry(self, entry):
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

    def database_path_changed(self):
        """
        We are now using a different database file - do something about that.
        """
        # Shouldn't be showing recent entries from another database
        self.recent_active_entries = []

        # Active entry and old search no longer valid
        self.active_entry = None
        self.active_entry_search_restore = None


# REORG: move into "render.py"
def render_search_results(keyword, arg, entries, max_items):
    """
    Build list of result items `max_items` long
    """
    items = []
    if not entries:
        items.append(NO_SEARCH_RESULTS_ITEM)
    else:
        for entry in entries[:max_items]:
            action = ExtensionCustomAction(
                {
                    "action": "activate_entry",
                    "entry": entry,
                    "keyword": keyword,
                    "prev_query_arg": arg,
                },
                keep_app_open=True,
            )
            items.append(
                ExtensionSmallResultItem(icon=ITEM_ICON, name=entry, on_enter=action)
            )
        if len(entries) > max_items:
            items.append(more_results_available_item(len(entries) - max_items))
    return RenderResultListAction(items)


class KeywordQueryEventListener(EventListener):
    """ KeywordQueryEventListener class used to manage user input """

    # REORG: move these into Keepassxc

    def __init__(self, keepassxc_db):
        self.keepassxc_db = keepassxc_db

    def on_event(self, event, extension):
        try:
            self.keepassxc_db.initialize(
                extension.get_db_path(), extension.get_inactivity_lock_timeout()
            )

            if self.keepassxc_db.is_passphrase_needed():
                return RenderResultListAction([NEED_PASSPHRASE_ITEM])
            return self.process_keyword_query(event, extension)
        except KeepassxcCliNotFoundError:
            return RenderResultListAction([KEEPASSXC_CLI_NOT_FOUND_ITEM])
        except KeepassxcFileNotFoundError:
            return RenderResultListAction([KEEPASSXC_DB_NOT_FOUND_ITEM])
        except KeepassxcCliError as exc:
            return RenderResultListAction([keepassxc_cli_error_item(exc.message)])

    def process_keyword_query(self, event, extension):
        """
        Handle a search query entered by user
        """
        query_keyword = event.get_keyword()
        query_arg = event.get_argument()

        if not query_arg:
            if extension.recent_active_entries:
                return render_search_results(
                    query_keyword,
                    "",
                    extension.recent_active_entries,
                    extension.get_max_result_items(),
                )
            return RenderResultListAction([ENTER_QUERY_ITEM])

        if extension.check_and_reset_active_entry(query_keyword, query_arg):
            return self.show_active_entry(query_arg)

        prev_query_arg = extension.check_and_reset_search_restore(query_arg)
        if prev_query_arg:
            return SetUserQueryAction("{} {}".format(query_keyword, prev_query_arg))

        entries = self.keepassxc_db.search(query_arg)
        return render_search_results(
            query_keyword, query_arg, entries, extension.get_max_result_items()
        )

    def show_active_entry(self, entry):
        """
        Retrieve entry details from database and render them
        """
        # REORG: break this up into
        # - "get_entry_details" + erorr handling
        # - render active entry
        items = []
        details = self.keepassxc_db.get_entry_details(entry)
        attrs = [
            ("Password", "password"),
            ("UserName", "username"),
            ("URL", "URL"),
            ("Notes", "notes"),
        ]
        for attr, attr_nice in attrs:
            val = details.get(attr, "")
            if val:
                action = ActionList(
                    [
                        ExtensionCustomAction(
                            {
                                "action": "show_notification",
                                "summary": "{} copied to the clipboard.".format(
                                    attr_nice.capitalize()
                                ),
                            }
                        ),
                        CopyToClipboardAction(val),
                    ]
                )

                if attr == "Password":
                    items.append(
                        ExtensionSmallResultItem(
                            icon=COPY_ICON,
                            name="Copy password to the clipboard",
                            on_enter=action,
                        )
                    )
                else:
                    items.append(
                        ExtensionResultItem(
                            icon=COPY_ICON,
                            name="{}: {}".format(attr_nice.capitalize(), val),
                            description="Copy {} to the clipboard".format(attr_nice),
                            on_enter=action,
                        )
                    )
        return RenderResultListAction(items)


class ItemEnterEventListener(EventListener):
    """ KeywordQueryEventListener class used to manage user input """

    # REORG: use "method_caller" to move this logic into Keepassxc class

    def __init__(self, keepassxc_db):
        self.keepassxc_db = keepassxc_db

    def on_event(self, event, extension):
        try:
            data = event.get_data()
            action = data.get("action", None)
            if action == "read_passphrase":
                return self.read_verify_passphrase()
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
            return RenderResultListAction([KEEPASSXC_CLI_NOT_FOUND_ITEM])
        except KeepassxcFileNotFoundError:
            return RenderResultListAction([KEEPASSXC_DB_NOT_FOUND_ITEM])
        except KeepassxcCliError as exc:
            return RenderResultListAction([keepassxc_cli_error_item(exc.message)])
        return DoNothingAction()

    def read_verify_passphrase(self):
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

    def on_event(self, event, extension):
        if event.new_value != event.old_value:
            if event.id == "database-path":
                # REORG: only call keepassxc
                # Pass "database_id" that will allow us to add multiple dbs
                # keepassxc would store databases in a dict
                self.keepassxc_db.change_path(event.new_value)
                extension.database_path_changed()
            elif event.id == "inactivity-lock-timeout":
                self.keepassxc_db.change_inactivity_lock_timeout(int(event.new_value))
