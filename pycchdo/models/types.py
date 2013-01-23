"""Types for database storage.

"""
from sqlalchemy.types import (
    TypeEngine, Integer, Boolean, Enum, String, Unicode, DateTime, DECIMAL,
    )


class ID(Integer):
    pass


class IDList(TypeEngine):
    pass


class TextList(TypeEngine):
    pass


class DecimalList(TypeEngine):
    pass


class File(TypeEngine):
    pass


class ParticipantsType(TypeEngine):
    pass


class ParameterInformations(TypeEngine):
    pass

