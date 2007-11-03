"""
Abstract base class for things that need building.

These classes should be listed as the entry point [fassembler.project]
"""
import os
import socket
from cStringIO import StringIO
from fassembler.namespace import Namespace
from fassembler.text import indent, underline, dedent

class Project(object):
    """
    This represents an abstract project.

    Subclasses should describe the project built in the docstring.

    Subclasses should also define an actions attribute, which is a list
    of tasks.
    """

    name = None
    title = None
    actions = None
    setting_defaults = {}

    def __init__(self, project_name, maker, logger, config):
        self.project_name = project_name
        self.maker = maker
        self.logger = logger
        self.config = config
        if self.name is None:
            raise NotImplementedError(
                "No name has been assigned to %r" % self)

    @property
    def config_section(self):
        return self.name

    def run(self):
        if self.actions is None:
            raise NotImplementedError(
                "The actions attribute has not been overridden in %r"
                % self)
        self.setup_config()
        self.bind_tasks()
        for task in self.actions:
            task.run()

    def bind_tasks(self):
        for task in self.actions:
            task.bind(maker=self.maker, logger=self.logger, config=self.config,
                      project=self)
            task.confirm_settings()

    def make_description(self):
        """
        Returns the description of this project, in the context of the
        settings given.
        """
        self.setup_config()
        self.bind_tasks()
        out = StringIO()
        title = self.title or self.name
        title = '%s (%s)' % (title, self.project_name)
        print >> out, underline(title)
        doc = self.__doc__
        if doc == Project.__doc__:
            doc = '[No project description set]'
        print >> out, dedent(doc)
        print >> out
        print >> out, indent(underline('Tasks', '='), '  ')
        print >> out
        for task in self.actions:
            desc = str(task)
            print >> out, indent(underline(task.title, '-'), '  ')
            print >> out, indent(desc, '  ')
            print >> out
        return out.getvalue()

    def create_namespace(self):
        ns = Namespace(self.config_section)
        ns['env'] = Environment(self.maker.base_path)
        ns['maker'] = self.maker
        ns['project'] = self
        ns['os'] = os
        ns.add_all_sections(self.config)
        ns['config'] = ns[self.config_section]
        return ns

    def setup_config(self):
        if not self.config.has_section(self.config_section):
            self.config.add_section(self.config_section)
        for name, value in self.setting_defaults.items():
            if (not self.config.has_option(self.config_section, name)
                and not self.config.has_option('DEFAULT', name)):
                self.config.set(self.config_section, name, value)

class Environment(object):

    def __init__(self, base_path):
        self.environ = os.environ
        self.base_path = base_path

    @property
    def hostname(self):
        return socket.gethostname().split('.')[0]

    @property
    def fq_hostname(self):
        return socket.gethostbyaddr(socket.gethostname())
