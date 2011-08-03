""" Actions to take when certain things happen in the model """


saved_obj_actions = []
removed_obj_actions = []
saved_note_actions = []
removed_note_actions = []


def saved_obj(obj):
    for action in saved_obj_actions:
        action(obj)


def removed_obj(obj):
    for action in removed_obj_actions:
        action(obj)


def saved_note(note):
    for action in saved_note_actions:
        action(obj)


def removed_note(note):
    for action in removed_note_actions:
        action(obj)
