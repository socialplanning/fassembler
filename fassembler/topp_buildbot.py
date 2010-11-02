"""
Installation of a TOPP buildbot master.
"""

from fassembler import tasks
from fassembler.project import Project, Setting
import os
import subprocess
import sys

interpolated = tasks.interpolated

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


editwarning = '''!!! WARNING !!! This is a generated file.  DO NOT EDIT!

Instead you should edit (and commit) the tmpl file in the fassembler
source, at {{project.skel_dir}}/{{config.stack_to_build}}_master.cfg_tmpl, then
re-run fassembler to regenerate this file.
'''

class BuildBotProject(Project):
    """Buildbot base project class"""


    files_dir = os.path.join(os.path.dirname(__file__), 'buildbot-files')
    skel_dir = os.path.join(files_dir, 'skel')

 
    depends_on_projects = ['fassembler:topp']

    hostname, platform, version = get_host_info()

    buildslave_dirname = 'buildslave'

    settings = [
        Setting('buildbot_url',
                inherit_config=('general', 'buildbot_url'),
                default='http://buildbot.socialplanning.org',
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
                help="Base port for applications built by the bots. There are multiple builders, so choose a number where you have a few hundred ports free after that!"),  # It kind of sucks that the master config is in charge of this.
        Setting('buildmaster_private_port',
                default='{{env.base_port+int(config.buildmaster_private_offset)}}',
                help="Port to run the private buildmaster on (force build allowed)"),
        Setting('buildmaster_private_offset',
                default='20',
                help="Offset from base_port for the private build master."),

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
        Setting('basedir',
                default='build',
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
        tasks.SaveSetting('Save buildbot settings',
                          {'buildbot_url': '{{config.buildbot_url}}'},
                          section='general'),
        ]


class BuildMasterProject(BuildBotProject):

    """Install Buildbot master that controls our automated builds & tests.
    """

    name = 'buildmaster'
    title = 'Installs a buildbot master'

    config_template = 'master.cfg_tmpl'

    settings = BuildBotProject.settings  + [
        Setting('master_dir',
                default='{{os.path.join(env.base_path, project.name)}}',
                help="Directory to put the build master in."
                ),
        Setting('stack_to_build',
                default='openplans',
                help="Which stack to build (choose one of: openplans, almanac)"
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
             content_path='{{os.path.join(project.skel_dir, config.stack_to_build)}}_master.cfg_tmpl',
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
        tasks.EnsureDir('Make sure src directory exists',
                        '{{os.path.join(config.buildslave_dir, "src")}}',
                        svn_add=False),
        tasks.EnsureFile(
            'Install the accept_certificates script',
            '{{os.path.join(config.buildslave_dir, "bin", "accept_certificates.sh")}}',
            content_path='{{os.path.join(project.skel_dir, "accept_certificates.sh")}}',
            force_overwrite=True, svn_add=False, executable=True),
        tasks.SourceInstall(
            'Install the port killer script',
            'https://svn.socialplanning.org/svn/standalone/portutils/trunk/',
            'portutils'
            ),
        tasks.Script(
            'Move aside the old config if it exists',
            'test -f {{config.buildslave_dir}}/buildbot.tac && mv -f {{config.buildslave_dir}}/buildbot.tac {{config.buildslave_dir}}/buildbot.tac.old || echo nothing to move',
            cwd='{{env.base_path}}',
            shell=True),
        tasks.Script(
            'Make a buildbot slave',
            ['bin/buildbot', 'create-slave',
             '--keepalive=60',  # Jeff warns that they lose connection at default
	     '--umask=002',  # it's 077 by default.
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

        ]
