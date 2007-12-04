"""
The configuration file loader (based on INITools)
"""

from initools import configparser
import re
import urllib

_url_re = re.compile(r'^https?://')

class ConfigParser(configparser.RawConfigParser):
    global_section = True
    inherit_defaults = False
    extendable = True
    default_extend_section_name = '__name__'
    ignore_missing_files = False

    def getdefault(self, section, option, default=None):
        try:
            return self.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError), e:
            return default

    def _open(self, filename, mode='r'):
        if mode == 'r' and _url_re.search(filename):
            # Load an HTTP url
            return urllib.urlopen(filename)
        else:
            return open(filename)
