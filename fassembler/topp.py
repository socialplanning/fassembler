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
        Setting('base_port',
                inherit_config=('general', 'base_port'),
                help='The base port to use for application (each application is an offset from this port)'),
        Setting('etc_svn_repository',
                inherit_config=('general', 'etc_repository'),
                default='https://svn.openplans.org/svn/config/',
                help='Parent directory where the configuration that will go in etc/ comes from'),
        Setting('etc_svn_subdir',
                default='{{env.hostname}}-{{os.path.basename(env.base_path)}}',
                help='svn subdirectory where data configuration is kept (will be created if necessary)'),
        Setting('admin_password',
                default=None,
                help='The admin password (will be auto-generated if not provided)'),
        Setting('db_prefix',
                default=None,
                help='The prefix to use for all database names'),
        ]

    actions = [
        tasks.CopyDir('create layout', os.path.join(project_base_dir, 'base-layout'), './'),
        tasks.SvnCheckout('check out etc/', '{{config.etc_svn_subdir}}',
                          'etc/',
                          base_repository='{{config.etc_svn_repository}}',
                          create_if_necessary=True),
        tasks.EnsureFile('Write secret.txt if necessary', '{{env.base_path}}/var/secret.txt', '{{env.random_string(40)}}',
                         overwrite=False),
        tasks.EnsureFile('Write admin.txt if necessary', '{{env.base_path}}/var/admin.txt',
                         'admin:{{config.admin_password or env.random_string(12, "alphanumeric")}}',
                         overwrite=False),
        tasks.SaveSetting('Save port', 'base_port', '{{config.base_port}}'),
        tasks.SaveSetting('Save secret filename', 'topp_secret_filename', '{{env.base_path}}/var/secret.txt'),
        tasks.SaveSetting('Save admin u/p', 'admin_info_filename', '{{env.base_path}}/var/admin.txt'),
        tasks.SaveSetting('Save db_prefix', 'db_prefix', '{{db_prefix}}', overwrite_if_empty=False),
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
                default=os.path.join(os.path.dirname(__file__), 'topp-files', 'supervisor-requirements.txt'),
                help='Specification for installing Supervisor'),
        ]
    
    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install Supervisor',
                          '{{config.spec}}'),
        tasks.CopyDir('create config layout', project_base_dir, './'),
        ]
