import json
import os
import re
import signal
import uuid
from subprocess import check_output

import yaml
from ipykernel.kernelbase import Kernel
from pexpect import replwrap, EOF

from . import utils

__version__ = '0.1'
version_pat = re.compile(r'version\D*(\d+(\.\d+)+)')

log_file = os.path.join(os.path.split(__file__)[0], 'imongo_kernel.log')
logger = utils.make_logger('IMongo', fname=log_file)
logger.info(f'Logging to {log_file}')


class MongoShellWrapper(replwrap.REPLWrapper):
    """
    A subclass of REPLWrapper specific for the MongoDB shell.
    run_command is the only method overridden.
    """

    def __init__(self, *args, **kwargs):
        replwrap.REPLWrapper.__init__(self, *args, **kwargs)
        logger.info('Making MyREPLWrapper')
        self.args = args
        self.kwargs = kwargs

    @staticmethod
    def _filter_response(res):
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
            exception_msg = 'Unexpected exception occurred.'
            logger.error('{}: {}: {}'.format(exception_msg, e.__class__.__name__, e.args))
            raise RuntimeError(exception_msg)

    def _expect_prompt(self, timeout=5):
        return self.child.expect([self.prompt, self.continuation_prompt],
                                 timeout=timeout)

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
        # Clean input command by removing indentation and comment lines
        # There seems to be a limitation with pexepect/mongo when entering
        # lines longer than 1000 characters. If that is the case, a ValueError
        # exception is raised.
        cmd_lines = [l for l in command.splitlines() if l and not l.startswith('//')]
        cmd = re.sub('\s{2,}', ' ', ' '.join(cmd_lines))
        logger.debug('Command length: {} chars'.format(len(cmd)))
        logger.debug('Command: {}'.format(cmd))
        if len(cmd) > 1024:
            # TODO: Enable sending lines long lines (>1024 on macOS >4096 on Linux).
            # This is related to a buffering issue and seems that can only be solved
            # by splitting lines, and waiting for the continuation prompt.
            # However this MAY interfere with how responses are currently received
            # Ref: http://pexpect.readthedocs.io/en/stable/_modules/pexpect/pty_spawn.html#spawn.send
            error = ('Code too long. Please commands with less than 1024 effective chracters.\n'
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
        """Spawns `mongo` subprocess"""

        prompt = 'mongo{}mongo'.format(uuid.uuid4())
        cont_prompt = '\.\.\. $'
        prompt_cmd = "prompt = '{}'".format(prompt)

        # dir_func is an assistant Javascript function to be used by do_complete.
        # May be a slightly hackish approach.
        # http://stackoverflow.com/questions/5523747/equivalent-of-pythons-dir-in-javascript
        dir_func = """function dir(object) {
                          attributes = [];
                          for (attr in object) {attributes.push(attr);}
                          attributes.sort();
                          return attributes;}"""
        try:
            spawn_cmd = ['mongo', f'--eval "{prompt_cmd}; {dir_func}"']
            spawn_cmd += self._parse_spawn_options() + ['--shell']
            self.mongowrapper = MongoShellWrapper(' '.join(spawn_cmd), orig_prompt=prompt,
                                                  prompt_change=None, continuation_prompt=cont_prompt)
        finally:
            # Signal handlers are inherited by forked processes, and we can't easily
            # reset it from the subprocess. Since kernelapp ignores SIGINT except in
            # message handlers, we need to temporarily reset the SIGINT handler here
            # so that bash and its children are interruptible.
            sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.signal(signal.SIGINT, sig)

    @staticmethod
    def _parse_spawn_options():
        """
        Parses spawn YAML command options from the default Jupyter configuration directory.
        http://jupyter.readthedocs.io/en/latest/projects/jupyter-directories.html#configuration-files
        """
        config_dir = os.environ.get('JUPYTER_CONFIG_DIR')
        if config_dir is None:
            config_dir = '.jupyter'
        config_path = os.path.join(os.path.expanduser('~'), config_dir, 'imongo_config.yml')
        logger.info(f'Trying to load {config_path}')
        try:
            config = yaml.load(open(config_path))
        except FileNotFoundError:
            logger.info('Using default configuration')
            return list()

        options = []
        for key, value in config.items():
            if key == 'shell':
                continue
            elif not value:
                options.append(f'--{key}')
            else:
                options.append(f'--{key} {value}')
        return options

    @staticmethod
    @utils.exception_logger
    def _pretty_output(json_data, show_levels=2):
        json_str = json.dumps(json_data)
        if json_data:
            logger.debug('Valid JSON')
        else:
            logger.debug('Empty JSON')
            return

        obj_uuid = str(uuid.uuid4())
        html_str = '<style>{}></style><div id="{}"></div>'
        css_path = os.path.join(os.path.split(__file__)[0], 'style.css')
        with open(css_path) as f:
            css = f.read().replace(' ', '').replace('\n', '')
            html_str = html_str.format(css, obj_uuid)
        js_str = 'require(["https://rawgit.com/caldwell/renderjson/master/renderjson.js"],' \
                 ' function() {document.getElementById(\'%s\').appendChild(' \
                 'renderjson.set_show_to_level(%d)(%s))});'
        js_str = js_str % (obj_uuid, show_levels, json_str)

        return html_str, js_str

    @staticmethod
    def _parse_shell_output(shell_output):
        json_loader = utils.exception_logger(json.loads)

        # TODO: Parse booleans, Binaries, etc
        try:
            return json.loads(shell_output)
        except json.JSONDecodeError:
            output = []
            for doc in [line for line in shell_output.splitlines() if line]:
                doc = re.sub('ISODate\(\"(.*?)\"\)', '{"$date": "\\1"}', doc)
                doc = re.sub('ObjectId\(\"(.*?)\"\)', '{"$oid": "\\1"}', doc)
                doc = re.sub('NumberLong\(\"(.*?)\"\)', '{"$numberLong": "\\1"}', doc)
                doc = json_loader(doc)
                if doc:
                    output.append(doc)
            return output

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

        if not silent and output:
            json_data = self._parse_shell_output(output)
            poutput = self._pretty_output(json_data)
            html_str, js_str = poutput if poutput else (None, None)
            html_msg = {'data': {'text/html': html_str}}
            js_msg = {'data': {'application/javascript': js_str}}
            self.send_response(self.iopub_socket, 'display_data', html_msg)
            self.send_response(self.iopub_socket, 'display_data', js_msg)

            result = {'data': {'text/plain': output},
                      'execution_count': self.execution_count}
            logger.debug(result)
            self.send_response(self.iopub_socket, 'execute_result', result)

        # TODO: Error catching messages such as the one below:
        # 2016-11-14T12:47:11.718+0900 E QUERY    [thread1] ReferenceError: aaa is not defined : @(shell):1:1
        # 2017-01-25T13:15:50.804+0900 E QUERY    [thread1] SyntaxError: expected expression, got '}' @(shell):1:12
        # 2017-02-13T22:09:16.483+0900 E QUERY    [main] TypeError: db.find is not a function :
        # @(shell):1:16
        # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Error

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
