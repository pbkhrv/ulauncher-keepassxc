"""
Wrapper for the `wmctrl` command line utility
"""
import subprocess
from typing import Tuple


class WmctrlNotFoundError(Exception):
    """
    wmctrl is not installed
    """


def activate_window_by_id(window_id) -> None:
    """
    Execute wmctrl command "activate window by id"
    """
    _run_wmctrl("-i", "-a", window_id)


def activate_window_by_class_name(class_name) -> None:
    """
    Execute wmctrl command "activate window by class name"
    """
    _run_wmctrl("-x", "-F", "-a", class_name)


# adapted from https://github.com/autokey/autokey/blob/master/lib/autokey/scripting.py
def _run_wmctrl(*args) -> Tuple[int, str]:
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
