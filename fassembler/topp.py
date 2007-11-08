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
                default='http://svn.openplans.org/svn/config/',
                help='Parent directory where the configuration that will go in etc/ comes from'),
        Setting('etc_svn_subdir',
                default='{{env.hostname}}-{{os.path.basename(env.base_path)}}',
                help='svn subdirectory where data configuration is kept (will be created if necessary)'),
        ]

    actions = [
        tasks.CopyDir('create layout', project_base_dir, './'),
        tasks.SvnCheckout('check out etc/', '{{config.etc_svn_subdir}}',
                          'etc/',
                          base_repository='{{config.etc_svn_repository}}',
                          create_if_necessary=True),
        ## FIXME: write secret.txt
        tasks.SaveSetting('Save port', 'base_port', '{{config.base_port}}'),
        tasks.SaveSetting('Save secret filename', 'topp_secret_filename', '{{env.base_path}}/etc/secret.txt'),
        ]



class SupervisorProject(Project):
    """
    Sets up Supervisor2 (http://www.plope.com/software/supervisor2/)
    """
    name = 'supervisor'
    title = 'Install Supervisor2'
    project_base_dir = os.path.join(os.path.dirname(__file__), 'supervisor-files')

    settings = [
        Setting('supervisor_req',
                default='supervisor',
                help='Requirement specification to give easy_install (can be a directory)'),
        ]
    
    actions = [
        tasks.VirtualEnv(),
        ## FIXME: use poach-eggs:
        tasks.EasyInstall('Install supervisor', '{{config.supervisor_req}}'),
        tasks.CopyDir('create config layout', project_base_dir, './'),
        ]
