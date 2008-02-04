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

    blah
    
class InstallBuildbot(tasks.Task):

    description = """
    Install Buildbot master into {{task.dest_path}}.
    """
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
