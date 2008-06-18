"""
Installation of Brainpower
http://www.openplans.org/projects/brainpower
"""

from fassembler import tasks
from fassembler.project import Project, Setting
import os
import subprocess
import sys

interpolated = tasks.interpolated

class InstallDjango(tasks.InstallTarball):

    version_path = interpolated('version_path')
    _tarball_url = interpolated('_tarball_url')
    _tarball_version = interpolated('_tarball_version')


    def __init__(self, stacklevel=1):
        super(InstallDjango, self).__init__(stacklevel)
        self.version_path = '{{task.dest_path}}/django_tarball_version.txt'
        self._tarball_url = '{{config.django_tarball_url}}'
        self._tarball_version = '{{config.django_tarball_version}}'

    def is_up_to_date(self):
        if os.path.exists(self.version_path):
            f = open(self.version_path)
            version = f.read().strip()
            f.close()
            if version == self._tarball_version:
                self.logger.notify('Version %s up-to-date' % version)
                return True

    def post_unpack_hook(self):
        self.maker.ensure_file(self.version_path, self._tarball_version,
                               svn_add=False)
        where = self.dest_path + '/Django-%s' % self._tarball_version
        py = self.interpolate(
            '{{project.build_properties["virtualenv_bin_path"]}}/python',
            stacklevel=1)
        self.maker.run_command(py, 'setup.py', 'install', cwd=where)

class BrainpowerProject(Project):
    """Brainpower base project class"""

    name = 'brainpower'
    title = 'Installs Brainpower'
    
    depends_on_projects = ['fassembler:topp']

    def get_req_setting(self, setting):
        return self.req_settings.get(setting, '')

    settings = [
        Setting('port_offset',
                default='11',
                help='Port offset from base_port to run the dev django server on'),
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help="Port to run the dev django server on"),
        Setting('spec',
                default='requirements/brainpower-req.txt',
                help='Specification of packages to install'),
        Setting('django_tarball_url',
                default='{{project.get_req_setting("django_tarball_url")}}',
                help='Where to download the django source',
                ),
        Setting('django_tarball_version',
                default='{{project.get_req_setting("django_tarball_version")}}',
                help='Version of Django to install',
                ),
        Setting('python',
                default='{{project.build_properties.get("virtualenv_python")}}',
                help='Where our Python gets installed',
                ),
        Setting('flunc',
                default='{{project.build_properties.get("virtualenv_bin_path") + "/flunc"}}',
                help="Where our Flunc executable is installed.",
                )
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install brainpower dependencies',
                          '{{config.spec}}'),
        InstallDjango(),
        tasks.SaveSetting('Save brainpower settings',
                          {'django_tarball_version': '{{config.django_tarball_version}}',
                           'django_tarball_url': '{{config.django_tarball_url}}',
                           'dev_port': '{{config.port}}',
                           'python': '{{config.python}}',
                           'flunc': '{{config.flunc}}',

                           },
                          section='brainpower'),
        ]


