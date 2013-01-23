"""Colored logger.
http://stackoverflow.com/questions/384076

"""
import logging
from logging import (
    Logger, Formatter, StreamHandler,
    DEBUG, INFO, WARN, ERROR, CRITICAL,
    )


__all__ = [
    'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL', 'ColoredLogger',
    ]


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

# The background is set with 40 plus the number of the color, and the foreground
# with 30

# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

FORMAT = (
    u"%(asctime)s %(name)-15s "
    #"$BOLD%(filename)s$RESET:%(lineno)d %(threadName)s\t"
    "$BOLD%(filename)s$RESET:%(lineno)d\t"
    "%(levelname)s$RESET "
    "%(message)s"
    )


def formatter_message(message, use_color = True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace(
            "$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message


COLORS = {
    'WARNING': YELLOW,
    'INFO': GREEN,
    'DEBUG': BLUE,
    'CRITICAL': MAGENTA,
    'ERROR': RED
}


class ColoredFormatter(Formatter):
    COLOR_FORMAT = formatter_message(FORMAT, True)

    def __init__(self, msg=None, use_color=True):
        if msg is None:
            msg = self.COLOR_FORMAT
        Formatter.__init__(self, msg)
        self.use_color = use_color

    def _short_level(self, level):
        return level[0]

    def format(self, record):
        """Modify the record."""
        levelname = record.levelname
        if self.use_color and levelname in COLORS:
            levelname_with_color = COLOR_SEQ % (30 + COLORS[levelname]) + \
                self._short_level(levelname) + RESET_SEQ
            record.levelname = levelname_with_color
        else:
            record.levelname = _short_level(levelname)
        return Formatter.format(self, record)

    def formatTime(self, record, datefmt=None):
        return super(ColoredFormatter, self).formatTime(record, datefmt)[11:]


# Custom logger class with multiple destinations
class ColoredLogger(Logger):
    def __init__(self, name):
        Logger.__init__(self, name, DEBUG)                

        color_formatter = ColoredFormatter()

        console = StreamHandler()
        console.setFormatter(color_formatter)

        self.addHandler(console)
        return
