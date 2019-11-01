"""
Wrapper for the `wmctrl` command line utility
"""
import subprocess
import re
from typing import NamedTuple


class WmctrlNotFoundError(Exception):
    """
    wmctrl is not installed
    """


class WindowInfo(NamedTuple):
    """
    Information about windows that wmctrl returns
    """

    id: str
    desktop_id: int
    pid: int
    class_name: str
    host: str
    title: str


def get_windows():
    """
    Request window info from wmctrl and parse results into list of WindowInfo objects
    """
    _, output = _run_wmctrl("-p", "-x", "-l")
    windows = []
    for line in output.splitlines():
        line = re.sub(r" +", " ", line)
        windows.append(WindowInfo(*line.split(" ", maxsplit=5)))
    return windows


def activate_window_by_id(window_id):
    """
    Execute wmctrl command "activate window by id"
    """
    _run_wmctrl("-i", "-a", window_id)


def activate_window_by_class_name(class_name):
    """
    Execute wmctrl command "activate window by class name"
    """
    _run_wmctrl("-x", "-F", "-a", class_name)


# adapted from https://github.com/autokey/autokey/blob/master/lib/autokey/scripting.py
def _run_wmctrl(*args):
    """
    Execute wmctrl with given args and handle errors
    """
    try:
        with subprocess.Popen(["wmctrl"] + list(args), stdout=subprocess.PIPE) as proc:
            output = proc.communicate()[0].decode()[:-1]  # Drop trailing newline
            returncode = proc.returncode
    except FileNotFoundError:
        raise WmctrlNotFoundError()

    return returncode, output
