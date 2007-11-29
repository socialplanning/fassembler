"""
Installation of the TOPP OpenCore environment.
"""

import os
import subprocess
import urllib
import shutil
from fassembler.project import Project, Setting
from fassembler import tasks
interpolated = tasks.interpolated
import warnings

warnings.filterwarnings('ignore', 'tempnam is .*')

tarball_version = '2.9.8openplans.1'
tarball_url = 'https://svn.openplans.org/eggs/OpenplansZope-%s.tar.bz2' % tarball_version
orig_zope_source = 'http://www.zope.org/Products/Zope/2.9.8/Zope-2.9.8-final.tgz'

class InstallZope(tasks.Task):

    dest_path = interpolated('src_path')
    version_path = interpolated('version_path')

    def __init__(self, stacklevel=1):
        super(InstallZope, self).__init__(
            'Install Zope', stacklevel=stacklevel+1)
        self.dest_path = '{{env.base_path}}/{{project.name}}/src/Zope'
        self.version_path = '{{task.dest_path}}/opencore_tarball_version.txt'

    def run(self):
        if os.path.exists(self.version_path):
            f = open(self.version_path)
            version = f.read().strip()
            f.close()
            if version == tarball_version:
                self.logger.notify('Version %s up-to-date' % version)
                return
        url = tarball_url
        tmp_fn = os.path.dirname(url)
        delete_tmp_fn = False
        try:
            self.logger.notify('Downloading %s' % url)
            if not self.maker.simulate:
                urllib.urlretrieve(url, tmp_fn)
            self.maker.run_command(
                'tar', 'jfx', tmp_fn,
                cwd=os.path.dirname(self.dest_path))
            self.maker.ensure_file(self.version_path, tarball_version, svn_add=False)
            delete_tmp_fn = True
        finally:
            if delete_tmp_fn and os.path.exists(tmp_fn):
                os.unlink(tmp_fn)

    def tmp_filename(self):
        return os.tempnam() + '.tar.bz2'

def make_tarball():
    filename = os.path.basename(tarball_url)
    dir = 'tmp-download'
    if not os.path.exists(dir):
        print 'creating %s' % dir
        os.makedirs(dir)
    tgz_filename = os.path.join(dir, os.path.basename(orig_zope_source))
    if os.path.exists(tgz_filename):
        print '%s already exists; not downloading' % tgz_filename
    else:
        print 'Downloading %s to %s' % (orig_zope_source, tgz_filename)
        urllib.urlretrieve(orig_zope_source, tgz_filename)
    print 'Unpacking'
    print 'Running tar zfx %s (in %s)' % (tgz_filename, dir)
    proc = subprocess.Popen(['tar', 'zfx', os.path.basename(tgz_filename)], cwd=dir)
    proc.communicate()
    base_name = os.path.splitext(os.path.basename(tgz_filename))[0]
    dest_name = os.path.join(dir, 'Zope')
    if os.path.exists(dest_name):
        print 'Deleting %s' % dest_name
        shutil.rmtree(dest_name)
    print 'Moving %s to %s' % (base_name, dest_name)
    shutil.move(os.path.join(dir, base_name), dest_name)
    patch_dir = os.path.join(os.path.dirname(__file__), 'opencore-files', 'patches')
    for fn in os.listdir(patch_dir):
        fn = os.path.abspath(os.path.join(patch_dir, fn))
        print 'Running patch -p0 --forward -i %s' % fn
        proc = subprocess.Popen(['patch', '-p0', '--forward', '-i', fn], cwd=dest_name)
        proc.communicate()
    print 'Creating %s' % filename
    print 'Running tar cfj %s Zope (in %s)' % (filename, dir)
    proc = subprocess.Popen(['tar', 'cfj', filename, 'Zope'], cwd=dir)
    proc.communicate()
    # use compileall?
    # delete the dir?
    # upload?
    print 'You may want to run this now:'
    print '  scp %s flow.openplans.org:/www/svn.openplans.org/eggs/' % os.path.join(dir, filename)

