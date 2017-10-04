import logging
from functools import wraps
from tornado.log import LogFormatter as ColoredFormatter

logger = logging.getLogger('IMongo')

def make_logger(name, fname=None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    file_formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s: %(message)s')
    FORMAT = '%(color)s[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s]%(end_color)s %(message)s'
    stream_formatter = ColoredFormatter(fmt=FORMAT, datefmt='%H:%M:%S')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(stream_formatter)
    stream_handler.setLevel(logging.INFO)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(filename=fname, mode='a')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger


def exception_logger(func):
    @wraps(func)
    def catcher(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            params = func.__module__, func.__name__, e.__class__.__name__, e.args
            logger.debug('{}.{} failed | {}: {}'.format(*params))
            return None

    return catcher
