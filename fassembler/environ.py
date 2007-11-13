import os
import socket
from fassembler.config import ConfigParser
import string
import random

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
        return socket.gethostbyaddr(socket.gethostname())

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
        ## FIXME: this should use ensure_file or something
        self.logger.info('Writing environment config file: %s' % self.config_filename)
        f = open(self.config_filename, 'wb')
        self.config.write(f)
        f.close()

    def random_string(self, length=20, chars=string.printable.strip()):
        """
        Return a random string of the given length, taken from the given characters.
        """
        return ''.join([
            random.choice(chars) for i in range(length)])
    
