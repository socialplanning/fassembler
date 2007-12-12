"""
Patch distutils files
"""

import os
import re

def find_distutils_file(logger):
    """
    Returns the location of the main distutils.cfg file
    """
    import distutils.dist
    dist = distutils.dist.Distribution(None)
    files = dist.find_config_files()
    writable_files = []
    for file in files:
        if not os.path.exists(file):
            logger.info('Distutils config file %s does not exist' % file)
            continue
        if os.access(file, os.W_OK):
            logger.debug('Distutils config %s is writable' % file)
            writable_files.append(file)
        else:
            logger.notify('Distutils config %s is not writable' % file)
    if not files:
        logger.fatal(
            'Could not find any existing writable config file (tried options %s)'
            % ', '.join(files))
        raise OSError("No config files found")
    if len(files) > 1:
        logger.notify(
            "Choosing file %s among writable options %s"
            % (files[0], ', '.join(files[1:])))
    return files[0]

def update_distutils_file(filename, section, name, value, logger, append=False):
    """
    Adds the setting ``name = value`` to ``[section]`` in ``filename``

    If ``append`` is true and the value already exists, then the value
    will be appended to the current value (on a separate line).
    """
    f = open(filename, 'r')
    lines = f.readlines()
    f.close()
    section_index = None
    for index, line in enumerate(lines):
        if line.strip().startswith('[%s]' % section):
            section_index = index
            break
    if section_index is None:
        logger.info('Adding section [%s]' % section)
        lines.append('\n')
        lines.append('[%s]\n' % section)
        lines.append('%s = %s\n' % (name, value))
    else:
        start_item_index = None
        item_index = None
        name_regex = re.compile(r'^%s\s*[=:]' % re.escape(name))
        whitespace_regex = re.compile(r'^\s+')
        for index_offset, line in enumerate(lines[section_index+1:]):
            index = index_offset + section_index + 1
            if item_index is not None:
                if whitespace_regex.match(line):
                    # continuation; point to last line
                    item_index = index
                else:
                    break
            if name_regex.match(line):
                start_item_index = item_index = index
            if line.startswith('['):
                # new section
                break
        if item_index is None:
            logger.info('Added %s to section [%s]' % (name, section))
            lines.insert(section_index+1,
                         '%s = %s\n' % (name, value))
        elif append:
            logger.info('Appended value %s to setting %s' % (value, name))
            lines.insert(item_index+1,
                         '    %s\n' % value)
        else:
            logger.info('Replaced setting %s' % name)
            lines[start_item_index:item_index+1] = ['%s = %s\n' % (name, value)]
    f = open(filename, 'w')
    f.writelines(lines)
    f.close()
