"""
Misc. builders for various topp products
"""
from fassembler.project import Project, Setting
from fassembler import tasks
from tempita import Template


script_config_template = Template("""\
[app:main]
use = egg:ScriptTranscluder
allow_hosts = *.openplans.org

[server:main]
use = egg:Paste#http
host = {{config.script_transcluder_serve_host}}
port = {{config.script_transcluder_port}}
""", stacklevel=1)

class ScriptTranscluder(Project):
    """
    Install ScriptTranscluder
    """
    
    name = 'scripttranscluder'
    title = 'Install ScriptTranscluder'
    settings = [
        Setting('script_transcluder_req',
                default='ScriptTranscluder',
                help='Requirement for installing ScriptTranscluder'),
        Setting('script_transcluder_port',
                default='xxx',
                help='Port to install ScriptTranscluder on'),
        Setting('script_transcluder_serve_host',
                default='127.0.0.1',
                help='Host to serve on'),
        ]
    
    actions = [
        tasks.VirtualEnv(),
        ## FIXME: use poach-eggs:
        tasks.EasyInstall('Install ScriptTranscluder', '{{config.script_transcluder_req}}',
                          'PasteScript', find_links='https://svn.openplans.org/svn/ScriptTranscluder/trunk#egg=ScriptTranscluder-dev'),
        tasks.InstallPasteConfig(script_config_template),
        tasks.InstallPasteStartup(),
        ]
