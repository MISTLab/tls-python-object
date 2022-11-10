import logging

DEFAULT_FORMAT_STR = "%(levelname)s:%(asctime)s:%(message)s"
DEFAULT_LEVEL = logging.WARNING

logger = logging.getLogger('tlspyo')
console_handler = logging.StreamHandler()
default_formatter = logging.Formatter(DEFAULT_FORMAT_STR)
console_handler.setFormatter(default_formatter)
logger.addHandler(console_handler)
logger.setLevel(DEFAULT_LEVEL)
