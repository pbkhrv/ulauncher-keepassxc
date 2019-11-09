"""
Utility classes for working with ExtensionCustomAction and its event listener
"""
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction


__CALLABLE_OBJECTS = {}


def get_callable_object_key(method):
    """
    Save object to be called later and return its pickle-able key
    """
    key = id(method.__self__)
    __CALLABLE_OBJECTS[key] = method.__self__
    return key


def get_callable_object(key):
    """
    Look up object by they key returned by `register_callable_object`
    """
    return __CALLABLE_OBJECTS.get(key, None)


# TODO replace this with a more generic CallableAction - pass then later execute any callable object (method, function etc)
class CallMethodAction(ExtensionCustomAction):
    """
    Call specified method with specified arguments from a ItemEnterEvent listener

    Because extension actions are implemented by pickling data and sending it
    to and from the main Ulauncher process, you cannot simply tell `on_enter`
    to "call" something directly - it has to be wrapped in a ExtensionCustomAction
    and then received and processed as `data` in an ItemEnterEvent listener.
    This utility class lets you shortcut that process - simply pass the method
    that you want to call and all its parameters.
    Its companion class CallMethodEventListner (that you need to register
    in your extension), will make sure to call the method that you specified
    whenever it receives the ItemEnterEvent.

    Usage:

        >>> from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
        >>> SOME_RESULT_ITEM = ExtensionSmallResultItem(
        ...   icon="images/replace.svg",
        ...   name="Replace a's with b's!",
        ...   on_enter=CallMethodAction("asdf".replace, "a", "b"),
        ... )
    """  # noqa: E501

    def __init__(self, method, *args, **kwargs):
        obj_key = get_callable_object_key(method)
        super(CallMethodAction, self).__init__(
            (obj_key, method.__name__, args, kwargs), keep_app_open=True
        )
        self.data = (obj_key, method.__name__, args, kwargs)


# pylint: disable=too-few-public-methods
class CallMethodEventListener(EventListener):
    """
    Companion class that makes the CallMethodAction work.
    You must subscribe an instance of this class to receive ItemEnterEvent:

    `self.subscribe(ItemEnterEvent, CallMethodEventListener())`
    """

    def on_event(self, event, _):
        data = event.get_data()
        if isinstance(data, tuple) and len(data) == 4 and isinstance(data[0], int):
            obj_key, method_name, args, kwargs = data
            obj = get_callable_object(obj_key)
            if obj:
                method = getattr(obj, method_name)
                return method(*args, **kwargs)
        return None
