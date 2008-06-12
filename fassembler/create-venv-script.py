"""
Call this like ``python fassembler/create-venv-script.py``; it will
refresh the fassembler-boot.py script
"""
import os
import subprocess
import re

here = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(here)
script_name = os.path.join(base_dir, 'fassembler-boot.py')

import virtualenv

EXTRA_TEXT = """
FASS_SVN_LOCATION = '/'.join('$HeadURL: $'[len('HeadURL')+2:-1].strip().split('/')[:-1])
if not FASS_SVN_LOCATION:
    # Happens when this is trunk
    FASS_SVN_LOCATION = 'https://svn.openplans.org/svn/fassembler/trunk'

import shutil

def extend_parser(parser):
    parser.add_option(
        '--svn',
        metavar='DIR_OR_URL',
        dest='fassembler_svn',
        default=FASS_SVN_LOCATION,
        help='Location of a svn directory or URL to use for the installation')

def adjust_options(options, args):
    if not args:
        return # caller will raise error
    
    # We're actually going to build the venv in a subdirectory
    base_dir = args[0]
    args[0] = join(base_dir, 'fassembler')

def after_install(options, home_dir):
    base_dir = os.path.dirname(home_dir)
    src_dir = join(home_dir, 'src')
    fassembler_svn = options.fassembler_svn
    if os.path.exists(fassembler_svn):
        # A directory
        logger.debug('Using svn checkout in directory %s' % fassembler_svn)
        fassembler_dir = os.path.abspath(fassembler_svn)
        logger.info('Using existing svn checkout at %s' % fassembler_dir)
    else:
        fassembler_dir = join(src_dir, 'fassembler')
        logger.notify('Installing fassembler from %s to %s' % (fassembler_svn, fassembler_dir))
        fs_ensure_dir(src_dir)
        call_subprocess(['svn', 'checkout', '--quiet', FASS_SVN_LOCATION, fassembler_dir],
                        show_stdout=True)
    logger.indent += 2
    try:
        call_subprocess([os.path.abspath(join(home_dir, 'bin', 'easy_install')), '-f', 'https://svn.openplans.org/eggs', 'mysql-python'],
                        cwd=os.path.abspath(fassembler_dir),
                        filter_stdout=filter_python_develop,
                        show_stdout=False)
        call_subprocess([os.path.abspath(join(home_dir, 'bin', 'python')), 'setup.py', 'develop'],
                        cwd=os.path.abspath(fassembler_dir),
                        filter_stdout=filter_python_develop,
                        show_stdout=False)
    finally:
        logger.indent -= 2
    script_dir = join(base_dir, 'bin')
    script_dest = join(script_dir, 'fassembler')
    logger.notify('Copying fassembler to %s' % script_dest)
    fs_ensure_dir(script_dir)
    os.symlink('../fassembler/bin/fassembler', script_dest)
    etc_dir = join(base_dir, 'etc')
    build_ini = join(etc_dir, 'build.ini')
    if not os.path.exists(build_ini):
        fs_ensure_dir(etc_dir)
        logger.notify('Touching %s' % build_ini)
        f = open(build_ini, 'w')
        f.close()
    logger.notify('Run "%s fassembler:topp" (etc) to build out the environment'
                  % script_dest)
    logger.notify('Run "%s Package" to install new packages that provide builds'
                  % join(home_dir, 'bin', 'easy_install'))

def fs_ensure_dir(dir):
    if not os.path.exists(dir):
        logger.info('Creating directory %s' % dir)
        os.makedirs(dir)

def filter_python_develop(line):
    if not line.strip():
        return Logger.DEBUG
    for prefix in ['Searching for', 'Reading ', 'Best match: ', 'Processing ',
                   'Moving ', 'Adding ', 'running ', 'writing ', 'Creating ',
                   'creating ', 'Copying ']:
        if line.startswith(prefix):
            return Logger.DEBUG
    return Logger.NOTIFY
"""

def main():
    text = virtualenv.create_bootstrap_script(EXTRA_TEXT, python_version='2.4')
    if os.path.exists(script_name):
        f = open(script_name)
        cur_text = f.read()
        f.close()
    else:
        cur_text = ''
    print 'Updating %s' % script_name
    if cur_text == 'text':
        print 'No update'
    else:
        print 'Script changed; updating...'
        f = open(script_name, 'w')
        f.write(text)
        f.close()

if __name__ == '__main__':
    main()

