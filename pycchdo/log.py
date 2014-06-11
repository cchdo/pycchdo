"""Colored logger.
http://stackoverflow.com/questions/384076

"""
from logging import (
    getLogger, Formatter, StreamHandler,
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
COLOR_SEQ = "\033[1;{0}m"
BOLD_SEQ = "\033[1m"

FORMAT = (
    u"%(asctime)s $BOLD%(name)-15s$RESET:%(lineno)d %(threadName)s\t"
    "%(levelname)s$RESET "
    "%(message)s"
    )


def formatter_message(message, use_color=True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace(
            "$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message


class ColoredFormatter(Formatter):
    COLOR_FORMAT = formatter_message(FORMAT, True)

    COLORS = {
        'WARNING': YELLOW,
        'INFO': GREEN,
        'DEBUG': BLUE,
        'CRITICAL': MAGENTA,
        'ERROR': RED
    }

    def __init__(self, fmt=None, date_fmt=None, use_color=True):
        if fmt is None:
            fmt = self.COLOR_FORMAT
        super(ColoredFormatter, self).__init__(fmt)
        self.use_color = use_color

    def _short_level(self, level):
        return level[0]

    def format(self, record):
        """Modify the record."""
        levelname = record.levelname
        if self.use_color and levelname in self.COLORS:
            levelname_with_color = u'{0}{1}{2}'.format(
                COLOR_SEQ.format(30 + self.COLORS[levelname]),
                self._short_level(levelname), RESET_SEQ)
            record.levelname = levelname_with_color
        else:
            record.levelname = self._short_level(levelname)
        return super(ColoredFormatter, self).format(record)

    def formatTime(self, record, datefmt=None):
        return super(ColoredFormatter, self).formatTime(record, datefmt)[11:]


color_formatter = ColoredFormatter()
color_console = StreamHandler()
color_console.setFormatter(color_formatter)


def ColoredLogger(name):
    """Add the color console handler to every logger acquired in pycchdo."""
    logger = getLogger(name)
    logger.addHandler(color_console)
    return logger
