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
        self.args = args
        self.kwargs = kwargs

    def _filter_response(self, res):
        msg = re.sub('\[\d+[A-Z]', '', res)
        msg = re.sub('\[J', '', msg)
        msg = [l.strip() for l in msg.split('\x1b') if l]

        output = []
        for l in msg[::-1]:
            if not output:
                output.append(l)
                continue
            if l not in output[-1]:
                output.append(l)
        return output[0]

    def _isbufferempty(self):
        condition1 = self.child.buffer.strip() == '\x1b[47G\x1b[J\x1b[47G'
        condition2 = self.child.buffer.strip() == ''
        return condition1 or condition2

    def _send_line(self, cmd):
        try:
            self.child.sendline(cmd)
            logger.debug('Command sent. Waiting for prompt')
        except Exception as e:
            exeception_msg = 'Unexpected exeception occurred.'
            logger.error('{}: {}: {}'.format(exeception_msg, e.__class__.__name__, e.args))
            raise RuntimeError(exeception_msg)

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
        # Clean input command by removing indentation
        # There seems to be a limitation with pexepect/mongo when entering
        # lines longer than 1000 characters. If that is the case, a ValueError
        # exception is raised.
        cmd = re.sub('\s{2,}', ' ', ' '.join([l for l in command.splitlines() if l]))
        logger.debug('Command length: {} chars'.format(len(cmd)))
        logger.debug('Command: {}'.format(cmd))
        if len(cmd) > 1000:
            error = ('Code too long. Please commands with less than 1000 effective chracters.\n'
                       'Indentation spaces/tabs don\'t count towards "effective" characters.')
            logger.error(error)
            raise ValueError(error.replace('\n', ' '))

        self._send_line(cmd)

        match = self._expect_prompt(timeout=timeout)
        logger.debug('Prompt type: {}'.format(match))

        logger.debug('Iterating over message')
        response = []
        while not self._isbufferempty():
            response.append(self.child.before)
            logger.debug('Buffer not empty, sending blank line')
            match = self._expect_prompt(timeout=timeout)
            if match == 1:
                # If continuation prompt is detected, restart child (by raising ValueError)
                error = ('Code incomplete. Please enter valid and complete code.\n'
                           'Continuation prompt functionality not implemented yet.')
                logger.error(error.replace('\n', ' '))
                raise ValueError(error)
            self._send_line('')
        response.append(self.child.before)
        response = self._filter_response(''.join(response))

        logger.debug('Response: {}'.format(response))

        return response


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
        error = None
        try:
            output = self.mongowrapper.run_command(code.rstrip())
        except KeyboardInterrupt:
            self.mongowrapper.child.sendeof()
            interrupted = True
            output = None
            error = 'KeyboardInterrupt.'
            self._start_mongo()
        except (EOF, ValueError, RuntimeError) as e:
            output = None
            error = e.args[0]
            self._start_mongo()
        finally:
            if error:
                error_msg = {'name': 'stderr', 'text': error + '\nRestarting mongo shell...'}
                self.send_response(self.iopub_socket, 'stream', error_msg)

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        if not silent and not error:
            result = {'data': { "text/plain": output},
                      'execution_count': self.execution_count}
            self.send_response(self.iopub_socket, 'execute_result', result)

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
