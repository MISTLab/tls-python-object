import logging

DEFAULT_FORMAT_STR = "%(levelname)s:%(asctime)s:%(message)s"
DEFAULT_LEVEL = logging.getLogger().getEffectiveLevel()

logger = logging.getLogger('tlspyo')
if not logger.handlers:
    console_handler = logging.StreamHandler()
    default_formatter = logging.Formatter(DEFAULT_FORMAT_STR)
    console_handler.setFormatter(default_formatter)
    logger.addHandler(console_handler)
if logger.level == logging.NOTSET:
    logger.setLevel(DEFAULT_LEVEL)
logger.propagate = False
