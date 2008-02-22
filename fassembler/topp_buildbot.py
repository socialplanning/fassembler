"""
Installation of a TOPP buildbot master.
"""

from fassembler import tasks
from fassembler.project import Project, Setting
import os
import subprocess
import sys

interpolated = tasks.interpolated

twisted_dirname = 'Twisted-2.5.0'
tarball_url = 'http://tmrc.mit.edu/mirror/twisted/Twisted/2.5/%s.tar.bz2' % twisted_dirname


def get_host_info():
    uname = os.uname()
    platform = sys.platform.title()
    if platform.startswith('Linux'):
        platform = 'Linux'
        # Hopefully this includes distro info on all linuxes?
        version = os.uname()[2]
    elif platform == 'Darwin':
        # we're more interested in "OSX" than "darwin".
        platform = 'Mac OSX'
        # thanks doug!
        cmd = subprocess.Popen("osascript -e 'tell app \"Finder\" to version'")
        version = cmd.stdout.read().strip()
    else:
        version = ''
    hostname = uname[1]
    return hostname, platform, version


class GetTwistedSource(tasks.InstallTarball):

    # easy_install twisted isn't possible, see
    # http://twistedmatrix.com/trac/ticket/1286
    # so we install from a tarball.
    
    _tarball_url = tarball_url
    _src_name = twisted_dirname
    _marker = interpolated('_marker')

    def __init__(self, stacklevel=1):
        super(GetTwistedSource, self).__init__(stacklevel=stacklevel+1)
        self._marker = '{{os.path.join(task.dest_path, ".marker")}}'

    def post_unpack_hook(self):
        # This is just a marker file to show for future runs that we
        # successfully downloaded and unpacked the tarball.
        open(self._marker, 'w').write('')

    def is_up_to_date(self):
        return os.path.exists(self._marker)


editwarning = '''!!! WARNING !!! This is a generated file.  DO NOT EDIT!

Instead you should edit (and commit) the tmpl file in the fassembler
source, under {{project.skel_dir}}, then re-run fassembler to
regenerate this file.
'''

class BuildBotProject(Project):
    """Buildbot base project class"""


    _twisted_src = twisted_dirname

    files_dir = os.path.join(os.path.dirname(__file__), 'buildbot-files')
    skel_dir = os.path.join(files_dir, 'skel')

 
    depends_on_projects = ['fassembler:topp']

    hostname, platform, version = get_host_info()

    buildslave_dirname = 'buildslave'

    settings = [
        Setting('buildbot_url',
                default='http://{{project.hostname}}.openplans.org:{{config.buildmaster_private_port}}/',
                help='Public URL of the buildbot web page',
                ),
        Setting('spec',
                default='requirements/buildbot-req.txt',
                help='Specification of packages to install'),
        Setting('buildmaster_host',
                default='localhost',
                help='Host the buildmaster runs on'),
        Setting('baseport',
                default='{{env.base_port}}',
                help="Base port"),

        Setting('child_baseport',
                default='{{env.base_port +  1000}}',
                help="Base port for applications built by the bots"),
        Setting('buildmaster_private_port',
                default='{{env.base_port+int(config.buildmaster_private_offset)}}',
                help="Port to run the private buildmaster on (force build allowed)"),
        Setting('buildmaster_private_offset',
                default='20',
                help="Offset from base_port for the public build master."),

        Setting('buildmaster_public_port',
                default='{{env.base_port+int(config.buildmaster_public_offset)}}',
                help="Port to run the public buildmaster on (force build disallowed)"),
        Setting('buildmaster_public_offset',
                default='21',
                help="Offset from base_port for the public build master."),
        
        Setting('buildslave_port',
                default='{{env.base_port+int(config.buildslave_port_offset)}}',
                help="Port build slaves connect to the master on"),
        Setting('buildslave_port_offset',
                default='22',
                help='Offset from base_port for the build slave connect port.'),

        Setting('buildbot_passwd',
                help="Password for buildslaves to connect to master."),

        Setting('buildslave_dir',
                default='{{project.buildslave_dirname}}',
                help="Subdirectory to put the buildslave in. Must be relative"
                ),
        Setting('oc_basedir',
                default='oc',
                help='Subdirectory where slave will build stuff.',
                ),
        Setting('editwarning',
                default=editwarning,
                help='Text to warn people about editing generated files.'
                ),
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install buildbot dependencies',
                          '{{config.spec}}'),
        GetTwistedSource(),
        tasks.Script('Install Twisted',
                     ['python', 'setup.py', 'install'],
                     use_virtualenv=True,
                     cwd='{{os.path.join(env.base_path, project.name, "src", project._twisted_src)}}'
                     ),
        # XXX This fails about half the time, because sourceforge sucks.
        # Just re-run until it works.
        tasks.EasyInstall('Install buildbot', 'buildbot>=0.7.6'),
        ]


