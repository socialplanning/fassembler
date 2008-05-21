"""
Represents a substitution namespace for templates.
"""

from UserDict import DictMixin
from tempita import Template
from cmdutils import CommandError
import sys
from fassembler.util import asbool
from fassembler.text import indent, underline, dedent

_in_broken_ns = False

class Namespace(DictMixin):
    """
    Represents a namespace that templates are executed in.

    ``self.dict`` contains the concrete dictionary object to use for
    interpretation.  ``exec`` (and ``eval`` etc) can only work with
    actual dictionaries.  This object acts *like* a dictionary as
    well, but more lazily.

    This can handle config files and config sections with recursive
    interpolation.
    """

    # Always available in templates:
    builtins = {
        'asbool': asbool,
        'indent': indent,
        'underline': underline,
        'dedent': dedent,
        }

    ## FIXME: probably this should have access to the maker, for
    ## error handling.
    def __init__(self, name=None):
        self.name = name
        self.dict = {}
        if name:
            self.dict['__name__'] = self.name
        self.dict.update(self.builtins)

    ## All the UserDict abstract methods:

    def __getitem__(self, key):
        return self.dict[key]

    def keys(self):
        return self.dict.keys()

    def __setitem__(self, key, value):
        self.dict[key] = value

    def __delitem__(self, key):
        del self.dict[key]

    def add_section(self, config, section, variable=None):
        """
        Add a section from the given ConfigParser-like object ``config``.

        This will show up as a variable named after ``section`` (or
        the name in ``variable`` if given).  The values in the config
        will be interpolated in this namespace.
        """
        if self.name:
            subname = '%s.%s' % (self.name, section)
        else:
            subname = section
        ns = SectionNamespace(self, config, section, name=subname)
        self.dict[variable or section] = ns

    def add_all_sections(self, config):
        """
        Add all sections from a configuration file.
        """
        for section in config.sections():
            self.add_section(config, section)

    def interpolate(self_, string, stacklevel=1, name=None, self=None):
        """
        Interpolate a string.

        You can provide temporary ``self`` object with that keyword
        argument.

        This handles exceptions internally.

        The variable ``name`` is used to name the string.  Alternately
        it can look up ``stacklevel`` frames to find the location
        where the literal ``string`` is given (for error reports).
        """
        ## FIXME: maybe I should actually use "self" somewhere?
        if name is None:
            name = self_.name
            if stacklevel:
                try:
                    caller = sys._getframe(stacklevel)
                except ValueError:
                    pass
                else:
                    name = caller.f_globals.get('__name__') or name
        tmpl = Template(string, name=name)
        try:
            old_self = None
            if self is not None:
                old_self = self_.dict.get('self')
                self_.dict['self'] = self
            return tmpl.substitute(self_.dict)
        finally:
            if old_self is not None:
                self_.dict['self'] = old_self
            elif 'self' in self_.dict:
                del self_.dict['self']

    def string_repr(self, detail=0):
        """
        The string representation of this namespace.
        """
        lines = []
        if self.name:
            lines.append('Namespace %s:' % self.name)
        else:
            lines.append('Namespace:')
        namespaces = []
        keys = []
        for key in sorted(self.keys()):
            value = self[key]
            if isinstance(value, SectionNamespace):
                namespaces.append((key, value))
            else:
                keys.append((key, value))
        for key, value in keys:
            if key in __builtins__ or key == '__builtins__':
                continue
            lines.append('%s: %s' % (key, self._quote(value)))
        if namespaces:
            lines.append('== Sections: ==')
            for key, value in namespaces:
                lines.append('%s:' % key)
                sublines = value.string_repr(detail).splitlines()
                for subline in sublines:
                    lines.append('  %s' % subline)
        return '\n'.join(lines)

    def _quote(self, value):
        try:
            value = str(value)
        except Exception, e:
            try:
                return 'Error doing str(%r): %s' % (value, e)
            except Exception, e:
                return 'Error doing repr(value): %s' % e
        else:
            if len(value) > 100:
                return value[:60]+'...'+value[-20:]

    def __str__(self):
        return self.string_repr()

    def execute_template(self, tmpl):
        """
        Executes the given template in this namespace.  Does error handling.
        """
        global _in_broken_ns
        try:
            return tmpl.substitute(self.dict)
        except KeyboardInterrupt:
            raise
        except:
            if not self['maker'].interactive:
                # If nobody's at the keyboard, errors must be fatal.
                raise
            if _in_broken_ns:
                # Hitting this recursively while already handling another error
                raise
            _in_broken_ns = True
            try:
                import traceback
                try:
                    # Enable nicer raw_input:
                    import readline
                except ImportError:
                    pass
                exc_info = sys.exc_info()
                print "Error: %s" % exc_info[1]
                template_content = tmpl.content
                if len(template_content) < 80 and len(template_content.strip().splitlines()) == 1:
                    print 'Template: %s' % template_content
                while 1:
                    ## FIXME: should beep here
                    response = raw_input('What to do? [(c)ancel/(q)uit/(r)etry/(s)how source/(n)amespace/(t)raceback/(p)db/(e)xecute/(r)etry/] ')
                    if not response.strip():
                        continue
                    char = response.strip().lower()[0]
                    if char == 'c':
                        break
                    elif char == 'q':
                        raise CommandError('Aborted', show_usage=False)
                    elif char == 's':
                        print 'Template:'
                        print template_content
                    elif char == 'n':
                        print 'Namespace:'
                        try:
                            print self
                        except KeyboardInterrupt:
                            raise
                        except:
                            # This shouldn't really happen
                            print 'Error printing self:', sys.exc_info()[1]
                            traceback.print_exc()
                    elif char == 't':
                        traceback.print_exception(*exc_info)
                    elif char == 'p':
                        import pdb
                        pdb.set_trace()
                    else:
                        print 'Invalid input: %r' % char
                raise
            finally:
                _in_broken_ns = False

