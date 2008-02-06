"""
Installation of a TOPP buildbot master.
"""

from fassembler import tasks
from fassembler.project import Project, Setting
import os
import socket
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



class BuildBotProject(Project):
    """Buildbot base project class"""

    _twisted_src = twisted_dirname

    files_dir = os.path.join(os.path.dirname(__file__), 'buildbot-files')
    skel_dir = os.path.join(files_dir, 'skel')

 
    depends_on_projects = ['fassembler:topp']

    hostname, platform, version = get_host_info()

    settings = [
        Setting('spec',
                default='requirements/buildbot-req.txt',
                help='Specification of packages to install'),
        Setting('buildmaster_host',
                default='localhost',
                help='Host the buildmaster runs on'),
        Setting('baseport',
                default='{{env.base_port}}',
                help="Base port"),

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
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install buildbot dependencies',
                          '{{config.spec}}'),
        GetTwistedSource(),
        tasks.Script('Install Twisted',
                     ['python', 'setup.py', 'install'],
                     use_virtualenv=True,
                     cwd='{{env.base_path}}/{{project.name}}/src/{{project._twisted_src}}'
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
    masterdir = 'master'

    settings = BuildBotProject.settings  + []

    actions = BuildBotProject.actions + [
        tasks.Script(
            'Make a buildbot master',
            ['bin/buildbot', 'create-master', masterdir],
            cwd='{{os.path.join(env.base_path, project.name)}}'
            ),
        tasks.EnsureFile(
             'Overwrite the buildbot master.cfg file',
             '{{os.path.join(env.base_path, project.name, project.masterdir, "master.cfg")}}',
             content_path='{{os.path.join(project.skel_dir, "master.cfg_tmpl")}}',
             force_overwrite=True, svn_add=False),
        ]
        

class BuildSlaveProject(BuildBotProject):

    """Install a Buildbot slave to connect to our build master"""

    name = 'buildslave'
    title = 'Installs a buildbot slave'

    settings = BuildBotProject.settings + [
        Setting('buildslave_name',
                default='{{project.name}}',
                help="Name of this build slave."),
        
        Setting('buildslave_dir',
                default='{{os.path.join(env.base_path, project.name)}}',
                help="Directory to put the buildslave in."),
        
        ]

    actions = BuildBotProject.actions + [
        tasks.Script(
            'Fetch the accept_certificates script',
            ['svn', 'export',
             'https://svn.openplans.org/svn/build/topp.build.buildbot/trunk/topp/build/buildbot/skel/bin/accept_certificates.sh'
             ],
            cwd='{{os.path.join(env.base_path, config.buildslave_dir, "bin")}}'
            ),
        tasks.Script(
            'Make a buildbot slave',
            ['bin/buildbot', 'create-slave', '--force',
             '{{config.buildslave_dir}}',
             '{{config.buildmaster_host}}:{{config.buildslave_port}}',
             '{{config.buildslave_name}}',
             '{{config.buildbot_passwd}}'
             ],
            cwd='{{os.path.join(env.base_path, project.name)}}'
            ),
        ]
