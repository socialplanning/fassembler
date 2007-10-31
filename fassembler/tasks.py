class Task(object):
    """
    Abstract base class for tasks
    """

    maker = None

    def __init__(self, anme):
        self.name = name

    def bind(self, maker, logger, config, project):
        self.maker = maker
        self.logger = logger
        self.config = config
        self.project = project

    def confirm_settings(self):
        # Quick test that bind has been called
        assert self.maker is not None

    def run(self):
        raise NotImplementedError
