from pycchdo.log import ColoredLogger, INFO, DEBUG


log = ColoredLogger(__name__)
log.setLevel(INFO)


from models import *
