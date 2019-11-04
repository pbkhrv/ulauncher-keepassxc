from ulauncher.api.shared.event import ItemEnterEvent
from keepassxc.custom_action_utils import CallMethodAction, CallMethodEventListener


class Recorder:
    """
    Record last method call and args
    """

    def __init__(self):
        self.was_called = False
        self.arg = None
        self.kwarg = None

    def foo(self, arg, kwarg=None):
        """
        Record this method
        """
        self.was_called = True
        self.arg = arg
        self.kwarg = kwarg


def test_call_method():
    obj = Recorder()
    assert not obj.was_called

    action = CallMethodAction(obj.foo, "arg", kwarg="kwarg")
    event_listener = CallMethodEventListener()
    event_listener.on_event(ItemEnterEvent(action._data), None)

    assert obj.was_called
    assert obj.arg == "arg"
    assert obj.kwarg == "kwarg"
