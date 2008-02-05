"""
Installation of a TOPP buildbot master.
"""

import os
from fassembler import tasks
from fassembler.project import Project, Setting
interpolated = tasks.interpolated

twisted_dirname = 'Twisted-2.5.0'
tarball_url = 'http://tmrc.mit.edu/mirror/twisted/Twisted/2.5/%s.tar.bz2' % twisted_dirname


class GetTwistedSource(tasks.InstallTarball):

    # easy_install twisted isn't possible, see
    # http://twistedmatrix.com/trac/ticket/1286
    # so we install from a tarball.
    
    _tarball_url = tarball_url
    _src_name = twisted_dirname
    _marker = interpolated('_marker')

    def __init__(self, stacklevel=1):
        super(GetTwistedSource, self).__init__(stacklevel=stacklevel+1)
        self._marker = '{{os.path.join(task.dest_path, ".marker")}}'

    def post_unpack_hook(self):
        # This is just a marker file to show for future runs that we
        # successfully downloaded and unpacked the tarball.
        open(self._marker, 'w').write('')

    def is_up_to_date(self):
        return os.path.exists(self._marker)


class BuildMasterProject(Project):

    """Install Buildbot master that controls our automated builds & tests.
    """

    name = 'buildmaster'
    title = 'Installs the buildbot master'
    _twisted_src = twisted_dirname

    files_dir = os.path.join(os.path.dirname(__file__), 'buildbot-files')
    skel_dir = os.path.join(files_dir, 'skel')

    settings = [
        Setting('spec',
                default='requirements/buildbot-req.txt',
                help='Specification of packages to install'),
        Setting('host',
                default='localhost',
                help='Host to serve on'),
        # XXX put port offsets & calculated ports here.
        # See docs/ports.txt
        ]
    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install buildbot dependencies',
                          '{{config.spec}}'),
        GetTwistedSource(),
        tasks.Script('Install Twisted', ['python', 'setup.py', 'install'],
                     use_virtualenv=True,
                     cwd='{{env.base_path}}/{{project.name}}/src/{{project._twisted_src}}'
                     ),
        # XXX This fails about half the time, because sourceforge sucks.
        # Just re-run until it works.
        tasks.EasyInstall('Install buildbot', 'buildbot>=0.7.6')
        ]

    depends_on_projects = ['fassembler:topp']
