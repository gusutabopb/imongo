import re
import signal
import logging
import uuid
from subprocess import check_output

from ipykernel.kernelbase import Kernel
from pexpect import replwrap, EOF
from tornado.log import LogFormatter as ColoredFormatter

__version__ = '0.1'
version_pat = re.compile(r'version: (\d+(\.\d+)+)')

def make_logger(name, fname=None) -> logging.Logger:
    if fname is None:
        fname = name + '.log'
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    file_formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s: %(message)s')
    FORMAT = '%(color)s[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s]%(end_color)s %(message)s'
    stream_formatter = ColoredFormatter(fmt=FORMAT, datefmt='%H:%M:%S')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(stream_formatter)
    stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(filename=fname, mode='a')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger


logger = make_logger('IMongo', fname='imongo_kernel.log')


class MyREPLWrapper(replwrap.REPLWrapper):
    """
    A subclass of REPLWrapper specific for the MongoDB shell.
    run_command is the only method overridden.
    """
    def __init__(self, *args, **kwargs):
        replwrap.REPLWrapper.__init__(self, *args, **kwargs)
        logger.info('Making MyREPLWrapper')

    def filter_response(self, res):
        # output = '\n'.join([re.sub('[\w ]*\x1b\[\d*[\w ]*[\r\n]*', '', msg) for msg in res])
        res = ['\n'.join(msg.splitlines()[1:]) for msg in res]
        res = '\n\n'.join(list(filter(None, res)))
        return res

    def _isbufferempty(self):
        return self.child.buffer.strip() == ''

    def run_command(self, command, timeout=-1):
        """Send a command to the REPL, wait for and return output.

        :param str command: The command to send. Trailing newlines are not needed.
          This should be a complete block of input that will trigger execution;
          if a continuation prompt is found after sending input, :exc:`ValueError`
          will be raised.
        :param int timeout: How long to wait for the next prompt. -1 means the
          default from the :class:`pexpect.spawn` object (default 30 seconds).
          None means to wait indefinitely.
        """
        # Split up multiline commands and feed them in bit-by-bit
        cmdlines = command.splitlines()
        logger.debug('Command lines: {}'.format(cmdlines))
        # splitlines ignores trailing newlines - add it back in manually
        if command.endswith('\n'):
            cmdlines.append('')
        if not cmdlines:
            raise ValueError("No command was given")

        res = []
        self.child.sendline(cmdlines[0])
        for line in cmdlines[1:]:
            self._expect_prompt(timeout=timeout)
            res.append(self.child.before)
            self.child.sendline(line)

        # Command was fully submitted, now wait for the next prompt
        if self._expect_prompt(timeout=timeout) == 1:
            logger.debug('Erroneous continuation prompt')
            # We got the continuation prompt - command was incomplete
            self.child.kill(signal.SIGINT)
            self._expect_prompt(timeout=1)
            raise ValueError("Continuation prompt found - input was incomplete:\n"
                             + command)

        while not self._isbufferempty():
            res.append(self.child.before)
            self._expect_prompt()
            self.child.sendline('')
        res.append(self.child.before)
        logger.debug('Response: {}'.format(res))

        return self.filter_response(res)


