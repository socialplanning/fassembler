"""
Misc. builders for various smaller topp products
"""

import os
from fassembler.project import Project, Setting
from fassembler import tasks
from tempita import Template

class ScriptTranscluderProject(Project):
    """
    Install ScriptTranscluder
    """
    
    name = 'scripttranscluder'
    title = 'Install ScriptTranscluder'
    settings = [
        ## FIXME: there should be some higher-level sense of
        ## tag/branch/trunk, and maybe latest too:
        Setting('spec',
                default='requirements/scripttranscluder-req.txt',
                help='Specification of packages to install'),
        Setting('port',
                default='{{env.config.getint("general", "base_port")+int(config.port_offset)}}',
                help='Port to install ScriptTranscluder on'),
        Setting('port_offset',
                default='5',
                help='Offset from base_port'),
        Setting('host',
                default='127.0.0.1',
                help='Host to serve on'),
        ]
    
    actions = [
        tasks.VirtualEnv(),
        ## FIXME: use poach-eggs?
        tasks.InstallSpec('Install ScriptTranscluder',
                          '{{config.spec}}'),
        tasks.InstallPasteConfig(path='scripttranscluder/src/scripttranscluder/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.InstallSupervisorConfig(),
        tasks.SaveURI(path='/include.js',
                      project_local=False,
                      trailing_slash=False),
        ]

    depends_on_projects = ['fassembler:topp']

class TaskTrackerProject(Project):
    """
    Install TaskTracker
    """

    name = 'tasktracker'
    title = 'Install TaskTracker'
    settings = [
        Setting('db_sqlobject',
                default='mysql://{{config.db_username}}:{{config.db_password}}@{{config.db_host}}/{{config.db_name}}',
                help='Full SQLObject connection string for database'),
        Setting('db_username',
                default='tasktracker',
                help='Database connection username'),
        Setting('db_password',
                default='tasktracker',
                help='Database connection password'),
        Setting('db_host',
                default='localhost',
                help='Host where database is running'),
        Setting('db_name',
                default='{{env.config.getdefault("general", "db_prefix", "")}}tasktracker',
                help='Name of database'),
        Setting('db_test_sqlobject',
                default='mysql://{{config.db_username}}:{{config.db_password}}@{{config.db_host}}/{{config.db_test_name}}',
                help='Full SQLObject connection string for test database'),
        Setting('db_test_name',
                default='tasktracker_test',
                help='Name of the test database'),
        Setting('db_root_password',
                default='',
                help='Database root password'),
        #Setting('tasktracker_repo',
        #        default='https://svn.openplans.org/svn/TaskTracker/trunk',
        #        help='svn location to install TaskTracker from'),
        Setting('port',
                default='{{env.config.getint("general", "base_port")+int(config.port_offset)}}',
                help='Port to install TaskTracker on'),
        Setting('port_offset',
                default='4',
                help='Offset from base_port for TaskTracker'),
        Setting('host',
                default='127.0.0.1',
                help='Host to serve on'),
        Setting('spec',
                default='requirements/tasktracker-req.txt',
                help='Specification of packages to install'),
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install TaskTracker',
                          '{{config.spec}}'),
        tasks.InstallPasteConfig(path='tasktracker/src/tasktracker/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.InstallSupervisorConfig(),
        tasks.CheckMySQLDatabase('Check database exists'),
        tasks.Script('Run setup-app',
                     ['paster', 'setup-app', '{{env.base_path}}/etc/{{project.name}}/{{project.name}}.ini#tasktracker'],
                     use_virtualenv=True,
                     cwd='{{env.base_path}}/{{project.name}}/src/{{project.name}}'),
        tasks.SaveURI(path='/tasks'),
        ]

    depends_on_projects = ['fassembler:topp']


class DeliveranceProject(Project):
    """
    Install Deliverance/DeliveranceVHoster
    """

    name = 'deliverance'
    title = 'Install Deliverance/DeliveranceVHoster'
    settings = [
        Setting('spec',
                default='requirements/deliverance-req.txt',
                help='Specification of packages to install'),
        Setting('openplans_hooks_repo',
                default='https://svn.openplans.org/svn/config/dvhoster/trunk',
                help='SVN location of openplans_hooks'),
        Setting('port',
                default='{{env.config.getint("general", "base_port")+int(config.port_offset)}}',
                help='Port to install Deliverance on'),
        Setting('port_offset',
                default='0',
                help='Offset from base_port for TaskTracker'),
        Setting('host',
                default='127.0.0.1',
                help='Host to serve on'),
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install Deliverance', '{{config.spec}}'),
        tasks.SvnCheckout('Checkout openplans_hooks',
                          '{{config.openplans_hooks_repo}}', '{{project.name}}/src/openplans_hooks'),
        tasks.InstallPasteConfig(path='deliverance/src/deliverancevhoster/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.InstallSupervisorConfig(),
        tasks.SaveURI(path='/', theme=False),
        ]

    depends_on_projects = ['fassembler:topp']
