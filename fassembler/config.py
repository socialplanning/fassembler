from initools import configparser

class ConfigParser(configparser.RawConfigParser):
    global_section = True
    inherit_defaults = False
    extendable = True
    default_extend_section_name = '__name__'