class OpenCoreProject(Project):
    """
    Install OpenCore
    """

    name = 'opencore'
    title = 'Install OpenCore'

    settings = [
        Setting('spec',
                default=os.path.join(os.path.dirname(__file__), 'opencore-files', 'opencore-requirements.txt'),
                help='Specification of packages to install'),
        Setting('zope_instance',
                default='var/opencore/zope',
                help='Instance home for Zope'),
        Setting('zeo_instance',
                default='var/opencore/zeo',
                help='Instance home for ZEO'),
        Setting('zope_user',
                default='{{env.parse_auth(env.config.get("general", "admin_info_filename")).username}}',
                help='Default admin username'),
        Setting('zope_password',
                default='{{env.parse_auth(env.config.get("general", "admin_info_filename")).password}}',
                help='Admin password'),
        Setting('port',
                default='{{env.config.getint("general", "base_port")+int(config.port_offset)}}',
                help="Port to install Zope on"),
        Setting('port_offset',
                default='1',
                help='Offset from base_port for Zope'),
        Setting('host',
                default='localhost',
                help='Interface/host to serve Zope on'),
        Setting('zeo_port',
                default='{{env.config.getint("general", "base_port")+int(config.zeo_port_offset)}}',
                help="Port to install ZEO on"),
        Setting('zeo_port_offset',
                default='2',
                help='Offset from base_port for ZEO'),
        Setting('zeo_host',
                default='localhost',
                help='Interface/host to serve ZEO on'),
        Setting('zope_source',
                default='{{project.build_properties["virtualenv_path"]}}/src/Zope',
                help='Location of Zope source'),
        Setting('zope_svn_repo',
                default='http://svn.zope.de/zope.org/Zope/branches/2.9',
                help='Location of Zope svn'),
        Setting('zope_egg',
                default='Zope==2.98_final',
                help='Requirement for installing Zope'),
        ## FIXME: not sure if this is right:
        ## FIXME: should also be more global
        ## FIXME: also, type check on bool-ness
        Setting('debug',
                default='0',
                help='Whether to start Zope in debug mode'),
        Setting('email_confirmation',
                default='0',
                help='Whether to send email configuration'),
        ]

    files_dir = os.path.join(os.path.dirname(__file__), 'opencore-files')
    patch_dir = os.path.join(files_dir, 'patches')
    skel_dir = os.path.join(files_dir, 'zope_skel')

    ## FIXME: I don't think this is the right way to start Zope, even under
    ## Supervisor:
    start_script_template = """\
#!/bin/sh
exec {{env.base_path}}/bin/zopectl fg
"""

    actions = [
        tasks.VirtualEnv(),
        InstallZope(),
        tasks.InstallSpec('Install OpenCore',
                          '{{config.spec}}'),
        tasks.CopyDir('Create custom skel',
                      skel_dir, '{{project.name}}/src/Zope/custom_skel'),
        #tasks.Script('Configure Zope', [
        #'./configure', '--prefix', '{{project.build_properties["virtualenv_path"]}}'],
        #cwd='{{config.zope_source}}'),
        #tasks.Script('Make Zope', ['make'], cwd='{{config.zope_source}}'),
        #tasks.Script('Install Zope', ['make', 'inplace'], cwd='{{config.zope_source}}'),
        tasks.Script('Make Zope Instance', [
        'python', '{{config.zope_source}}/bin/mkzopeinstance.py', '--dir', '{{config.zope_instance}}',
        '--user', '{{config.zope_user}}:{{config.zope_password}}',
        '--skelsrc', '{{config.zope_source}}/custom_skel'],
                     use_virtualenv=True),
        tasks.Script('Make ZEO Instance', [
        'python', '{{config.zope_source}}/bin/mkzeoinstance.py', '{{config.zeo_instance}}', '{{config.zeo_port}}'],
                     use_virtualenv=True),
        ## FIXME: linkzope and linkzopebinaries?
        ## FIXME: Write start script
        tasks.InstallSupervisorConfig(),
        tasks.EnsureFile('Write the start script',
                         '{{env.base_path}}/bin/start-{{project.name}}',
                         content=start_script_template,
                         svn_add=True,
                         executable=True),
        tasks.SaveURI(uri_template='${uri}/VirtualHostBase/http/${HTTP_HOST}/openplans/projects/${project}/VirtualHostRoot',
                      path='/'),
        tasks.SaveURI(project_name='opencore_global',
                      uri_template='${uri}/VirtualHostBase/http/${HTTP_HOST}/openplans/VirtualHostRoot',
                      path='/',
                      project_local=False)
        # ZEO doesn't really have a uri
        ]

if __name__ == '__main__':
    make_tarball()