# noinspection PyAbstractClass
class MongoKernel(Kernel):
    implementation = 'IMongo'
    implementation_version = __version__
    _banner = None
    language_info = {'name': 'javascript',
                     'codemirror_mode': 'shell',
                     'mimetype': 'text/x-mongodb',
                     'file_extension': '.js'}

    @property
    def language_version(self):
        m = version_pat.search(self.banner)
        return m.group(1)

    @property
    def banner(self):
        if self._banner is None:
            self._banner = check_output(['mongo', '--version']).decode('utf-8').strip()
        return self._banner

    def __init__(self, **kwargs):
        Kernel.__init__(self, **kwargs)
        logger.debug(self.language_info)
        logger.debug(self.language_version)
        logger.debug(self.banner)
        self._start_mongo()

    def _start_mongo(self):
        # Signal handlers are inherited by forked processes, and we can't easily
        # reset it from the subprocess. Since kernelapp ignores SIGINT except in
        # message handlers, we need to temporarily reset the SIGINT handler here
        # so that bash and its children are interruptible.
        # sig = signal.signal(signal.SIGINT, signal.SIG_DFL)

        # dir_func is an assitant Javascript function to be used bydo_complete.
        # May be a slightly hackish approach.
        # http://stackoverflow.com/questions/5523747/equivalent-of-pythons-dir-in-javascript

        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            prompt = 'mongo{}mongo'.format(uuid.uuid4())
            cont_prompt = '\.\.\. $'
            prompt_cmd = "prompt = '{}'".format(prompt)
            dir_func = """function dir(object) {
                              attributes = [];
                              for (attr in object) {attributes.push(attr);}
                              attributes.sort();
                              return attributes;}"""
            spawn_cmd = """mongo --eval "{}" --shell""".format(';'.join([prompt_cmd, dir_func]))
            self.mongowrapper = MyREPLWrapper(spawn_cmd, orig_prompt=prompt,
                                       prompt_change=None, continuation_prompt=cont_prompt)
        finally:
            signal.signal(signal.SIGINT, sig)

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False):
        if not code.strip():
            return {'status': 'ok',
                    'execution_count': self.execution_count,
                    'payload': [],
                    'user_expressions': {}}

        interrupted = False
        try:
            output = self.mongowrapper.run_command(code.rstrip())
        except KeyboardInterrupt:
            self.mongowrapper.child.sendintr()
            interrupted = True
            self.mongowrapper._expect_prompt()
            output = self.mongowrapper.child.before
        except EOF:
            output = self.mongowrapper.child.before + 'Restarting process...'
            self._start_mongo()

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        if not silent:
            stream_content = {'name': 'stdout', 'text': output}
            logger.debug('Stream content: {}'.format(stream_content))
            self.send_response(self.iopub_socket, 'stream', stream_content)


        # TODO: Error catching messages such as the one below:
        #2016-11-14T12:47:11.718+0900 E QUERY    [thread1] ReferenceError: aaa is not defined :
        #@(shell):1:1

        return_msg = {'status': 'ok', 'execution_count': self.execution_count,
                      'payload': [], 'user_expressions': {}}
        logger.debug('Return message: {}'.format(return_msg))
        return return_msg


    def do_complete(self, code, cursor_pos):
        # TODO: Implement. Currently not working.


        code = code[:cursor_pos]
        default = {'matches': [], 'cursor_start': 0,
                   'cursor_end': cursor_pos, 'metadata': dict(),
                   'status': 'ok'}

        if not code or code[-1] == ' ':
            return default

        tokens = code.replace(';', ' ').split()
        if not tokens:
            return default

        matches = []
        token = tokens[-1]
        start = cursor_pos - len(token)

        logger.debug('Tokens: {}'.format(tokens))
        logger.debug('Comp code: {}'.format(code))

        # matches = self.mongowrapper.run_command("dir(")
        # [i.strip().replace(',', '').replace('"', '') for i in s.splitlines()[2:-1]]

        # if token[0] == '$':
        #     # complete variables
        #     cmd = 'compgen -A arrayvar -A export -A variable %s' % token[1:] # strip leading $
        #     output = self.mongowrapper.run_command(cmd).rstrip()
        #     completions = set(output.split())
        #     # append matches including leading $
        #     matches.extend(['$'+c for c in completions])
        # else:
        #     # complete functions and builtins
        #     cmd = 'compgen -cdfa %s' % token
        #     output = self.mongowrapper.run_command(cmd).rstrip()
        #     matches.extend(output.split())
        #
        # if not matches:
        #     return default
        # matches = [m for m in matches if m.startswith(token)]

        return {'matches': sorted(matches), 'cursor_start': start,
                'cursor_end': cursor_pos, 'metadata': dict(),
                'status': 'ok'}
