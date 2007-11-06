"""
Misc. builders for various topp products
"""
from fassembler.project import Project, Setting
from fassembler import tasks
from tempita import Template


scripttranscluder_config_template = Template("""\
[app:main]
use = egg:ScriptTranscluder
allow_hosts = *.openplans.org

[server:main]
use = egg:Paste#http
host = {{config.scripttranscluder_serve_host}}
port = {{config.scripttranscluder_port}}
""", stacklevel=1)

class ScriptTranscluderProject(Project):
    """
    Install ScriptTranscluder
    """
    
    name = 'scripttranscluder'
    title = 'Install ScriptTranscluder'
    settings = [
        ## FIXME: there should be some higher-level sense of
        ## tag/branch/trunk, and maybe latest too:
        Setting('scripttranscluder_repo',
                default='https://svn.openplans.org/svn/ScriptTranscluder/trunk',
                help='svn repository for ScriptTranscluder'),
        Setting('scripttranscluder_port',
                default='FIXME',
                help='Port to install ScriptTranscluder on'),
        Setting('scripttranscluder_serve_host',
                default='127.0.0.1',
                help='Host to serve on'),
        ]
    
    actions = [
        tasks.VirtualEnv(),
        ## FIXME: use poach-eggs?
        tasks.SourceInstall('Check out and install ScriptTranscluder',
                            '{{config.scripttranscluder_repo}}', 'scripttranscluder'),
        tasks.EasyInstall('Install PasteScript', 'PasteScript'),
        tasks.InstallPasteConfig(scripttranscluder_config_template),
        tasks.InstallPasteStartup(),
        ]


tasktracker_config_template = Template("""\
[app:main]
use = egg:TaskTracker

[server:main]
use = egg:Paste#http
host = {{config.tasktracker_serve_host}}
port = {{config.tasktracker_port}}
""", stacklevel=1)

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
                default='tasktracker',
                help='Name of database'),
        Setting('db_test_sqlobject',
                default='mysql://{{config.db_username}}:{{config.db_password}}@{{config.db_host}}/{{config.db_test_name}}',
                help='Full SQLObject connection string for test database'),
        Setting('db_test_name',
                default='tasktracker_test',
                help='Name of the test database'),
        Setting('db_root_password',
                default=None,
                help='Database root password'),
        Setting('tasktracker_repo',
                default='https://svn.openplans.org/svn/TaskTracker/trunk',
                help='svn location to install TaskTracker from'),
        ## FIXME: should these just be port/host?
        Setting('tasktracker_port',
                default='FIXME',
                help='Port to install TaskTracker on'),
        Setting('tasktracker_serve_host',
                default='127.0.0.1',
                help='Host to serve on'),
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.SourceInstall('Check out and install TaskTracker',
                            '{{config.tasktracker_repo}}', 'tasktracker'),
        ## FIXME: Not sure if I need this:
        tasks.EasyInstall('Install PasteScript', 'PasteScript'),
        tasks.InstallPasteConfig(path='tasktracker/src/tasktracker/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.CheckMySQLDatabase('Check database exists'),
        tasks.Script('Run setup-app',
                     ['paster', 'setup-app', '{{env.base_path}}/etc/{{project.name}}/{{project.name}}.ini'],
                     use_virtualenv=True,
                     cwd='{{env.base_path}}/{{project.name}}/src/{{project.name}}'),
        ]