class BuildMasterProject(BuildBotProject):

    """Install Buildbot master that controls our automated builds & tests.
    """

    name = 'buildmaster'
    title = 'Installs a buildbot master'

    settings = BuildBotProject.settings  + [
        Setting('master_dir',
                default='{{os.path.join(env.base_path, project.name)}}',
                help="Directory to put the build master in."
                ),
        ]

    actions = BuildBotProject.actions + [
        tasks.Script(
            'Make a buildbot master',
            ['bin/buildbot', 'create-master', '{{config.master_dir}}'],
            cwd='{{config.master_dir}}'
            ),
        tasks.EnsureFile(
             'Overwrite the buildbot master.cfg file',
             '{{os.path.join(config.master_dir, "master.cfg")}}',
             content_path='{{os.path.join(project.skel_dir, "master.cfg_tmpl")}}',
             force_overwrite=True, svn_add=False),
        ]
        

class BuildSlaveProject(BuildBotProject):

    """Install a Buildbot slave to connect to our build master"""

    name = BuildBotProject.buildslave_dirname
    title = 'Installs a buildbot slave'

    settings = BuildBotProject.settings + [
        Setting('buildslave_name',
                help="Name of this build slave."
                ),
        Setting('buildslave_description',
                default='{{project.platform}} {{project.version}} running on {{project.hostname}}',
                help="Public description of your build slave's platform.",
                )
        ]

    actions = BuildBotProject.actions + [
        tasks.EnsureFile(
            'Install the accept_certificates script',
            '{{os.path.join(config.buildslave_dir, "bin", "accept_certificates.sh")}}',
            content_path='{{os.path.join(project.skel_dir, "accept_certificates.sh")}}',
            force_overwrite=True, svn_add=False, executable=True),
        tasks.Script(
            'Move aside the old config if it exists',
            'test -f {{config.buildslave_dir}}/buildbot.tac && mv -f {{config.buildslave_dir}}/buildbot.tac {{config.buildslave_dir}}/buildbot.tac.old || echo nothing to move',
            cwd='{{env.base_path}}',
            shell=True),
        tasks.Script(
            'Make a buildbot slave',
            ['bin/buildbot', 'create-slave',
             '--keepalive=60',  # Jeff warns that they lose connection at default
             '.',
             '{{config.buildmaster_host}}:{{config.buildslave_port}}',
             '{{config.buildslave_name}}',
             '{{config.buildbot_passwd}}'
             ],
            cwd='{{os.path.join(env.base_path, config.buildslave_dir)}}'
            ),
        tasks.EnsureFile(
             'Overwrite the buildslave host info file',
             '{{os.path.join(config.buildslave_dir, "info", "host")}}',
             content_path='{{os.path.join(project.skel_dir, "host_tmpl")}}',
             force_overwrite=True, svn_add=False),
        tasks.EnsureFile(
             'Overwrite the buildslave admin info file',
             '{{os.path.join(config.buildslave_dir, "info", "admin")}}',
             content_path='{{os.path.join(project.skel_dir, "admin_tmpl")}}',
             force_overwrite=True, svn_add=False),
        tasks.EnsureFile(
            'Install the test wrapper maker',
            '{{os.path.join(config.buildslave_dir, "bin", "mkzopetest.sh")}}',
            content_path='{{os.path.join(project.skel_dir, "mkzopetest.sh")}}',
            force_overwrite=True, svn_add=False, executable=True),

        ]
