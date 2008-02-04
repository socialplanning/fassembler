"""
Installation of a TOPP buildbot master.
"""

import os
from fassembler import tasks
from fassembler.project import Project, Setting
interpolated = tasks.interpolated
import warnings


warnings.filterwarnings('ignore', 'tempnam is .*')


class BuildMasterProject(Project):

    """Install Buildbot master that controls our automated builds & tests.
    """

    name = 'buildmaster'
    title = 'Installs the buildbot master'
    
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

        ]

    depends_on_projects = ['fassembler:topp']
