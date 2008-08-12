"""
Misc. builders for various smaller topp products
"""

from fassembler import tasks
from fassembler.project import Project, Setting

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
                default='{{env.base_port+int(config.port_offset)}}',
                help='Port to install ScriptTranscluder on'),
        Setting('port_offset',
                default='5',
                help='Offset from base_port'),
        Setting('host',
                default='localhost',
                help='Host to serve on'),
        ]
    
    actions = [
        tasks.VirtualEnv(),
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
                default='{{env.db_root_password}}',
                help='Database root password'),
        #Setting('tasktracker_repo',
        #        default='https://svn.openplans.org/svn/TaskTracker/trunk',
        #        help='svn location to install TaskTracker from'),
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help='Port to install TaskTracker on'),
        Setting('port_offset',
                default='4',
                help='Offset from base_port for TaskTracker'),
        Setting('host',
                default='localhost',
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
                     cwd='{{env.base_path}}/{{project.name}}/src/{{project.name}}',
                     phase='setup'),
        tasks.SaveURI(path='/tasks'),
        tasks.SaveCabochonSubscriber({'delete_project' : '/projects/{id}/tasks/project/destroy'}, use_base_port=True),
        ]

    depends_on_projects = ['fassembler:topp', 'fassembler:cabochon']
    depends_on_executables = ['mysql_config']

class CabochonProject(Project):
    """
    Install Cabochon
    """
    depends_on_projects = ['fassembler:topp']

    name = 'cabochon'
    title = 'Install Cabochon'
    settings = [
        Setting('db_sqlobject',
                default='mysql://{{config.db_username}}:{{config.db_password}}@{{config.db_host}}/{{config.db_name}}',
                help='Full SQLObject connection string for database'),
        Setting('db_username',
                default='cabochon',
                help='Database connection username'),
        Setting('db_password',
                default='cabochon',
                help='Database connection password'),
        Setting('db_host',
                default='localhost',
                help='Host where database is running'),
        Setting('db_name',
                default='{{env.config.getdefault("general", "db_prefix", "")}}cabochon',
                help='Name of database'),
        Setting('db_test_sqlobject',
                default='mysql://{{config.db_username}}:{{config.db_password}}@{{config.db_host}}/{{config.db_test_name}}',
                help='Full SQLObject connection string for test database'),
        Setting('db_test_name',
                default='cabochon_test',
                help='Name of the test database'),
        Setting('db_root_password',
                default='{{env.db_root_password}}',
                help='Database root password'),
        #Setting('cabochon_repo',
        #        default='https://svn.openplans.org/svn/Cabochon/trunk',
        #        help='svn location to install Cabochon from'),
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help='Port to install Cabochon on'),
        Setting('port_offset',
                default='6',
                help='Offset from base_port for Cabochon'),
        Setting('host',
                default='localhost',
                help='Host to serve on'),
        Setting('spec',
                default='requirements/cabochon-req.txt',
                help='Specification of packages to install'),
        Setting('cabochon_user_info',
                default='{{env.var}}/cabochon-password.txt',
                help='The cabochon admin user info'),
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install Cabochon',
                          '{{config.spec}}'),
        tasks.InstallPasteConfig(path='cabochon/src/cabochon/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.InstallSupervisorConfig(),
        tasks.CheckMySQLDatabase('Check database exists'),
        tasks.Script('Run setup-app',
                     ['paster', 'setup-app', '{{env.base_path}}/etc/{{project.name}}/{{project.name}}.ini#cabochon'],
                     use_virtualenv=True,
                     cwd='{{env.base_path}}/{{project.name}}/src/{{project.name}}',
                     phase='setup'),
        tasks.EnsureFile('Write cabochon_user_info.txt if necessary', '{{config.cabochon_user_info}}',
                         'cabochon:{{env.random_string(12, "alphanumeric")}}',
                         overwrite=False),
        tasks.SaveSetting('save setting', {'cabochon_user_info':
                                           '{{config.cabochon_user_info}}'}),
        tasks.SaveURI(path='/', public=False),
        ]

    depends_on_projects = ['fassembler:topp']
    depends_on_executables = ['mysql_config']


