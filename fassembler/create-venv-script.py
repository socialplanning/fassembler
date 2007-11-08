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
import shutil

def adjust_options(options, args):
    # We're actually going to build the venv in a subdirectory
    base_dir = args[0]
    args[0] = join(base_dir, 'fassembler')

def after_install(options, home_dir):
    base_dir = os.path.dirname(home_dir)
    src_dir = join(home_dir, 'src')
    fassembler_dir = join(src_dir, 'fassembler')
    logger.notify('Installing fassembler from __SVN_LOCATION__ to %s' % fassembler_dir)
    fs_ensure_dir(src_dir)
    call_subprocess(['svn', 'checkout', '--quiet', '__SVN_LOCATION__', fassembler_dir],
                    show_stdout=True)
    call_subprocess([os.path.abspath(join(home_dir, 'bin', 'python')),
                     'setup.py', 'develop'],
                    cwd=os.path.abspath(fassembler_dir),
                    filter_stdout=filter_python_develop,
                    show_stdout=False)
    script_dir = join(base_dir, 'bin')
    script_dest = join(script_dir, 'fassembler')
    logger.notify('Copying fassembler to %s' % script_dest)
    fs_ensure_dir(script_dir)
    script_src = join(home_dir, 'bin', 'fassembler')
    shutil.copyfile(script_src, script_dest)
    shutil.copymode(script_src, script_dest)
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
        
fs_first_develop = False

def filter_python_develop(line):
    global fs_first_develop
    if not line.strip():
        return Logger.DEBUG
    for prefix in ['Searching for', 'Reading ', 'Best match: ', 'Processing ',
                   'Moving ', 'Adding ', 'running ', 'writing ', 'Creating ',
                   'creating ', 'Copying ']:
        if line.startswith(prefix):
            return Logger.DEBUG
    if not fs_first_develop:
        fs_first_develop = True
    else:
        line = '  '+line
    return (Logger.NOTIFY, line)
"""


_repo_url_re = re.compile(r'^URL:\s+(.*)$', re.MULTILINE)

def find_svn_location():
    """
    Returns the svn location where this script is located
    """
    proc = subprocess.Popen(
        ['svn', 'info', base_dir],
        stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    match = _repo_url_re.search(stdout)
    if not match:
        print 'svn info %s output:' % base_dir
        print stdout
        raise OSError(
            "Could not find svn URL")
    return match.group(1)

def main():
    text = virtualenv.create_bootstrap_script(EXTRA_TEXT)
    svn_location = find_svn_location()
    text = text.replace('__SVN_LOCATION__', svn_location)
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

