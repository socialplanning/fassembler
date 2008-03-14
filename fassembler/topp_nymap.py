"""
builders for the nymap static files
"""

from fassembler.project import Project, Setting
from fassembler import tasks

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
#        tasks.SaveURI(path='/maps/ows',
#                      project_name='{{project.name}}_geoserver',
#                      uri='{{config.geoserver_url}}',
#                      project_local=False,
#                      theme=False),
        ]

    depends_on_projects = ['fassembler:topp']
