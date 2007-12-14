"""
General TOPP-related projects, for the initial setup of the
environment.
"""

import os
from fassembler.project import Project, Setting
from fassembler import tasks

class ToppProject(Project):
    """
    Create the basic layout used at TOPP for a set of applications.
    """

    name = 'topp'
    title = 'TOPP (openplans.org) Standard File Layout'
    project_base_dir = os.path.join(os.path.dirname(__file__), 'topp-files')

    settings = [
        ## FIXME: this *should* draw from the global settings if it is not set
        Setting('requirements_svn_repo',
                inherit_config=('general', 'requirement_profile'),
                default='https://svn.openplans.org/svn/build/requirements/trunk',
                help="Location where requirement files will be found for all builds"),
        Setting('base_port',
                inherit_config=('general', 'base_port'),
                help='The base port to use for application (each application is an offset from this port)'),
        Setting('var',
                inherit_config=('general', 'var'),
                help='The location where persistent files (persistent across builds) are kept'),
        Setting('etc_svn_repository',
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
        ]

    actions = [
        tasks.CopyDir('create layout', os.path.join(project_base_dir, 'base-layout'), './'),
        tasks.SaveSetting('Save var setting',
                          {'var': '{{os.path.abspath(config.var)}}'}),
        tasks.SaveSetting('Save settings',
                          {'base_port': '{{config.base_port}}',
                           'topp_secret_filename': '{{env.var}}/secret.txt',
                           'admin_info_filename': '{{env.var}}/admin.txt',
                           }),
        tasks.SaveSetting('Save db_prefix', {'db_prefix': '{{config.db_prefix}}'}, overwrite_if_empty=False),
        tasks.EnsureDir('Make sure var directory exists', '{{env.var}}', svn_add=False),
        tasks.SvnCheckout('check out etc/', '{{config.etc_svn_subdir}}',
                          'etc/',
                          base_repository='{{config.etc_svn_repository}}',
                          create_if_necessary=True),
        tasks.SvnCheckout('checkout out requirements/', '{{config.requirements_svn_repo}}',
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
