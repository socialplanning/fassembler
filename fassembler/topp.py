"""
General TOPP-related projects, for the initial setup of the
environment.
"""

import os
import socket
from cmdutils import CommandError
from fassembler.project import Project, Setting
from fassembler import tasks

class CheckBasePorts(tasks.Task):

    description = """
    Check that the ports {{task.base_port}} - {{int(task.base_port)+int(task.port_range)}} are open
    """

    base_port = tasks.interpolated('base_port')

    port_range = 7

    def __init__(self, name='Check base ports', base_port='{{config.base_port}}',
                 stacklevel=1):
        super(CheckBasePorts, self).__init__(name, stacklevel=stacklevel+1)
        self.base_port = base_port

    def run(self):
        base_port = int(self.base_port)
        port_range = int(self.port_range)
        self.logger.info('Checking ports %s-%s' % (base_port, base_port+port_range))
        bad = []
        for port in range(base_port, base_port+port_range+1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(('127.0.0.1', port))
            except socket.error, e:
                self.logger.info('Cannot bind port %s: %s' % (port, e))
                bad.append(port)
            else:
                sock.close()
        if bad:
            msg = 'Cannot bind to port(s): %s' % ', '.join(map(str, bad))
            self.logger.warn(msg)
            response = self.maker.ask('Continue despite unavailable ports?')
            if response == 'y':
                return
            raise CommandError(msg, show_usage=False)
        else:
            self.logger.info('All ports worked')

class EnvironRefresh(tasks.Task):

    description = """
    Update configuration from {{env.config_filename}} if necessary
    """

    def __init__(self, name='Refresh environ', stacklevel=1):
        super(EnvironRefresh, self).__init__(name, stacklevel=stacklevel+1)

    def run(self):
        self.environ.refresh_config()

class ToppProject(Project):
    """
    Create the basic layout used at TOPP for a set of applications.
    """

    name = 'topp'
    title = 'TOPP (openplans.org) Standard File Layout'
    project_base_dir = os.path.join(os.path.dirname(__file__), 'topp-files')

    settings = [
        Setting('requirements_svn_repo',
                inherit_config=('general', 'requirements_svn_repo'),
                default='https://svn.openplans.org/svn/build/requirements/trunk',
                help="Location where requirement files will be found for all builds"),
        Setting('base_port',
                inherit_config=('general', 'base_port'),
                help='The base port to use for application (each application is an offset from this port)'),
        Setting('var',
                default='{{env.base_path}}/var',
                inherit_config=('general', 'var'),
                help='The location where persistent files (persistent across builds) are kept'),
        Setting('etc_svn_repo',
                inherit_config=('general', 'etc_repository'),
                default='https://svn.openplans.org/svn/config/',
                help='Parent directory where the configuration that will go in etc/ comes from'),
        Setting('etc_svn_subdir',
                default='{{env.hostname}}-{{os.path.basename(env.base_path)}}',
                help='svn subdirectory where data configuration is kept (will be created if necessary)'),
        Setting('admin_password',
                default='',
                help='The admin password (will be auto-generated if not provided)'),
        Setting('db_prefix',
                default='',
                help='The prefix to use for all database names'),
        Setting('find_links',
                default='https://svn.openplans.org/eggs',
                help='Custom locations for distutils and easy_install to look in'),
        ]

    actions = [
        CheckBasePorts(),
        tasks.CopyDir('create layout', os.path.join(project_base_dir, 'base-layout'), './'),
        tasks.SvnCheckout('check out etc/', '{{config.etc_svn_subdir}}',
                          'etc/',
                          base_repository='{{config.etc_svn_repo}}',
                          on_create_set_props={'svn:ignore': 'projects.txt\n'},
                          create_if_necessary=True),
        EnvironRefresh(),
        tasks.SaveSetting('Save var setting',
                          {'var': '{{os.path.abspath(config.var)}}'}),
        tasks.SaveSetting('Save settings',
                          {'base_port': '{{config.base_port}}',
                           'topp_secret_filename': '{{env.var}}/secret.txt',
                           'admin_info_filename': '{{env.var}}/admin.txt',
                           'find_links': '{{config.find_links}}',
                           'db_prefix': '{{config.db_prefix}}',
                           'requirements_svn_repo': '{{config.requirements_svn_repo}}',
                           }),
        tasks.EnsureDir('Make sure var directory exists', '{{env.var}}', svn_add=False),
        tasks.SvnCheckout('check out requirements/', '{{config.requirements_svn_repo}}',
                          'requirements'),
        tasks.EnsureFile('Write secret.txt if necessary', '{{env.var}}/secret.txt', '{{env.random_string(40)}}',
                         overwrite=False),
        tasks.EnsureFile('Write admin.txt if necessary', '{{env.var}}/admin.txt',
                         'admin:{{config.admin_password or env.random_string(12, "alphanumeric")}}',
                         overwrite=False),
        ]



class SupervisorProject(Project):
    """
    Sets up Supervisor2 (http://www.plope.com/software/supervisor2/)
    """
    name = 'supervisor'
    title = 'Install Supervisor2'
    project_base_dir = os.path.join(os.path.dirname(__file__), 'supervisor-files')

    settings = [
        Setting('spec',
                default='requirements/supervisor-req.txt',
                help='Specification for installing Supervisor'),
        ]
    
    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install Supervisor',
                          '{{config.spec}}'),
        tasks.CopyDir('create config layout', project_base_dir, './'),
        tasks.EnsureDir('Ensure log directory exists',
                        '{{env.var}}/logs/supervisor'),
        tasks.EnsureDir('Ensure pid location exists',
                        '{{env.var}}/supervisor'),
        ]
