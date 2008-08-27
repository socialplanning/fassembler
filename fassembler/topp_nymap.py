"""
builders for the nymap static files
"""

from fassembler.project import Project, Setting
from fassembler import tasks
from fassembler.apache import ApacheMixin
import os

class NYMapProject(Project):
    """
    Install NYMap
    """
    
    name = 'nymap'
    title = 'Install NYMap'
    settings = [
        Setting('svn',
                default='http://svn.opengeo.org/vespucci/branches/woonerf/',
                help='Location of nymap svn repository'),
#        Setting('geoserver_url',
#                default='http://artois.openplans.org/geoserver/ows/',
#                help='Location where GeoServer is running'),
        ]
    
    actions = [
        tasks.SvnCheckout(
            'Checkout nymap',
            repository='{{config.svn}}',
            dest='{{env.base_path}}/{{project.name}}/src/nymap'),
        tasks.Script(
            'Run build script',
            ['./build', '-f'],
            cwd='{{env.base_path}}/{{project.name}}/src/nymap/build'),
        tasks.SaveURI(path='/maps',
                      uri='file://{{env.base_path}}/{{project.name}}/src/nymap',
                      project_local=False,
                      ## FIXME: this should be themable, but currently
                      ## is not (see #2172):
                      theme=False,
                      ),
        ]

    depends_on_projects = ['fassembler:topp']

class ProxyProject(Project, ApacheMixin):
    """
    Install Proxy
    """
    
    name = 'proxy'
    title = 'Install Proxy'

    settings = [
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help="Port to install Apache (for proxy) on"),
        Setting('port_offset',
                default='11',
                help='Offset from base_port for Apache (for proxy)'),
        Setting('host',
                default='localhost',
                help='Interface/host to serve Apache/WordPress on'),
        Setting('apache_exec',
                default='{{project.apache_exec()}}',
                help='Location of apache executable'),
        Setting('apache_module_dir',
                default='{{project.apache_module_dir()}}',
                help='Location of apache modules'),
        Setting('php_cgi_exec',
                default='{{project.php_cgi_exec()}}',
                help='Location of php cgi executable'),
        Setting('server_admin',
                default='{{env.environ["USER"]}}@{{env.fq_hostname}}',
                help='Server admin for Apache'),
        ]

    skel_dir = os.path.join(os.path.dirname(__file__), 'proxy-files', 'skel')
        
    actions = [
        #proxy stuff
        tasks.CopyDir('Create layout',
                      skel_dir, './'),

        tasks.InstallSupervisorConfig(),
        tasks.SaveURI(path='/proxy', project_local=False),
    ]

    depends_on_projects = ['fassembler:topp']
    
