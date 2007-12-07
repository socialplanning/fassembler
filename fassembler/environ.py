import os
import socket
from fassembler.config import ConfigParser
import string
import random
import subprocess
from datetime import datetime

class bunch(object):
    """
    A generic object that holds values in the attributes.
    """
    def __init__(self, **kw):
        for name, value in kw.items():
            setattr(self, name, value)
    def __repr__(self):
        return '<bunch %s %s>' % (
            hex(id(self)),
            ' '.join(['%s=%r' % (n, v) for n, v in sorted(self.__dict__.items())]))

class Environment(object):

    """
    The environment represents global settings of the build.  It is
    available as ``env`` in templates.

    Besides several properties and functions there is a ``.base_path``
    attribute and ``.environ`` (which is the same as ``os.environ``).
    """

    def __init__(self, base_path, logger):
        self.environ = os.environ
        self.base_path = os.path.abspath(base_path)
        self.logger = logger
        self._parser = None
        # Gets set later:
        self.maker = None

    @property
    def hostname(self):
        """
        The hostname of the current computer; just a single segment
        like ``'flow'``, not fully-qualified.

        This uses the same mechanism as the ``hostname`` command; if
        you are getting the wrong value you should do ``sudo hostname
        corrent-hostname``
        """
        return socket.gethostname().split('.')[0]

    @property
    def fq_hostname(self):
        """
        The fully-qualified hostname of this computer.

        This uses reverse DNS to determine the complete domain name.
        """
        ## this seems to return localhost.localdomain and other useless stuff:
        return socket.gethostbyaddr(socket.gethostname())[0]

    @property
    def config_filename(self):
        """
        The global configuration file.
        """
        return os.path.join(self.base_path, 'etc', 'build.ini')

    @property
    def config(self):
        """
        The config property gives a ConfigParser (-like) object that
        represents the global configuration for the build.
        """
        if self._parser is None:
            self._parser = ConfigParser()
            if os.path.exists(self.config_filename):
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
        """
        Parses an admin authentication file into an object with a
        ``.username`` and ``.password`` attribute.

        Typically used like::

            env.parse_auth(env.config.get('general', 'admin_info_filename'))
        """
        f = open(filename)
        line = f.read().strip()
        f.close()
        username, password = line.split(':', 1)
        return bunch(username=username, password=password)

    def add_built_project(self, name, time=None):
        if time is None:
            time = datetime.now()
        if self.maker.simulate:
            # Didn't really build at all
            return
        dest = self.maker.path('etc/projects.txt')
        if os.path.exists(dest):
            f = open(dest, 'r')
            lines = f.readlines()
            f.close()
        else:
            lines = []
        new_lines = []
        for line in lines:
            if not line.strip() or line.strip().startswith('#'):
                new_lines.append(line)
                continue
            if line.split()[0] != name:
                new_lines.append(line)
        new_lines.append('%s %s\n' % (name, time.strftime('%Y-%m-%d %H:%M:%S')))
        self.logger.info('Writing build info for %s to %s' % (name, dest))
        f = open(dest, 'w')
        f.writelines(new_lines)
        f.close()
        
