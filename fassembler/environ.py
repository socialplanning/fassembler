import os
import socket
from fassembler.config import ConfigParser
from fassembler.util import asbool
from initools.configparser import CanonicalFilenameSet
import string
import random
from datetime import datetime

secret_chars = string.ascii_letters + string.digits + '!@#$%^&*()[]|_-+=;:.,<>'
def random_string(length=20, chars=secret_chars):
    """
    Return a random string of the given length, taken from the given
    characters.  String starts with a letter so that passing it on the
    command line is less likely to confuse things.
    """
    return 'x' + ''.join([random.choice(chars) for i in range(length)])
    
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
        self.simulated_built_projects = []

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
        ## this seems to return localhost.localdomain and other useless stuff sometimes:
        try:
            return socket.gethostbyaddr(socket.gethostname())[0]
        except socket.error, e:
            self.logger.debug('Could not get full hostname (using "localhost" instead): %s' % e)
            return 'localhost'

    @property
    def config_filename(self):
        """
        Returns the path to build.ini, the global configuration file.
        """
        return os.path.join(self.base_path, 'etc', 'build.ini')

    @property
    def default_config_filename(self):
        """
        Returns the path to default-build.ini, which allows the specification
        of default settings which can then be overridden in etc/build.ini.
        """
        return os.path.join(self.base_path, 'requirements', 'default-build.ini')

    @property
    def config(self):
        """
        The config property gives a ConfigParser (-like) object that
        represents the global configuration for the build.
        """
        if self._parser is None:
            self._parser = ConfigParser()
            configfiles = []
            for i in self.default_config_filename, self.config_filename:
                if os.path.exists(i):
                    configfiles.append(i)
            self._parser.read(configfiles)
        return self._parser

    @property
    def localbuild(self):
        return asbool(self.config.get('general', 'localbuild'))

    def refresh_config(self):
        """
        Get rid of the configuration, so that it will be re-read later
        """
        command_line_settings = []
        if self._parser is not None:
            for section in self._parser.sections():
                for option in self._parser.options(section):
                    filename = self._parser.setting_location(section, option)[0]
                    if filename is None or filename == '<cmdline>':
                        command_line_settings.append(
                            (section, option, self._parser.get(section, option)))
        self._parser = None
        if command_line_settings:
            p = self.config
            for section, option, value in command_line_settings:
                if not p.has_section(section):
                    p.add_section(section)
                p.set(section, option, value)
        
    @property
    def base_port(self):
        return self.config.getint('general', 'base_port')

    @property
    def var(self):
        return self.config.get('general', 'var')

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
        self.config.write_sources(f, CanonicalFilenameSet([self.config_filename, None, '<cmdline>']))
        f.close()

    random_string = staticmethod(random_string)

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
        """
        Adds the named project to etc/projects.txt, so that it is listed as built
        """
        if time is None:
            time = datetime.now()
        if self.maker.simulate:
            # Didn't really build at all
            self.simulated_built_projects.append(name)
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
        
    def is_project_built(self, name):
        """
        Checks if the given project is built.  If this is a simulated run, this
        will take into account projects that were simulated/built.
        """
        if name in self.simulated_built_projects:
            return True
        dest = self.maker.path('etc/projects.txt')
        if os.path.exists(dest):
            f = open(dest, 'r')
            lines = f.readlines()
            for line in lines:
                if not line.strip() or line.strip().startswith('#'):
                    continue
                if line.split()[0] == name:
                    return True
        return False

    @property
    def db_root_password(self):
        """
        Return the root password, as best we can figure it out.

        Looks in [general] db_root_password, and also in (or a file
        location in [general] db_root_password_filename)
        ~/.mysql-root-pw (the file must have a proper permission to
        work).
        """
        if self.config.getdefault('general', 'db_root_password'):
            return self.config.get('general', 'db_root_password')
        filename = self.config.getdefault('general', 'db_root_password_filename', '~/.mysql-root-pw')
        filename = os.path.expanduser(filename)
        if os.path.exists(filename):
            self.check_restricted_permissions(filename)
            f = open(filename, 'rb')
            c = f.read().strip()
            f.close()
            return c
        else:
            self.logger.debug('No root password file %s (using empty password)' % filename)
        return ''

    def check_restricted_permissions(self, filename):
        """
        Checks that a file is not readable or writable by anyone other than you
        """
        mode = os.stat(filename).st_mode
        # Group or other, readable, writable, executable:
        bad_modes = 077
        if mode & bad_modes:
            raise OSError(
                "The file %s must not be readable by other users; use \"chmod 600 %s\" to fix"
                % (filename, filename))
