import os
import socket
from fassembler.config import ConfigParser
import string
import random

class bunch(object):
    def __init__(self, **kw):
        for name, value in kw.items():
            setattr(self, name, value)
    def __repr__(self):
        return '<bunch %s %s>' % (
            hex(id(self)),
            ' '.join(['%s=%r' % (n, v) for n, v in sorted(self.__dict__.items())]))

class Environment(object):

    def __init__(self, base_path, logger):
        self.environ = os.environ
        self.base_path = os.path.abspath(base_path)
        self.logger = logger
        self._parser = None

    @property
    def hostname(self):
        return socket.gethostname().split('.')[0]

    @property
    def fq_hostname(self):
        ## FIXME: this seems to return localhost.localdomain and other useless stuff
        return socket.gethostbyaddr(socket.gethostname())[0]

    @property
    def config_filename(self):
        return os.path.join(self.base_path, 'etc', 'build.ini')

    @property
    def config(self):
        if self._parser is None:
            self._parser = ConfigParser()
            self._parser.read(self.config_filename)
        return self._parser

    def save(self):
        """
        Save the configuration in etc/build.ini
        """
        if self._parser is None:
            # Nothing was changed
            self.logger.info('No config file changes made')
            return
        ## FIXME: this should use ensure_file or something
        ## FIXME: somehow this is clearing the config file when no changes are made
        ## (the self._parser is None check avoids this, but only incidentally)
        self.logger.info('Writing environment config file: %s' % self.config_filename)
        f = open(self.config_filename, 'wb')
        self.config.write(f)
        f.close()

    secret_chars = string.ascii_letters + string.digits + '!@#$%^&*()[]|_-+=;:.,<>'

    def random_string(self, length=20, chars=secret_chars):
        """
        Return a random string of the given length, taken from the given characters.

        You can also give chars like chars='alphanumeric', which will
        use string.alphanumeric.
        """
        if hasattr(string, chars):
            chars = getattr(string, chars).strip()
        return ''.join([
            random.choice(chars) for i in range(length)])
    
    def parse_auth(self, filename):
        f = open(filename)
        line = f.read().strip()
        f.close()
        username, password = line.split(':', 1)
        return bunch(username=username, password=password)
