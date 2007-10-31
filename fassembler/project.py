"""
Abstract base class for things that need building.

These classes should be listed as the entry point [fassembler.project]
"""

class Project(object):
    """
    This represents an abstract project.

    Subclasses should describe the project built in the docstring.

    Subclasses should also define a tasks attribute, which is a list
    of tasks.
    """

    name = None
    tasks = None

    def __init__(self, maker, logger, config):
        self.maker = maker
        self.config = config
        if self.name is None:
            raise NotImplementedError(
                "No name has been assigned to %r" % self)

    def run(self):
        if self.tasks is None:
            raise NotImplementedError(
                "The tasks attribute has not been overridden in %r"
                % self)
        for task in self.tasks:
            task.bind(maker=self.maker, logger=self.logger, config=self.config,
                      project=self)
            task.confirm_settings()
        for task in self.tasks:
            task.run()

    
