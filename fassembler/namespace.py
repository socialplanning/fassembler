from UserDict import DictMixin
from tempita import Template
from cmdutils import CommandError
import sys

class Namespace(DictMixin):
    def __init__(self, name=None):
        self.name = name
        self.dict = {}
        if name:
            self.dict['__name__'] = self.name

    def __getitem__(self, key):
        return self.dict[key]

    def keys(self):
        return self.dict.keys()

    def __setitem__(self, key, value):
        self.dict[key] = value

    def __delitem__(self, key):
        del self.dict[key]

    def add_section(self, config, section, variable=None):
        if self.name:
            subname = '%s.%s' % (self.name, section)
        else:
            subname = section
        ns = SectionNamespace(self, config, section, name=subname)
        self.dict[variable or section] = ns

    def add_all_sections(self, config):
        for section in config.sections():
            self.add_section(config, section)

    def interpolate(self_, string, stacklevel=1, name=None, self=None):
        """
        Interpolate a string.
        """
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
        return value

    def __str__(self):
        return self.string_repr()

    def execute_template(self, tmpl):
        try:
            return tmpl.substitute(self.dict)
        except:
            import traceback
            try:
                # Enable nicer raw_input:
                import readline
            except ImportError:
                pass
            exc_info = sys.exc_info()
            print "Error: %s" % exc_info[1]
            print "Namespace:"
            print self
            retry = False
            while 1:
                response = raw_input('What to do? [(c)ancel/(t)raceback/(p)db/(e)xecute/(r)etry/(q)uit] ')
                if not response.strip():
                    continue
                char = response.strip().lower()[0]
                if char == 'c':
                    break
                elif char == 'q':
                    raise CommandError('Aborted')
                elif char == 't':
                    traceback.print_exception(*exc_info)
                elif char == 'p':
                    import pdb
                    pdb.set_trace()
                elif char == 'e':
                    expr = response[1:].strip()
                    if not expr:
                        print 'Use "e express_to_execute"'
                        continue
                    try:
                        exec compile(expr, '<e>', "single") in self.dict
                    except:
                        print 'Error in expression %s:' % expr
                        traceback.print_exc()
                elif char == 'r':
                    retry = True
                    break
                else:
                    print 'Invalid input: %r' % char
            if retry:
                return self.execute_template(tmpl)
            raise

class SectionNamespace(DictMixin):

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
        lines = ['Section: [%s]' % self.section]
        options = sorted(self.config.options(self.section))
        for option in options:
            raw = self.config.get(self.section, option)
            lines.append('%s = %s' % (option, raw))
            try:
                interpolated = self.ns.interpolate(raw, name=self.name, self=self)
            except Exception, e:
                interpolated = 'Error evaluating: %s' % e
            if interpolated != raw:
                lines.append('  %s' % interpolated)
        return '\n'.join(lines)
