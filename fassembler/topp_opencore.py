from fassembler.project import Project, Setting
from fassembler import tasks
from tempita import Template

class OpenCoreProject(Project):
    """
    Install OpenCore
    """

    name = 'opencore'
    title = 'Install OpenCore'

    actions = [
        tasks.VirtualEnv(),
        # Other stuff here
        ]
