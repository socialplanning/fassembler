from UserDict import DictMixin
from tempita import Template

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

    ## FIXME: this needs to be fixed a bunch:
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
            if isinstance(value, self.__class__):
                namespaces.append((key, value))
            else:
                keys.append((key, value))
        for key, value in keys:
            if detail >= 1:
                loc = ' from %s [%s]' % (self.positions[key], self.sections[key])
            else:
                loc = ''
            lines.append('%s: %s%s', (key, self._quote(value), loc))
        if namespaces:
            lines.append('== Sub-namespaces: ==')
            for key, value in namespaces:
                lines.append('%s:' % key)
                sublines = value.string_repr(detail).splitlines()
                for subline in sublines:
                    lines.append('  %s' % subline)
        if detail >= 2 and self.lost:
            lines.append('== Lost items: ==')
            for item in lost:
                lines.append(item)
        return '\n'.join(lines)

class SectionNamespace(DictMixin):

    def __init__(self, ns, config, section, name=None):
        self.ns = ns
        self.config = config
        self.section = section
        self.name = name

    def __getitem__(self, key):
        if key not in self:
            raise KeyError(key)
        return self.config.get(self.section, key)

    def __setitem__(self, key, value):
        self.config.set(self.section, key, value)

    def __delitem__(self, key):
        self.config.remove_option(self.section, key)

    def keys(self):
        return self.config.options(self.section)

    def __contains__(self, key):
        return self.config.has_option(self.section, key)

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
