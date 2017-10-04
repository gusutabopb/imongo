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


css = """
a.disclosure:link         { text-decoration: none; }
a.disclosure:visited      { text-decoration: none; }
.disclosure    { color: #337AB7; font-size: 150%;}
.syntax        { color: grey; }
.string        { color: #9A334F; }
.number        { color: #5C9632; }
.boolean       { color: #AA9739; }
.key           { color: #403075; }
.keyword       { color: #AA9739; }
.object.syntax { color: #337AB7; }
.array.syntax  { color: #337AB7; }
""".replace(' ', '').replace('\n', '')

# .disclosure    ("⊕", "⊖") FIFTH
# .syntax        (",", ":", "{", "}", "[", "]") GREY
# .string        (includes quotes)      SECONDARY
# .number                               THIRD
# .boolean        FIFTH  AA9739
# .key           (object key)           PRIMARY
# .keyword       ("null", "undefined") FIFTH
# .object.syntax ("{", "}") GREY
# .array.syntax  ("[", "]") GREY
