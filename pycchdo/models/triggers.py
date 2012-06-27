"""Actions to take when certain things happen in the model."""


saved_obj_actions = []
deleted_obj_actions = []
saved_note_actions = []
deleted_note_actions = []


def _call(actions, *args, **kwargs):
    """ Calls each action with the passed in args and kwargs.

        Action specification:
            - function object: the action to call
            - 2-ple: the action to call and the object to pass as self

    """
    for action in actions:
        if type(action) is tuple and len(action) == 2:
            fn, self = action
            fn(self, *args, **kwargs)
        else:
            action(*args, **kwargs)


def saved_obj(obj):
    _call(saved_obj_actions, obj)


def deleted_obj(obj):
    _call(deleted_obj_actions, obj)


def saved_note(note):
    _call(saved_note_actions, note)


def deleted_note(note):
    _call(deleted_note_actions, note)
