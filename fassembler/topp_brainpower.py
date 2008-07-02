"""
Installation of Brainpower
http://www.openplans.org/projects/brainpower
"""

from fassembler import tasks
from fassembler.project import Project, Setting
import os
import subprocess

interpolated = tasks.interpolated

apache_conf_prelude = """
To serve brainpower via apache and mod_python, you should put
this in your apache config:
"""

apache_conf_example = """
    <VirtualHost ...>
      ServerName ...
      SetEnv DJANGO_SETTINGS_MODULE brainpower.settings
      SetEnv PYTHON_EGG_CACHE /tmp/egg-cache
      DocumentRoot  {{task.htdocs}}
      <Location "/">
         SetHandler python-program
         PythonPath "['{{project.build_properties.get("virtualenv_bin_path") or "argh"}}'] + sys.path"
         PythonHandler brainpower_handler
         PythonDebug Off
      </Location>
      <Location "/adminmedia/">
        SetHandler None
      </Location>
    </VirtualHost>
        """

apache_conf_postscript = """
To avoid editing apache's config on every build, use a 'current'
symlink instead of the dated build directory for DocumentRoot and
PythonPath, and just update the symlink after each build.
"""

class InstallDjango(tasks.InstallTarball):

    version_path = interpolated('version_path')
    _tarball_url = interpolated('_tarball_url')
    _tarball_version = interpolated('_tarball_version')

    description = """
    Install Django {{task._tarball_version}}.

    This downloads {{task._tarball_url}}.
    """

    def __init__(self, stacklevel=1):
        super(InstallDjango, self).__init__(stacklevel)
        self.version_path = '{{task.dest_path}}/django_tarball_version.txt'
        self._tarball_url = '{{config.django_tarball_url}}'
        self._tarball_version = '{{config.django_tarball_version}}'

    def is_up_to_date(self):
        if not (self._tarball_version and self._tarball_url):
            self.logger.notify("No django version specified, skipping")
            return True
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


class AdminMediaLink(tasks.Task):

    htdocs = interpolated('htdocs')

    def __init__(self, name, stacklevel=1):
        super(AdminMediaLink, self).__init__(name, stacklevel=stacklevel+1)
        self.htdocs = '{{project.build_properties["virtualenv_path"]}}/htdocs'
        
    def run(self):
        self.maker.ensure_dir(self.htdocs, svn_add=False)
        linktarget = os.path.join(self.htdocs, 'adminmedia')
        py = self.interpolate(
            '{{project.build_properties["virtualenv_bin_path"]}}/python',
            stacklevel=1)
        script = subprocess.Popen(
            [py, '-c',
             'import os, django; print os.path.dirname(django.__file__)'],
            stdout=subprocess.PIPE)
        stdout, stderr = script.communicate()
        djangopath = stdout.strip()
        linksource = os.path.join(djangopath, 'contrib', 'admin', 'media')
        self.maker.ensure_symlink(linksource, linktarget, overwrite=True)
        apache_example = self.interpolate(apache_conf_example)
        self.logger.notify(apache_conf_prelude,
                           color='green')
        self.logger.notify(apache_example, color="yellow")
        self.logger.notify(apache_conf_postscript, color='green')
        
    
    
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

        Setting('db_engine',
                default='mysql',
                help="Engine to use for django's database"),
        Setting('db_host',
                default='',
                help="Database host"),

        Setting('db_username',
                default='root',
                help="Database user"),
        Setting('db_password',
                default='',
                help="Database password"),
        Setting('db_root_password',
                default='',
                help="Database root password"),
        
        Setting('db_name',
                default='brainpower',
                help="Database name"),
        Setting('test_db_name',
                default='brainpower_test',
                help="Scratch database name for tests"),
        
        Setting('secret_key',
                default='{{maker.ask_password("Enter secret key for Django or press enter for a random one")}}',
                help="Django's secret key"),
        
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
        tasks.CheckMySQLDatabase('Check main brainpower database exists'),
        tasks.CheckMySQLDatabase('Check test brainpower database exists',
                                 db_name='{{config.test_db_name}}'),
        tasks.SaveSetting('Save brainpower settings',
                          {'django_tarball_version': '{{config.django_tarball_version}}',
                           'django_tarball_url': '{{config.django_tarball_url}}',
                           'dev_port': '{{config.port}}',
                           'python': '{{config.python}}',
                           'flunc': '{{config.flunc}}',
                           'db_engine': '{{config.db_engine}}',
                           'db_username': '{{config.db_username}}',
                           'db_password': '{{config.db_password}}',
                           'db_host': '{{config.db_host}}',
                           'db_name': '{{config.db_name}}',
                           'secret_key': '{{config.secret_key}}',
                           },
                          section='brainpower'),
        tasks.Script('Initialize brainpower database',
                     ['brainpower/bin/manage.py', 'syncdb', '--noinput']),
        # Order of arguments matters here! Watch out for
        # django bug http://code.djangoproject.com/ticket/7595
        tasks.Script('Initialize brainpower test database',
                     ['brainpower/bin/manage.py', 'syncdb', '--settings=brainpower.test_settings', '--noinput']
                     ),

        AdminMediaLink('Link topp admin media into {{task.htdocs}}.'),
        ]
