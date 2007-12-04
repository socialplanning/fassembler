"""
Abstract base class for things that need building.

These classes should be listed as the entry point [fassembler.project]
"""
import os
import sys
from cStringIO import StringIO
from fassembler.namespace import Namespace
from fassembler.text import indent, underline, dedent
from cmdutils import CommandError
from tempita import Template

class Project(object):
    """
    This represents an abstract project.

    Subclasses should describe the project built in the docstring,
    and/or the title attribute.

    Subclasses should also define an actions attribute, which is a
    list of tasks, and a settings attribute, which is a list of
    Setting instances.
    """

    name = None
    title = None
    actions = None
    settings = []

    def __init__(self, project_name, maker, environ, logger, config):
        self.project_name = project_name
        self.maker = maker
        self.environ = environ
        self.logger = logger
        self.config = config
        if self.name is None:
            raise NotImplementedError(
                "No name has been assigned to %r" % self)
        self.build_properties = {}

    @property
    def config_section(self):
        """
        The section that should be used to find settings for this project.
        """
        return self.name

    def confirm_settings(self):
        """
        This is run to confirm that all the required settings have
        been set, for this project and all its tasks.
        """
        errors = []
        try:
            self.setup_config()
        except ValueError, e:
            errors.append(e)
        return errors

    def run(self):
        """
        Actually run the project.  Subclasses seldom override this;
        this runs all the tasks given in ``self.actions``
        """
        if self.actions is None:
            raise NotImplementedError(
                "The actions attribute has not been overridden in %r"
                % self)
        self.setup_config()
        self.bind_tasks()
        for task in self.actions:
            self.logger.set_section(self.name+'.'+task.name)
            self.logger.notify('== %s ==' % task.name, color='bold green')
            self.logger.indent += 2
            try:
                try:
                    task.run()
                finally:
                    self.logger.indent -= 2
            except (KeyboardInterrupt, CommandError):
                raise
            except:
                should_continue = self.maker.handle_exception(sys.exc_info(), can_continue=True)
                if not should_continue:
                    self.logger.fatal('Project %s aborted.' % self.title, color='red')
                    raise CommandError('Aborted', show_usage=False)

    def bind_tasks(self):
        """
        Bind all the task instances to the context in which they will
        be run (with this project, the maker, etc).
        """
        for task in self.actions:
            task.bind(maker=self.maker, environ=self.environ,
                      logger=self.logger, config=self.config,
                      project=self)
            task.confirm_settings()
            task.setup_build_properties()

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
        print >> out, indent(underline('Settings', '='), '  ')
        ns = self.create_namespace()
        if not self.settings:
            print >> out, indent('No settings', '    ')
        else:
            for setting in self.settings:
                try:
                    setting_value = getattr(ns['config'], setting.name)
                except Exception, e:
                    setting_value = 'Cannot calculate value: %s %s' % (e.__class__.__name__, e)
                print >> out, indent(setting.description(value=setting_value), '    ')
        print >> out
        print >> out, indent(underline('Tasks', '='), '  ')
        for task in self.actions:
            desc = str(task)
            print >> out, indent(underline(task.title, '-'), '    ')
            print >> out, indent(desc, '    ')
            print >> out
        return out.getvalue()

    def interpolate(self, string, stacklevel=1, name=None):
        """
        Interpolate a string in the context of the project namespace.
        """
        return self.interpolate_ns(string, self.create_namespace(), stacklevel=stacklevel+1, name=name)

    def interpolate_ns(self, string, ns, stacklevel=1, name=None):
        """
        Interpolate a string in the given namespace.
        """
        if string is None:
            return None
        if isinstance(string, (list, tuple)):
            new_items = []
            for item in string:
                new_items.append(self.interpolate_ns(item, ns, stacklevel+1, name=name))
            return new_items
        if isinstance(string, dict):
            new_dict = {}
            for key in string:
                new_dict[self.interpolate_ns(key, ns, stacklevel+1, name=name)] = self.interpolate_ns(
                    string[key], ns, stacklevel+1, name=name)
            return new_dict
        if not isinstance(string, Template):
            tmpl = Template(string, name=name, stacklevel=stacklevel+1)
        else:
            tmpl = string
        return ns.execute_template(tmpl)

    def create_namespace(self):
        """
        Create a namespace for this object.

        Each call returns a new namespace.  This namespace can be
        further augmented (as it is by tasks).
        """
        ns = Namespace(self.config_section)
        ns['env'] = self.environ
        ns['maker'] = self.maker
        ns['project'] = self
        ns['os'] = os
        ns.add_all_sections(self.config)
        ns['config'] = ns[self.config_section]
        return ns

    def setup_config(self):
        """
        This sets all the configuration values, using defaults when
        necessary, or a value from the global configuration.
        """
        if not self.config.has_section(self.config_section):
            self.config.add_section(self.config_section)
        for setting in self.settings:
            if (not self.config.has_option(self.config_section, setting.name)
                and not self.config.has_option('DEFAULT', setting.name)):
                if not setting.has_default(self.environ):
                    raise ValueError(
                        "The setting [%s] %s (%s) must be set.  Use \"%s=VALUE\" on the command-line to set it"
                        % (self.config_section, setting.name, setting.help, setting.name))
                self.config.set(self.config_section, setting.name, setting.get_default(self.environ))

class Setting(object):
    """
    Instances of Setting describe one setting a project takes.

    Settings each have a name, and should have help.  They may have a
    default value; if none is given then the setting must be set by
    the user.

    If ``inherit_config`` is given with a value like
    ``('section_name', 'config_name')``, then the setting will inherit
    from that value in the global config if it is not given explicitly.
    """

    class _NoDefault(object):
        def __repr__(self):
            return '(no default)'
    NoDefault = _NoDefault()
    del _NoDefault

    def __init__(self, name, default=NoDefault, help=None, inherit_config=None):
        self.name = name
        self.default = default
        self.help = help
        self.inherit_config = inherit_config

    def has_default(self, environ):
        """
        Is there a default for this setting, given the environment and
        its global configuration?
        """
        if self.default is not self.NoDefault:
            return True
        if self.inherit_config is not None:
            if environ.config.has_option(*self.inherit_config):
                return True
        return False

    def get_default(self, environ):
        """
        Find the default value for this setting, given the environment
        and its global configuration.
        """
        if self.inherit_config and environ.config.has_option(*self.inherit_config):
            return environ.config.get(*self.inherit_config)
        if self.default is not self.NoDefault:
            return self.default
        assert 0, 'no default'

    def __str__(self):
        return self.description(value=self.default)
        
    def description(self, value=None):
        msg = '%s:' % self.name
        msg += '\n  Default: %s' % self.description_repr(self.default)
        if value != self.default:
            msg += '\n  Value:   %s' % self.description_repr(value)
        if self.help:
            msg += '\n'+indent(self.help, '    ')
        return msg
        
    def description_repr(self, value):
        if isinstance(value, basestring):
            if value == '':
                return "''"
            if value.strip() != value or value.strip('"\'') != value:
                return repr(value)
            if isinstance(value, unicode):
                value = value.encode('unicode_escape')
            else:
                value = value.encode('string_escape')
            return value
        return repr(value)
            
