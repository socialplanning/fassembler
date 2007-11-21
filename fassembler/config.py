"""
The configuration file loader (based on INITools)
"""

from initools import configparser

class ConfigParser(configparser.RawConfigParser):
    global_section = True
    inherit_defaults = False
    extendable = True
    default_extend_section_name = '__name__'

    def getdefault(self, section, option, default=None):
        try:
            return self.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError), e:
            return default
