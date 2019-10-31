"""
Wrapper for the `wmctrl` command line utility
"""
import subprocess
from collections import defaultdict
import re
from typing import NamedTuple


class WmctrlNotFoundError(Exception):
    """
    wmctrl is not installed
    """
    pass


class WindowInfo(NamedTuple):
    id: str
    desktop_id: int
    pid: int
    class_name: str
    host: str
    title: str


def get_windows():
    _, output = _run_wmctrl("-p", "-x", "-l")
    ws = []
    for l in output.splitlines():
        l = re.sub(r" +", " ", l)
        ws.append(WindowInfo(*l.split(" ", maxsplit=5)))
    return ws


def activate_window_by_id(window_id):
    _run_wmctrl("-i", "-a", window_id)


def activate_window_by_class_name(class_name):
    _run_wmctrl("-x", "-F", "-a", class_name)


# adapted from https://github.com/autokey/autokey/blob/master/lib/autokey/scripting.py
def _run_wmctrl(*args):
    try:
        with subprocess.Popen(["wmctrl"] + list(args), stdout=subprocess.PIPE) as p:
            output = p.communicate()[0].decode()[:-1]  # Drop trailing newline
            returncode = p.returncode
    except FileNotFoundError:
        raise WmctrlNotFoundError()

    return returncode, output
