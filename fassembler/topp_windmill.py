"""
Builder for windmill install
"""

from fassembler import tasks
from fassembler.project import Project
from fassembler.project import Setting

class WindmillProject(Project):
    """
    Install Windmill
    """
    
    name = 'windmill'
    title = 'Install Windmill'

    settings = [
        Setting('spec',
                default='requirements/windmill-req.txt',
                help='Specification of packages to install'),
        ]

    actions = [
        tasks.VirtualEnv(different_python='python2.5'),
        tasks.InstallSpec('Install windmill and other dependencies',
                          '{{config.spec}}'),
        ]

    depends_on_projects = ['fassembler:topp']