class TwirlipProject(Project):
    """
    Install Twirlip
    """

    depends_on_projects = ['fassembler:topp']

    name = 'twirlip'
    title = 'Install Twirlip'
    settings = [
        Setting('db_sqlobject',
                default='mysql://{{config.db_username}}:{{config.db_password}}@{{config.db_host}}/{{config.db_name}}',
                help='Full SQLObject connection string for database'),
        Setting('db_username',
                default='twirlip',
                help='Database connection username'),
        Setting('db_password',
                default='twirlip',
                help='Database connection password'),
        Setting('db_host',
                default='localhost',
                help='Host where database is running'),
        Setting('db_name',
                default='{{env.config.getdefault("general", "db_prefix", "")}}twirlip',
                help='Name of database'),
        Setting('db_test_sqlobject',
                default='mysql://{{config.db_username}}:{{config.db_password}}@{{config.db_host}}/{{config.db_test_name}}',
                help='Full SQLObject connection string for test database'),
        Setting('db_test_name',
                default='twirlip_test',
                help='Name of the test database'),
        Setting('db_root_password',
                default='{{env.db_root_password}}',
                help='Database root password'),
        #Setting('twirlip_repo',
        #        default='https://svn.openplans.org/svn/Twirlip/trunk',
        #        help='svn location to install Twirlip from'),
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help='Port to install Twirlip on'),
        Setting('port_offset',
                default='7',
                help='Offset from base_port for Twirlip'),
        Setting('host',
                default='localhost',
                help='Host to serve on'),
        Setting('spec',
                default='requirements/twirlip-req.txt',
                help='Specification of packages to install'),
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install Twirlip',
                          '{{config.spec}}'),
        tasks.InstallPasteConfig(path='twirlip/src/twirlip/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.InstallSupervisorConfig(),
        tasks.CheckMySQLDatabase('Check database exists'),
        tasks.Script('Run setup-app',
                     ['paster', 'setup-app', '{{env.base_path}}/etc/{{project.name}}/{{project.name}}.ini#main_app'],
                     use_virtualenv=True,
                     cwd='{{env.base_path}}/{{project.name}}/src/{{project.name}}',
                     phase='setup'),
        tasks.SaveURI(path='/notification',
                      project_local=False,
                      theme=False),
        tasks.SaveCabochonSubscriber({'create_page' : '/page/create',
                                      'edit_page' : '/page/edit',
                                      'delete_page' : '/page/delete',
                                      'email_changed' : '/page/email_changed'}),
        
        ]

    depends_on_projects = ['fassembler:topp']
    depends_on_executables = ['mysql_config']


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
                default='https://svn.openplans.org/svn/build/openplans_hooks/trunk',
                help='SVN location of openplans_hooks'),
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help='Port to install Deliverance on'),
        Setting('port_offset',
                default='0',
                help='Offset from base_port for Deliverance'),
        Setting('host',
                default='localhost',
                help='Host to serve on'),
        Setting('force_ssl',
                inherit_config=('general', 'force_ssl'),
                default='False',
                help='Redirect ssl-only paths to https'),
        Setting('default_rules_repo',
                default='{{project.req_settings.get("rules_repo", "https://svn.openplans.org/svn/build/rules/openplans")}}',
                help='Default svn location of deliverance rules',
                )
        ]

    actions = [
        tasks.SaveSetting('Save force_ssl setting',
                          {'force_ssl': '{{config.force_ssl}}'}),
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install Deliverance', '{{config.spec}}'),
        tasks.TestLxml('{{env.base_path}}/deliverance'),
        tasks.SvnCheckout('Checkout openplans_hooks',
                          '{{config.openplans_hooks_repo}}', '{{project.name}}/src/openplans_hooks'),
        tasks.SvnCheckout('Checkout default rules',
                          '{{config.default_rules_repo}}',
                          '{{env.var}}/deliverance/default_rules'),
        tasks.InstallPasteConfig(path='deliverance/src/deliverancevhoster/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.InstallSupervisorConfig(),
        tasks.SaveURI(path='/', theme=False),
        ]

    depends_on_projects = ['fassembler:topp']



class RelateMeProject(Project):
    """
    Install RelateMe
    """

    name = 'relateme'
    title = 'Install RelateMe'
    settings = [
        Setting('db_host',
                default='localhost',
                help='Host where database is running'),
        Setting('db_streetsblog_username',
                default='streetsblog',
                help='Database connection username'),
        Setting('db_streetsblog_password',
                default='sblog',
                help='Database connection password'),
        Setting('db_streetsblog_name',
                default='streetsblog',
                help='Name of database'),
        Setting('db_streetfilms_username',
                default='sfilms',
                help='Database connection username'),
        Setting('db_streetfilms_password',
                default='sfilms',
                help='Database connection password'),
        Setting('db_streetfilms_name',
                default='sfilms',
                help='Name of database'),
        Setting('db_root_password',
                default='{{env.db_root_password}}',
                help='Database root password'),
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help='Port to install RelateMe on'),
        Setting('port_offset',
                default='9',
                help='Offset from base_port for RelateMe'),
        Setting('host',
                default='localhost',
                help='Host to serve on'),
        Setting('spec',
                default='requirements/relateme-req.txt',
                help='Specification of packages to install'),
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install RelateMe',
                          '{{config.spec}}'),
        tasks.InstallPasteConfig(path='relateme/src/relateme/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.InstallSupervisorConfig(),
        ## RelateMe uses the WordPress database, so it doesn't control anything:
        #tasks.CheckMySQLDatabase('Check database exists'),
        #tasks.Script('Run setup-app',
        #             ['paster', 'setup-app', '{{env.base_path}}/etc/{{project.name}}/{{project.name}}.ini#relateme'],
        #             use_virtualenv=True,
        #             cwd='{{env.base_path}}/{{project.name}}/src/{{project.name}}'),
        ## Currently we are not using Deliverance, so this is kind of redundant:
        #tasks.SaveURI(path='/api/relateme'),
        ]

    depends_on_projects = ['fassembler:topp']
    depends_on_executables = ['mysql_config']
