# Copyright (c) 2011 Joshua D. Bartlett
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import array
import fcntl
import os
import pty
import select
import sys
import termios
import pwd
import grp


# The following escape codes are xterm codes.
# See http://rtfm.etla.org/xterm/ctlseq.html for more.
START_ALTERNATE_MODE = set('\x1b[?{0}h'.format(i) for i in ('1049', '47', '1047'))
END_ALTERNATE_MODE = set('\x1b[?{0}l'.format(i) for i in ('1049', '47', '1047'))
ALTERNATE_MODE_FLAGS = tuple(START_ALTERNATE_MODE) + tuple(END_ALTERNATE_MODE)

import logging
log = logging.getLogger('dataplicity.m2m')


class Interceptor(object):
    '''
    This class does the actual work of the pseudo terminal. The spawn() function is the main entrypoint.
    '''

    def __init__(self, user=None, group=None, size=None):
        self.user = user
        self.group = group
        if size is None:
            size = [80, 24]
        self.size = size
        self.master_fd = None
        self.pid = None

    def spawn(self, argv=None):
        '''
        Create a spawned process.
        Based on the code for pty.spawn().
        '''
        assert self.master_fd is None

        pid, master_fd = pty.fork()
        self.master_fd = master_fd
        self.pid = pid
        if pid == pty.CHILD:
            if self.user is not None:
                try:
                    uid = pwd.getpwnam(self.user).pw_uid
                except KeyError:
                    log.error("No such user: %s", self.user)
                else:
                    os.setuid(uid)
                    log.debug('switched user for remote process to %s(%s)', self.user, uid)
            if self.group is not None:
                try:
                    gid = grp.getgrnam(self.group).gr_gid
                except KeyError:
                    log.error("No such group: %s", self.group)
                else:
                    os.setgid(gid)
                    log.debug('switched group for remote process to %s(%s)', self.group, gid)
            if not argv:
                argv = [os.environ['SHELL']]
            os.execlp(argv[0], *argv)
            # Previous command replaces the process
            return

        self._init_fd()
        try:
            self._copy()
        except (IOError, OSError):
            pass

        os.close(master_fd)
        self.master_fd = None

    def _init_fd(self):
        '''
        Called once when the pty is first set up.
        '''
        self._set_pty_size()

    def _signal_winch(self, signum, frame):
        '''
        Signal handler for SIGWINCH - window size has changed.
        '''
        self._set_pty_size()

    def _set_pty_size(self):
        '''
        Sets the window size of the child pty based on the window size of our own controlling terminal.
        '''
        assert self.master_fd is not None

        # Get the terminal size of the real terminal, set it on the pseudoterminal.
        rows, cols = self.size
        buf = array.array('h', [cols, rows, 0, 0])
        #fcntl.ioctl(pty.STDOUT_FILENO, termios.TIOCGWINSZ, buf, True)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, buf)

    def _copy(self):
        '''
        Main select loop. Passes all data to self.master_read() or self.stdin_read().
        '''
        assert self.master_fd is not None
        master_fd = self.master_fd
        while 1:
            rfds, wfds, xfds = select.select([master_fd], [], [])
            if master_fd in rfds:
                data = os.read(self.master_fd, 1024 * 1024)
                self.master_read(data)

    def resize_terminal(self, size):
        """Resize terminal to [COLUMNS, LINES]"""
        self.size = size
        self._set_pty_size()

    def write_stdout(self, data):
        '''
        Writes to stdout as if the child process had written the data.
        '''

        #os.write(pty.STDOUT_FILENO, data)

    def write_master(self, data):
        '''
        Writes to the child process from its controlling terminal.
        '''
        master_fd = self.master_fd
        assert master_fd is not None
        while data != '':
            n = os.write(master_fd, data)
            data = data[n:]

    def master_read(self, data):
        '''
        Called when there is data to be sent from the child process back to the user.
        '''

        self.write_stdout(data)

    def stdin_read(self, data):
        '''
        Called when there is data to be sent from the user/controlling terminal down to the child process.
        '''
        self.write_master(data)

if __name__ == '__main__':
    i = Interceptor()
    i.write_stdout('\nThe dream has begun.\n')
    i.spawn(sys.argv[1:])
    i.write_stdout('\nThe dream is (probably) over.\n')