class SectionNamespace(DictMixin):
    """
    Represents a section in a config object, where all values are
    recursively interpolated by the namespace object ``self.ns``

    If you use dictionary methods, the uninterpolated values are
    given.  Attributes are interpolated.  Thus if you get
    ``section.foo`` the value of ``foo`` is interpolated.  If you get
    ``section['foo']`` it is not interpolated.
    """

    def __init__(self, ns, config, section, name=None):
        self.ns = ns
        self.config = config
        self.section = section
        self.name = name

    def __getitem__(self, key):
        if self.config.has_option(self.section, key):
            return self.config.get(self.section, key)
        elif key in self.config.defaults():
            return self.config.defaults()[key]
        else:
            raise KeyError(key)

    def __setitem__(self, key, value):
        self.config.set(self.section, key, value)

    def __delitem__(self, key):
        ## FIXME: not sure how to handle globals; they shouldn't be
        ## deletable though.
        self.config.remove_option(self.section, key)

    def keys(self):
        return self.config.options(self.section)

    def __contains__(self, key):
        return (self.config.has_option(self.section, key)
                or key in self.config.defaults())

    def __repr__(self):
        return '<%s around %r section [%s]>' % (
            self.__class__.__name__, self.cp, self.section)

    def __getattr__(self, key):
        if key not in self:
            raise AttributeError(key)
        value = self[key]
        if isinstance(value, basestring):
            value = self.ns.interpolate(value, name=self.name, self=self)
        return value

    def string_repr(self, detail=0):
        """
        The string representation of this object, for human consumption and debugging.
        """
        lines = ['Section: [%s]' % self.section]
        options = sorted(self.config.options(self.section))
        for option in options:
            raw = self.config.get(self.section, option)
            lines.append('%s = %s' % (option, raw))
            try:
                interpolated = self.ns.interpolate(raw, name=self.name, self=self)
            except KeyboardInterrupt:
                raise
            except Exception, e:
                interpolated = 'Error evaluating: %s' % e
            if interpolated != raw:
                lines.append('  %s' % interpolated)
        return '\n'.join(lines)
