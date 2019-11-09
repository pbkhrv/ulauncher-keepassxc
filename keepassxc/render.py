"""
Functions that deal with rendering Ulauncher result items
"""

from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.ActionList import ActionList

# from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction

NO_SEARCH_RESULTS_ITEM = ExtensionResultItem(
    icon="images/not_found.svg",
    name="No matching entries found...",
    description="Please check spelling or make the query less specific",
    on_enter=DoNothingAction(),
)


def item_more_results_available(cnt):
    """
    Item showing how many more results are available
    """
    return ExtensionSmallResultItem(
        icon="images/empty.png",
        name="...{} more results available, please refine the search query...".format(
            cnt
        ),
        on_enter=DoNothingAction(),
    )


def cli_not_found_error():
    """
    Was not able to execute keepassxc-cli because it was either
    not found or wrong permissions
    """
    return RenderResultListAction(
        [
            ExtensionResultItem(
                icon="images/error.svg",
                name="Cannot execute keepassxc-cli",
                # pylint: disable=line-too-long
                description="Please make sure keepassxc-cli is installed and accessible",  # noqa: E501
                on_enter=DoNothingAction(),
            )
        ]
    )


def db_file_not_found_error():
    """
    Database file specified in preferences could not be found
    """
    return RenderResultListAction(
        [
            ExtensionResultItem(
                icon="images/error.svg",
                name="Cannot find the database file",
                description="Please verify database file path in extension preferences",
                on_enter=DoNothingAction(),
            )
        ]
    )


def keepassxc_cli_error(message):
    """
    Error message received while attempting to execute keepassxc-cli
    """
    return RenderResultListAction(
        [
            ExtensionResultItem(
                icon="images/error.svg",
                name="Error while calling keepassxc CLI",
                description=message,
                on_enter=DoNothingAction(),
            )
        ]
    )


def ask_to_enter_passphrase():
    """
    Ask user to enter the passphrase to unlock database
    """
    return RenderResultListAction(
        [
            ExtensionResultItem(
                icon="images/keepassxc-search-locked.svg",
                name="Unlock KeePassXC database",
                description="Enter passphrase to unlock the KeePassXC database",
                # FUTURE replace with call_object_method
                on_enter=ExtensionCustomAction({"action": "read_passphrase"}),
            )
        ]
    )


def ask_to_enter_query():
    """
    Ask user to start entering the search query
    """
    return RenderResultListAction(
        [
            ExtensionResultItem(
                icon="images/keepassxc-search.svg",
                name="Enter search query...",
                description="Please enter your search query",
                on_enter=DoNothingAction(),
            )
        ]
    )


def search_results(keyword, arg, entries, max_items):
    """
    Build list of result items `max_items` long
    """
    items = []
    if not entries:
        items.append(NO_SEARCH_RESULTS_ITEM)
    else:
        for entry in entries[:max_items]:
            # FUTURE replace with call_object_method
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
                ExtensionSmallResultItem(
                    icon="images/key.svg", name=entry, on_enter=action
                )
            )
        if len(entries) > max_items:
            items.append(item_more_results_available(len(entries) - max_items))
    return RenderResultListAction(items)


def active_entry(details):
    """
    Show details of an entry and allow various items to be copied to the clipboard
    """
    attrs = [
        ("Password", "password"),
        ("UserName", "username"),
        ("URL", "URL"),
        ("Notes", "notes"),
    ]
    items = []
    for attr, attr_nice in attrs:
        val = details.get(attr, "")
        if val:
            action = ActionList(
                [
                    # FUTURE replace with call_object_method
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
                        icon="images/copy.svg",
                        name="Copy password to the clipboard",
                        on_enter=action,
                    )
                )
            else:
                items.append(
                    ExtensionResultItem(
                        icon="images/copy.svg",
                        name="{}: {}".format(attr_nice.capitalize(), val),
                        description="Copy {} to the clipboard".format(attr_nice),
                        on_enter=action,
                    )
                )
    return RenderResultListAction(items)
