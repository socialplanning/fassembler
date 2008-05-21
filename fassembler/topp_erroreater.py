"""
Installation for ErrorEater, both the app and the Supervisor listener
"""
from fassembler.project import Project, Setting
from fassembler import tasks
from tempita import Template

class ErrorEaterProject(Project):
    """
    Install ErrorEater
    """

    name = 'erroreater'
    title = 'Install ErrorEater'
    settings = [
        Setting('spec',
                default='requirements/erroreater-req.txt',
                help='Specification of packages to install'),
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help='Port to install ErrorEater on'),
        Setting('port_offset',
                default='8',
                help='Offset from base_port'),
        Setting('host',
                default='localhost',
                help='Host to serve on'),
        ]

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install ErrorEater',
                          '{{config.spec}}'),
        tasks.InstallPasteConfig(path='erroreater/src/erroreater/fassembler_config.ini_tmpl'),
        tasks.InstallPasteStartup(),
        tasks.InstallSupervisorConfig(),
        tasks.SaveURI(path='/.debug/errors',
                      project_local=False,
                      theme=False),
        tasks.Script('Run setup-app',
                     ['paster', 'setup-app', '{{env.base_path}}/etc/{{project.name}}/{{project.name}}.ini#main-app'],
                     use_virtualenv=True,
                     cwd='{{env.base_path}}/{{project.name}}/src/{{project.name}}'),
        ]

    ## FIXME: and the listener
    depends_on_projects = ['fassembler:topp']

errorlistener_template = Template("""\
[eventlistener:errorlistener]
command = {{env.base_path}}/errorlistener/bin/supervisor-error-listener --queue-dir={{env.var}}/errorlistener/queue --http-config='{{env.base_path}}/etc/build.ini applications erroreater uri +/errors/add-error'
# We handle our own queuing and threading, so we don't need multiple
# listeners:
numprocs = 1
events = PROCESS_COMMUNICATION
stderr_logfile = {{env.var}}/logs/{{project.name}}/{{project.name}}-supervisor.log
stderr_logfile_maxbytes = 1MB
stderr_logfile_backups = 10
#redirect_stderr = true
""")

class ErrorListenerProject(Project):
    """
    Install SupervisorErrorListener
    """

    name = 'errorlistener'
    title = 'Install error listener'
    settings = [
        Setting('spec',
                default='requirements/errorlistener-req.txt',
                help='Specification of packages to install'),
        ]
    
    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install SupervisorErrorListener',
                          '{{config.spec}}'),
        tasks.EnsureFile('Install supervisor listener config',
                         '{{env.base_path}}/etc/supervisor.d/errorlistener.ini',
                         content=errorlistener_template),
        tasks.EnsureDir('Create log directory',
                        '{{env.var}}/logs/errorlistener'),
        ]

    depends_on_projects = ['fassembler:topp', 'fassembler:supervisor', 'fassembler:erroreater']
    
