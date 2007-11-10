"""
Simple script to make a Zope egg
"""

ZOPE_TARBALL = 'http://www.zope.org/Products/Zope/2.9.8/Zope-2.9.8-final.tgz'
SCP_LOCATION = 'flow.openplans.org:/www/svn.openplans.org/eggs/'

from cmdutils import OptionParser, CommandError, main_func
import os
import sys
import getpass
import tempfile
import urllib
import shutil
import atexit
import subprocess

DEFAULT_USERNAME = os.environ.get('OPENPLANS_USER', getpass.getuser())
DIST_LOCATION = 'lib/python/dist'

parser = OptionParser(
    usage='%prog [OPTIONS] [TARBALL]',
    version_package='fassembler',
    description="Create an egg and optionally upload it to openplans",
    max_args=1,
    use_logging=True)

parser.add_option(
    '--upload',
    metavar='SCP_LOCATION',
    help='Upload to the given scp location (default %s)' % SCP_LOCATION,
    default=SCP_LOCATION)

parser.add_option(
    '--upload-username',
    metavar='USERNAME',
    dest='upload_username',
    help='scp username (default %s; override with $OPENPLANS_USER)' % DEFAULT_USERNAME,
    default=DEFAULT_USERNAME)

parser.add_option(
    '--no-upload',
    action='store_true',
    dest='no_upload',
    help='Do not upload to openplans')

parser.add_option(
    '--keep-tempfiles',
    action='store_true',
    dest='keep_tempfiles',
    help='Do not delete temporary files')

parser.add_verbose()

files_to_delete = []
logger = None
def delete_files():
    for file in files_to_delete:
        if os.path.exists(file):
            logger.notify('Deleting file %s' % file)
            if os.path.isdir(file):
                shutil.rmtree(file)
            else:
                os.unlink(file)
atexit.register(delete_files)

@main_func(parser)
def main(options, args):
    global logger
    logger = options.logger
    if not args:
        tarball = ZOPE_TARBALL
    else:
        tarball = args[0]
    if tarball.startswith('http'):
        logger.notify('Downloading tarball from %s' % tarball)
        location = tarball
        tarball = os.path.abspath(os.path.basename(ZOPE_TARBALL))
        logger.notify('Destination file %s' % tarball)
        cmd = ['wget', '--continue', '--output-document', tarball, location]
        logger.info('Calling %s' % cmd)
        subprocess.call(cmd)
        if not options.keep_tempfiles:
            files_to_delete.append(tarball)
    tar_dest = os.path.splitext(os.path.basename(ZOPE_TARBALL))[0]
    if not os.path.exists(tar_dest):
        os.mkdir(tar_dest)
    else:
        logger.notify('Using existing directory %s' % tar_dest)
    if not options.keep_tempfiles:
        files_to_delete.append(tar_dest)
    cmd = ['tar', 'zfx', tarball]
    logger.info('Calling %s in %r' % (cmd, tar_dest))
    subprocess.call(cmd,
                    cwd=tar_dest)
    pkg_dest = os.path.join(tar_dest, os.listdir(tar_dest)[0])
    logger.notify('Creating egg')
    cmd = [sys.executable, '-c',
           'import setuptools, os; __file__=os.path.abspath("setup.py"); execfile("setup.py")',
           'bdist_egg']
    logger.info('Calling %s in %r' % (cmd, pkg_dest))
    subprocess.call(cmd,
                    cwd=pkg_dest)
    eggs = os.path.join(pkg_dest, DIST_LOCATION)
    egg = os.path.join(eggs, os.listdir(eggs)[0])
    logger.notify('Egg created: %s' % egg)
    logger.notify('Moving to current directory')
    egg_base = os.path.basename(egg)
    shutil.move(egg, egg_base)
    if not options.no_upload:
        scp_location = '%s@%s' % (options.upload_username, options.upload)
        cmd = ['scp', egg_base, scp_location]
        logger.info('Calling %s' % ' '.join(cmd))
        subprocess.call(cmd)
        if not options.keep_tempfiles:
            files_to_delete.append(egg_base)
    
if __name__ == '__main__':
    main()
    
