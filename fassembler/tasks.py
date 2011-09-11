"""
The abstract base class for tasks (``Task``) and many useful
subclasses that actually do something.
"""

import copy
import os
import re
import subprocess
import sys
import urlparse

from fassembler.distutilspatch import find_distutils_file, update_distutils_file
from fassembler.util import asbool
from glob import glob
from tempita import Template
from types import StringTypes

class interpolated(object):
    """
    This is a descriptor, a dynamic kind of attribute.

    This descriptor takes values, and whenever the values are
    retrieved they are interpolated with ``self.interpolate(value)``.
    """
    def __init__(self, name):
        self.name = name
    def __get__(self, obj, type=None):
        ## FIXME: I *could* return a string subclass that gives access to the raw value too
        if obj is None:
            return self
        try:
            raw_value = getattr(obj, '_' + self.name)
        except AttributeError:
            raise AttributeError(
                "No value set for %s" % self.name)
        return obj.interpolate(raw_value, name=obj.position + (' attribute %s' % self.name))
    def __set__(self, obj, value):
        ## FIXME: nice to compile the template here too
        setattr(obj, '_' + self.name, value)
    def __delete__(self, obj, value):
        delattr(obj, '_' + self.name)
    def __repr__(self):
        return '<%s for attribute %s>' % (
            self.__class__.__name__, self.name)


class Task(object):
    """
    Abstract base class for tasks
    """

    maker = None
    description = None
    name = interpolated('name')

    def __init__(self, name, stacklevel=1):
        self.name = name
        self.position = self._stacklevel_position(stacklevel+1)

    @property
    def title(self):
        """
        A human-readable summary of this task.
        """
        return '%s  (%s.%s)' % (self.name, self.__class__.__module__,
                                self.__class__.__name__)

    def bind(self, maker, environ, logger, config, project):
        """
        This is called by the project to bind this task instance to a
        running environment.
        """
        self.maker = maker
        self.environ = environ
        self.logger = logger
        self.config = config
        self.project = project
        self.config_section = project.config_section

    def confirm_settings(self):
        """
        This is called to check that all required settings have been set.
        """
        # Quick test that bind has been called
        assert self.maker is not None

    def setup_build_properties(self):
        """
        Called early on to set any project.build_properties that other
        tasks might need.
        """

    def run(self):
        """
        Subclasses should implement this.
        """
        raise NotImplementedError

    def interpolate(self, string, stacklevel=1, name=None):
        """
        Interpolate the given string, using ``name`` if given or a
        name derived from the callstack if not.
        """
        return self.project.interpolate_ns(
            string, self.create_namespace(), stacklevel=stacklevel+1, name=name)

    def create_namespace(self):
        """
        Create a task-local namespace.
        """
        ns = self.project.create_namespace()
        ns['task'] = self
        return ns

    def copy_dir(self, *args, **kw):
        """
        Run maker.copy_dir, with interpolated arguments.
        """
        self._run_fill_method('copy_dir', *args, **kw)

    def copy_file(self, *args, **kw):
        """
        Run maker.copy_file, with interpolated arguments.
        """
        self._run_fill_method('copy_file', *args, **kw)

    def _run_fill_method(self, method_name, *args, **kw):
        ns = self.create_namespace()
        kw.setdefault('template_vars', ns.dict)
        def interpolater(content, vars, filename):
            tmpl = Template(content, name=filename)
            return ns.execute_template(tmpl)
        kw.setdefault('interpolater', interpolater)
        method = getattr(self.maker, method_name)
        method(*args, **kw)

    def _stacklevel_position(self, stacklevel):
        """
        Figure out the file location of the given frame, stacklevel frames back.
        """
        try:
            caller = sys._getframe(stacklevel)
        except ValueError:
            return None
        globals = caller.f_globals
        lineno = caller.f_lineno
        if '__file__' in globals:
            name = globals['__file__']
            if name.endswith('.pyc') or name.endswith('.pyo'):
                name = name[:-1]
        elif '__name__' in globals:
            name = globals['__name__']
        else:
            name = '<string>'
        if lineno:
            name += ':%s' % lineno
        return name

    def venv_property(self, name='path'):
        """
        Return a property in ``self.project.build_properties`` named
        ``virtualenv_<name>``.  Gives a reasonable error if not present.
        """
        prop = self.project.build_properties.get('virtualenv_%s' % name)
        if not prop:
            raise Exception(
                "You must run a VirtualEnv task before this task")
        return prop

    def __str__(self):
        """
        Human-readable description of what this task will do.
        """
        if self.description is None:
            return repr(self)
        if self.maker is None:
            return repr(self).lstrip('>') + ' (unbound)>'
        try:
            return self.interpolate(self.description, name='description of %s' % self.__class__.__name__)
        except Exception, e:
            return '%s (error in description: %s)>' % (repr(self).rstrip('>'), e)

    def iter_subtasks(self):
        return []

class Script(Task):
    """
    Run a process/script
    """

    description = """
    Run the process:
      {{maker._format_command(task.script)}}
      {{if task.cwd}}
      in {{task.cwd}}
      {{endif}}
    {{if task.extra_args}}Also call run_command with keyword arguments {{task.extra_args}}{{endif}}
    {{if task.use_virtualenv }}A virtualenv environment will be used (one MUST be built for the project).
    {{else}}No virtualenv environment will be used.
    {{endif}}
    {{if task.stdin}}
    Also send the text {{task.stdin|repr}} as stdin
    {{endif}}
    """

    script = interpolated('script')
    cwd = interpolated('cwd')
    stdin = interpolated('stdin')

    def __init__(self, name, script, cwd=None, stacklevel=1, use_virtualenv=False,
                 stdin=None, **extra_args):
        super(Script, self).__init__(name, stacklevel=stacklevel+1)
        self.script = script
        self.cwd = cwd
        self.use_virtualenv = use_virtualenv
        self.stdin = stdin
        self.extra_args = extra_args

    def run(self):
        script = self.script
        kw = self.extra_args.copy()
        if self.use_virtualenv:
            kw['script_abspath'] = self.venv_property('bin_path')
        kw['stdin'] = self.stdin
        self.maker.run_command(script, cwd=self.cwd, **kw)


class CopyDir(Task):
    """
    Copy files
    """

    description = """
    Copy the files from {{task.source}} to {{os.path.join(env.base_path, task.dest)}}
    """

    source = interpolated('source')
    dest = interpolated('dest')

    def __init__(self, name, source, dest, stacklevel=1, add_dest_to_svn=False):
        super(CopyDir, self).__init__(name, stacklevel=stacklevel+1)
        self.source = source
        self.dest = dest
        self.add_dest_to_svn = add_dest_to_svn

    def run(self):
        self.logger.info(
            'Copying %s to %s' % (self.source, self.dest))
        self.copy_dir(self.source, self.dest, add_dest_to_svn=self.add_dest_to_svn)

class EnsureFile(Task):
    """
    Write a single file
    """

    description = """
    Write the file {{task.dest}} with the given content ({{len(task.resolved_content)}} bytes/{{len(task.resolved_content.splitlines())}} lines){{if task.content_path}} loaded from {{task.content_path}}{{endif}}.
    {{if not task.overwrite:}}
    If {{task.dest}} already exists{{if maker.exists(task.dest)}} (and it does){{endif}}, do not overwrite it.
    {{endif}}
    {{if task.svn_add}}
    If {{os.path.dirname(task.dest)}} is an svn checkout, this file will be added.
    {{endif}}
    {{if task.executable}}
    The file will be made executable.
    {{endif}}
    {{if task.content_path and task.content_path.endswith('tmpl')}}
    The output will have Tempita markup evaluated.
    {{endif}}
    """

    dest = interpolated('dest')
    content = interpolated('content')
    content_path = interpolated('content_path')

    def __init__(self, name, dest, content=None, content_path=None, overwrite=True,
                 svn_add=False, executable=False, stacklevel=1,
                 force_overwrite=False):
        super(EnsureFile, self).__init__(name, stacklevel=stacklevel+1)
        self.dest = dest
        self.content = content
        self.content_path = content_path
        assert content or content_path, (
            "You must give a value for content or content_path")
        self.overwrite = overwrite
        self.force_overwrite = force_overwrite
        self.svn_add = svn_add
        self.executable = executable

    @property
    def resolved_content(self):
        """
        The content from self.content or self.content_path
        """
        if self.content_path:
            tmpl = Template.from_filename(self.maker.path(self.content_path))
            return self.interpolate(tmpl)
        else:
            return self.content

    def run(self):
        if not self.overwrite and self.maker.exists(self.dest):
            self.logger.notify('File %s already exists; not overwriting' % self.dest)
            return
        self.maker.ensure_file(self.dest, self.resolved_content, svn_add=self.svn_add,
                               overwrite=self.force_overwrite, executable=self.executable)


class EnsureSymlink(Task):
    """
    Write a symlink
    """

    description = """
    Write the symlink {{task.dest}} pointing to {{task.source}}
    {{if not task.overwrite:}}
    If {{task.dest}} already exists{{if maker.exists(task.dest)}} (and it does){{endif}}, do not overwrite it.
    {{endif}}
    """

    dest = interpolated('dest')
    source = interpolated('source')

    def __init__(self, name, source, dest, overwrite=True, stacklevel=1,
                 force_overwrite=False):
        super(EnsureSymlink, self).__init__(name, stacklevel=stacklevel+1)
        self.dest = dest
        self.source = source
        self.overwrite = overwrite
        self.force_overwrite = force_overwrite

    def run(self):
        if not self.overwrite and self.maker.exists(self.dest):
            self.logger.notify('File %s already exists; not overwriting'
                               % self.dest)
            return
        if os.path.exists(self.dest) and not os.path.islink(self.dest):
            self.logger.notify('Removing non-link at %s' % self.dest)
            self.maker.rmtree(self.dest)
        self.maker.ensure_symlink(self.source, self.dest,
                                  overwrite=self.force_overwrite)


class EnsureDir(Task):

    description = """
    Ensure that the directory {{task.dest}} exists, creating if necessary.
    {{if task.svn_add}}
    If the parent directory {{os.path.dirname(task.dest)}} is an svn repository, also svn add this directory.
    {{endif}}
    """

    dest = interpolated('dest')

    def __init__(self, name, dest, svn_add=True, stacklevel=1):
        super(EnsureDir, self).__init__(name, stacklevel=stacklevel+1)
        self.dest = dest
        self.svn_add = svn_add

    def run(self):
        self.maker.ensure_dir(self.dest, svn_add=self.svn_add)

class SvnCheckout(Task):
    """
    Check out files from svn
    """

    description = """
    Check out files from {{task.full_repository}} to {{task.dest}}
    {{if task.create_if_necessary}}
    {{if task.base_repository and task.base_repository.startswith('file:')}}
    If the repository at {{task.base_repository}} does not exist, it will be created.
    {{endif}}
    If the svn directory at {{task.full_repository}} does not exist, it will be created.
    {{endif}}
    {{if task.on_create_set_props}}
    If creating the directory, set the properties:
    {{for name, value in sorted(task.on_create_set_props.items()):}}
      {{name}} = {{value}}
    {{endfor}}
    {{endif}}
    """

    repository = interpolated('repository')
    dest = interpolated('dest')
    base_repository = interpolated('base_repository')
    on_create_set_props = interpolated('on_create_set_props')

    def __init__(self, name, repository, dest, base_repository=None,
                 create_if_necessary=False, on_create_set_props=None, stacklevel=1):
        super(SvnCheckout, self).__init__(name, stacklevel=stacklevel+1)
        self.repository = repository
        self.dest = dest
        self.base_repository = base_repository
        if on_create_set_props and not create_if_necessary:
            raise ValueError(
                "Setting on_create_set_props when create_if_necessary is false doesn't make sense")
        self.create_if_necessary = create_if_necessary
        self.on_create_set_props = on_create_set_props

    @property
    def full_repository(self):
        """
        The repository, interpreted relative to ``self.base_repository``
        """
        base = self.base_repository
        if base:
            if not base.endswith('/'):
                base += '/'
            return urlparse.urljoin(base, self.repository)
        else:
            return self.repository

    def run(self):
        base = self.base_repository
        if base and self.create_if_necessary and base.startswith('file:'):
            self.confirm_repository(base)
        full_repo = self.full_repository
        if self.create_if_necessary:
            created = self.confirm_directory(full_repo)
        else:
            created = False
        self.maker.checkout_svn(full_repo, self.dest)
        if created and self.on_create_set_props:
            for name, value in sorted(self.on_create_set_props.items()):
                self.logger.notify('Setting property %s to %r' % (name, value))
                self.maker.run_command(
                    ['svn', 'ps', name, value, self.dest])

    def confirm_repository(self, repo):
        """
        Checks that the repository exists.  If it does not exist and
        create is True, and the repository is a ``file:`` repository,
        this will create the repository.
        """
        assert repo.startswith('file:')
        stdout, stderr, returncode = self.maker.run_command(
            ['svn', 'ls', repo],
            expect_returncode=True,
            return_full=True)
        if returncode:
            if 'Unable to open' not in stderr:
                self.logger.warn(
                    'Got unexpected output from "svn ls %s":\n%s'
                    % (repo, stdout))
                return
            repo_path = os.path.sep + repo[5:].lstrip('/\\')
            self.logger.notify('Creating repository %s' % repo)
            self.maker.run_command(
                ['svnadmin', 'create', repo_path])

    def confirm_directory(self, repo):
        """
        Makes sure the svn directory exists, and creates it if it does not.
        """
        stdout, stderr, returncode = self.maker.run_command(
            ['svn', 'ls', repo],
            expect_returncode=True,
            return_full=True)
        if returncode:
            self.logger.notify('Creating svn directory for %s' % repo)
            self.maker.run_command(
                ['svn', 'mkdir', '-m', 'Auto-creating directory for %s' % self.project.name,
                 repo])
            return True
        else:
            self.logger.debug('repository directory %s exists' % repo)
            return False

class VirtualEnv(Task):
    """
    Create a virtualenv environment
    """

    description = """
    Create a virtualenv environment in {{maker.path(task.path or project.name)}}
    {{if not task.path}} ({{project.name}} is the project name){{endif}}
    {{if task.different_python}} run as a separate process using task.different_python as the binary{{endif}}
    {{if task.site_packages}}Global site-packages will be available{{else}}Global site-packages will NOT be available{{endif}}

    {{if os.path.exists(task.path_resolved):}}
    Directory already exists.
    {{if project.config.getdefault('DEFAULT', 'force_virtualenv'):}}
    Because force_virtualenv is set, the virtualenv will be recreated.
    {{else}}
    Because force_virtualenv is not set, the virtualenv (re)creation will be skipped.
    {{endif}}
    {{endif}}

    Also, setuptools 0.6c11 will be installed in the virtualenv.

    {{if task.use_pip()}}
    Pip will also be installed into the virtualenv.
    {{endif}}
    """

    def use_pip(self):
        if self.config.has_option(self.project.name, 'use_pip'):
            _use_pip = asbool(self.config.get(self.project.name, 'use_pip'))
        else:
            _use_pip = asbool(self.config.getdefault('general', 'use_pip'))
        return _use_pip
            
    def __init__(self, name='Create virtualenv', path=None, site_packages=False,
                 different_python=False, stacklevel=1,
                 
never_create_virtualenv=False):
        super(VirtualEnv, self).__init__(name, stacklevel=stacklevel+1)
        self.path = path
        self.site_packages = site_packages
        self.different_python = different_python
        self.never_create_virtualenv = never_create_virtualenv


    @property
    def path_resolved(self):
        return self.maker.path(self.path or self.project.name)

    def virtualenv_exists(self):
        path = self.path_resolved
        if os.path.exists(path) and os.path.exists(os.path.join(path, 'lib')):
            return True
        return False

    def run(self):
        path = self.path_resolved
        if self.virtualenv_exists():
            if self.never_create_virtualenv:
                self.logger.notify('Skipping virtualenv creation as directory %s exists' % path)
                return
            if not self.project.config.getdefault('DEFAULT', 'force_virtualenv'):
                self.logger.notify('Skipping virtualenv creation as directory %s exists' % path)
                return
            else:
                self.logger.notify('Forcing virtualenv recreation')
        if self.never_create_virtualenv:
            self.logger.fatal("Virtualenv at %s does not exist, but should already exist!" % path)
            raise Exception
        import virtualenv
        if not self.different_python:
            ## FIXME: kind of a nasty hack, but maybe it's okay?
            virtualenv.logger = self.logger
            self.logger.level_adjust -= 2
            try:
                virtualenv.create_environment(path, site_packages=self.site_packages)
            finally:
                self.logger.level_adjust += 2
        else:
            venv_path = virtualenv.__file__
            if not venv_path:
                self.logger.fatal("Can't find 'virtualenv' binary")
                return
            if venv_path.endswith('.pyc') or venv_path.endswith('.pyo'):
                venv_path = venv_path[:-1]
            venv_args = [self.different_python, venv_path]
            if not self.site_packages:
                venv_args.append('--no-site-packages')
            venv_args.append(path)
            self.logger.notify('Subprocess virtualenv creation')
            proc = subprocess.Popen(venv_args, stdout=subprocess.PIPE)
            proc.communicate()
        self.logger.notify('virtualenv created in %s' % path)
        

    def iter_subtasks(self):
        if self.virtualenv_exists() and self.never_create_virtualenv:
            return []

        _tasks = []
        if self.environ.config.has_option('general', 'find_links'):
            find_links = self.environ.config.get('general', 'find_links')
            _tasks.append(
                SetDistutilsValue('Add custom find_links locations',
                                  'easy_install', 'find_links', find_links))
        _tasks.append(
            EasyInstall('Install latest setuptools',
                        'setuptools==0.6c11'))
        if self.use_pip():
            _tasks.append(EasyInstall('Install pip',
                                      'pip'))
        return _tasks

    def setup_build_properties(self):
        path = self.path_resolved
        assert path, "no path (%r)" % path
        props = self.project.build_properties
        ## FIXME: doesn't work on Windows:
        props['virtualenv_path'] = path
        props['virtualenv_bin_path'] = os.path.join(path, 'bin')
        props['virtualenv_python'] = os.path.join(path, 'bin', 'python')
        props['virtualenv_src_path'] = os.path.join(path, 'src')
        if not self.different_python:
            props['virtualenv_lib_python'] = os.path.join(path, 'lib', 'python%s' % sys.version[:3])
        else:
            proc = subprocess.Popen([self.different_python, '-V'],
                                    stderr=subprocess.PIPE)
            ver = proc.communicate()[1].strip()
            ver = ver.split()[1][:3]
            props['virtualenv_lib_python'] = os.path.join(path, 'lib', 'python%s' % ver[:3])


class EasyInstall(Script):
    """
    Run easy_install
    """

    ## FIXME: commas:
    description = """
    Install (with easy_install) the {{if len(task.reqs)>1}}packages{{else}}package{{endif}}: {{for req in task.reqs:}}{{req}} {{endfor}}
    """

    ## FIXME: name in the signature is dangerous
    def __init__(self, name, *reqs, **kw):
        assert reqs, 'No requirements given (just a name %r)' % name
        self.reqs = list(reqs)
        kw.setdefault('cwd', '{{project.build_properties.get("virtualenv_path", "/")}}')
        if 'find_links' in kw:
            find_links = kw.pop('find_links')
            if isinstance(find_links, basestring):
                find_links = [find_links]
            if find_links:
                self.reqs[:0] = ['-f', ' '.join(find_links)]
        kw['stacklevel'] = kw.get('stacklevel', 1)+1
        super(EasyInstall, self).__init__(name, ['easy_install'] + list(self.reqs), use_virtualenv=True, **kw)

class SourceInstall(SvnCheckout):
    """
    Install from svn source
    """
    ## FIXME: this should support other version control systems someday,
    ## maybe using the setuptools entry point for version control.

    description = """
    Check out {{task.repository}} into src/{{task.checkout_name}}/,
    then run python setup.py develop
    """

    checkout_name = interpolated('checkout_name')

    def __init__(self, name, repository, checkout_name, stacklevel=1):
        self.checkout_name = checkout_name
        dest = '{{project.build_properties["virtualenv_path"]}}/src/{{task.checkout_name}}'
        super(SourceInstall, self).__init__(
            name, repository, dest, create_if_necessary=False,
            stacklevel=stacklevel+1)

    def run(self):
        super(SourceInstall, self).run()
        self.maker.run_command(
            self.interpolate('{{project.build_properties["virtualenv_bin_path"]}}/python', stacklevel=1),
            'setup.py', 'develop',
            cwd=self.dest)

class InstallPasteConfig(Task):

    template = interpolated('template')
    path = interpolated('path')

    description = """
    Install a Paste configuration file in
    {{if task.ininame}}etc/{{project.name}}/{{task.ininame}}.ini
    {{else}}etc/{{project.name}}/{{project.name}}.ini{{endif}}
    from {{if task.template}}a static template{{else}}the file {{task.path}}{{endif}}
    """

    def __init__(self, template=None, path=None, name='Install Paste configuration',
                 ininame=None, stacklevel=1):
        super(InstallPasteConfig, self).__init__(name, stacklevel=stacklevel+1)
        assert path or template, "You must give one of path or template"
        self.path = path
        self.template = template
        self.ininame = ininame

    def run(self):
        ininame = self.ininame or self.project.name
        dest = os.path.join('etc', self.project.name, ininame+'.ini')
        if self.template:
            self.maker.ensure_file(
                dest,
                self.template)
        else:
            self.copy_file(self.path, dest)
        self.logger.notify('Configuration written to %s' % dest)

class InstallPasteStartup(Task):

    description = """
    Install the standard Paste startup script
    """

    exe_dir = interpolated('exe_dir')

    def __init__(self, name='Install Paste startup script', exe_dir='{{env.base_path}}/{{project.name}}/src/{{project.name}}', stacklevel=1):
        super(InstallPasteStartup, self).__init__(name, stacklevel=stacklevel+1)
        self.exe_dir = exe_dir

    def run(self):
        path = os.path.join('bin', 'start-'+self.project.name)
        self.maker.ensure_file(
            path,
            self.content,
            executable=True)
        self.logger.notify('Startup script written to %s' % path)

    @property
    def content(self):
        return self.interpolate(self.content_template, name=__name__+'.InstallPasteStartup.content_template')

    content_template = """\
#!/bin/sh
cd {{task.exe_dir}}
exec {{env.base_path}}/{{project.name}}/bin/paster serve {{env.base_path}}/etc/{{project.name}}/{{project.name}}.ini "$@"
"""

class InstallSupervisorConfig(Task):

    description = """
    Install standard supervisor template into {{task.conf_path}}
    """

    script_name = interpolated('script_name')

    def __init__(self, name='Install supervisor startup script',
                 script_name='{{project.name}}', stacklevel=1):
        super(InstallSupervisorConfig, self).__init__(name, stacklevel=stacklevel+1)
        self.script_name = script_name

    @property
    def conf_path(self):
        return os.path.join('etc', 'supervisor.d', self.script_name + '.ini')

    def run(self):
        self.maker.ensure_file(
            self.conf_path,
            self.content,
            executable=True)
        ## FIXME: is this really the proper place to be making a log directory?
        ## I don't really think so.
        self.maker.ensure_dir(
            os.path.join(self.environ.var, 'logs', self.project.name))
        self.logger.notify('Supervisor config written to %s' % self.conf_path)

    @property
    def content(self):
        return self.interpolate(self.content_template, name=__name__+'.InstallSupervisorConfig.content_template')

    content_template = """\
[program:{{task.script_name}}]
command = {{env.base_path}}/bin/start-{{task.script_name}}
{{#FIXME: should set user=username}}
stdout_logfile = {{env.var}}/logs/{{project.name}}/{{task.script_name}}-supervisor.log
stdout_logfile_maxbytes = 1MB
stdout_logfile_backups = 10
redirect_stderr = true
stdout_capture_maxbytes = 200KB
stderr_capture_maxbytes = 200KB
"""

class CheckMySQLDatabase(Task):

    db_name = interpolated('db_name')
    db_host = interpolated('db_host')
    db_username = interpolated('db_username')
    db_password = interpolated('db_password')
    db_root_password = interpolated('db_root_password')
    db_charset = interpolated('db_charset')

    description = """
    Check that the database {{task.db_name}}@{{task.db_host}} exists
    (accessing it with u/p {{config.db_username}}/{{repr(config.db_password)}}).
    If it does not exist, create the database.  If the database does
    exist, make sure that the user has full access.

    This will connect as root to create the database if necessary.
    """

    def __init__(self, name, db_name='{{config.db_name}}',
                 db_host='{{config.db_host}}', db_username='{{config.db_username}}',
                 db_password='{{config.db_password}}', db_root_password='{{config.db_root_password}}',
                 db_charset='{{config.get("db_charset", "utf8")}}',
                 stacklevel=1):
        super(CheckMySQLDatabase, self).__init__(name, stacklevel=stacklevel+1)
        self.db_name = db_name
        self.db_host = db_host
        self.db_username = db_username
        self.db_password = db_password
        self.db_root_password = db_root_password
        self.db_charset = db_charset

    password_error = 1045
    access_denied_error = 1044
    unknown_database = 1049
    unknown_server = 2005
    server_cant_connect = 2003
    
    def passkw(self, password):
        # There is no default for the passwd argument, so we have
        # to pass that argument in conditionally
        if password:
            return {'passwd': password}
        else:
            return {}

    def run(self):
        try:
            import MySQLdb
        except ImportError:
            self.logger.fatal(
                "Cannot check MySQL database: MySQLdb module is not installed")
            ## FIXME: query or something?
            return
        try:
            self.logger.debug(
                "Connecting to MySQL database %s@%s, username=%s, password=%r"
                % (self.db_name, self.db_host, self.db_username, self.db_password))
            conn = MySQLdb.connect(
                host=self.db_host,
                db=self.db_name,
                user=self.db_username,
                **self.passkw(self.db_password))
        except MySQLdb.OperationalError, e:
            code = e.args[0]
            if code == self.unknown_server or code == self.server_cant_connect:
                self.logger.fatal(
                    "Cannot connect to MySQL server at %s: %s"
                    % (self.db_host, e))
                raise
            elif code == self.password_error or code == self.access_denied_error:
                # Could be a database name problem, or access
                self.logger.notify(
                    "Cannot connect to %s@%s, will try to create"
                    % (self.db_name, self.db_host))
            elif code == self.unknown_database:
                self.logger.notify(
                    "Database %s does not exist, will try to create" % self.db_name)
            else:
                self.logger.fatal(
                    "Unexpected MySQL connection error: %s"
                    % e)
                raise
            self.create_database()
        else:
            # All is good
            self.logger.debug("Connection successful")
            conn.close()
        self.change_permissions()
        self.logger.notify('Database %s@%s setup for user %s' % (self.db_name, self.db_host, self.db_username))

    def create_database(self):
        """
        Creates the database, accessing MySQL as root.
        """
        import MySQLdb
        try:
            conn = self.root_connection()
        except MySQLdb.OperationalError, e:
            code = e.args[0]
            if code == self.unknown_database:
                pass
            else:
                self.logger.fatal("Error connecting as root: %s" % e)
                raise
        else:
            # Database exists fine
            self.logger.debug('Database exists')
            conn.close()
            return
        conn = MySQLdb.connect(
            host=self.db_host,
            user='root',
            **self.passkw(self._root_password_override or self.db_root_password))
        ## FIXME: ideally the character set would be checked even if the database existed,
        ## and updated with ALTER DATABASE <dbname> CHARACTER SET <db_charset>
        plan = 'CREATE DATABASE %s CHARACTER SET %%s' % self.db_name
        charset = self.db_charset
        self.logger.info('Executing %s' % (plan % repr(charset)))
        if not self.maker.simulate:
            conn.cursor().execute(plan, (charset,))
        conn.close()

    def change_permissions(self):
        """
        Grants all privileges to the configured user for the database.
        """
        conn = self.root_connection()
        plan = "GRANT ALL PRIVILEGES ON %s.* TO %s@localhost IDENTIFIED BY %r" % (
            self.db_name, self.db_username, self.db_password)
        self.logger.info('Executing %s' % plan)
        if not self.maker.simulate:
            plan = "GRANT ALL PRIVILEGES ON %s.* TO %s@localhost" % (self.db_name, self.db_username)
            if self.db_password:
                plan += " IDENTIFIED BY %s"
                args = (self.db_password,)
            else:
                args = ()
                self.logger.warn('Note: no password set for %s@localhost; login may not work' % self.db_name)
            conn.cursor().execute(plan, args)
        conn.close()
        
    _root_password_override = None

    def root_connection(self):
        """
        Returns a connection to the MySQL database, as root.
        """
        import MySQLdb
        try:
            return MySQLdb.connect(
                host=self.db_host,
                db=self.db_name,
                user='root',
                **self.passkw(self._root_password_override or self.db_root_password))
        except MySQLdb.OperationalError, e:
            exc_info = sys.exc_info()
            code = e.args[0]
            if code == self.password_error:
                self.logger.fatal("The root password %r is incorrect" % (self._root_password_override or self.db_root_password or '(no password)'))
                if self.maker.interactive:
                    ## FIXME: this could use getpass.  But I hate
                    ## getpass.  Personal bias that I never have
                    ## anyone looking over my shoulder?
                    try:
                        self.maker.beep_if_necessary()
                        self.__class__._root_password_override = raw_input('Please enter the correct password (^C to abort): ')
                    except KeyboardInterrupt:
                        print '^C'
                        raise exc_info[0], exc_info[1], exc_info[2]
                    return self.root_connection()
            raise
        
class SaveSetting(Task):
    """
    Save a setting in build.ini.

    Optional validation can be performed by passing a validators
    dictionary, where keys correspond to the keys in variables, and
    values are callables taking a single argument that raise
    ValueError if something is wrong.
    """
    
    description = """
    {{if not task.overwrite_if_empty and not filter(None, task.variables.values())}}
    *Would* save the settings {{task.format_variables(task.variables)}}, if the setting was provided;
    because no setting was provided, the variable will not be set.
    {{else}}
    Save the setting{{if len(task.variables)>1}}s{{endif}} into build.ini:
    {{for setting in task.format_variables(task.variables)}}
    * {{setting}}
    {{endfor}}
    {{endif}}
    """

    variables = interpolated('variables')
    section = interpolated('section')

    def __init__(self, name, variables, section='general',
                 overwrite_if_empty=True, overwrite=True,
                 validators={},
                 stacklevel=1):
        assert isinstance(variables, dict), (
            "The variables parameter should be a dictionary")
        super(SaveSetting, self).__init__(name, stacklevel=stacklevel+1)
        self.variables = variables
        self.section = section
        self.overwrite_if_empty = overwrite_if_empty
        self.overwrite = overwrite
        self.validators = validators

    def run(self):
        config = self.environ.config
        if not config.has_section(self.section):
            config.add_section(self.section)
        for key, value in self.variables.items():
            if isinstance(key, (tuple, list)):
                section, key = key
            else:
                section = self.section
            if self.validators.has_key(key):
                self.validators[key](value)
            should_write = self.should_write_setting(section, key, value)
            if should_write:
                config.set(section, key, value)
            else:
                if value != config.get(section, key):
                    self.logger.notify(
                        'Not overwriting build.ini option [%s] %s = %r (new value would have been %r)'
                        % (section, key, config.get(section, key), value))
        self.environ.save()

    def should_write_setting(self, section, key, value):
        if self.overwrite:
            return True
        if not self.environ.config.has_option(section, key):
            return True
        if self.overwrite_if_empty and not self.environ.config.get(section, key):
            return True
        if value == self.environ.config.get(section, key):
            return True
        return False
 
    def format_variables(self, variables):
        """
        Format the given variable dictionary for human reading.
        """
        keys = sorted(variables)
        default_section = self.section
        output = []
        for key in keys:
            if isinstance(key, (tuple, list)):
                section, key = key
            else:
                section = default_section
            if not self.should_write_setting(section, key, variables[key]):
                output.append(
                    'will not write [%s] %s = %r (current value: %r)'
                    % (section, key, variables[key], self.environ.config.get(section, key)))
            else:
                output.append('[%s] %s = %r' % (section, key, variables[key]))
        return output

class SaveURI(SaveSetting):

    project_name = interpolated('project_name')

    def __init__(self, name='Save URI setting',
                 project_name='{{project.name}}',
                 path=None,
                 uri='http://{{config.host}}:{{config.port}}',
                 project_local=True,
                 uri_template=None,
                 uri_template_main_site=None,
                 theme=True,
                 trailing_slash=True,
                 header_name=None,
                 public=True,
                 stacklevel=1):
        assert path is not None, (
            "You must give a value for path")
        variables = {'{{task.project_name}} uri': uri,
                     '{{task.project_name}} path': path,
                     }
        if not project_local:
            variables['{{task.project_name}} project_local'] = 'false'
        if uri_template:
            variables['{{task.project_name}} uri_template'] = uri_template
        if uri_template_main_site:
            variables['{{task.project_name}} uri_template_main_site'] = uri_template_main_site
        if not theme:
            variables['{{task.project_name}} theme'] = 'false'
        elif theme == 'not-main-site':
            variables['{{task.project_name}} theme'] = theme
        if not trailing_slash:
            variables['{{task.project_name}} trailing_slash'] = 'false'
        if header_name:
            variables['{{task.project_name}} header_name'] = header_name
        if not public:
            variables['{{task.project_name}} public'] = 'false'
        self.project_name = project_name
        super(SaveURI, self).__init__(
            name, variables, section='applications',
            stacklevel=stacklevel+1)
                                      
class Patch(Task):

    files = interpolated('files')
    dest = interpolated('dest')
    strip = interpolated('strip')

    description = """
    Patch the files {{', '.join(task.files)}}
    {{if task.expanded_files != task.files}}(expanded to {{', '.join(task.expanded_files)}}){{endif}}
    Patches applied to {{task.dest}}, -p {{task.strip}}.
    """

    def __init__(self, name, files, dest, strip='0', stacklevel=1):
        super(Patch, self).__init__(name, stacklevel=stacklevel+1)
        if isinstance(files, basestring):
            files = [files]
        self.files = files
        self.dest = dest
        self.strip = strip

    _rejects_regex = re.compile('rejects to file (.*)')

    def run(self):
        files = self.expanded_files
        if files != self.files:
            self.logger.notify('Applying patches %s (from %s)' % (', '.join(files), ', '.join(self.files)))
        else:
            self.logger.notify('Applying patches %s' % ', '.join(files))
        for file in files:
            self.logger.indent += 2
            try:
                # --forward makes re-applying a patch OK
                stdout, stderr, returncode = self.maker.run_command(
                    ['patch', '-p', self.strip, '--forward', '-i', file],
                    cwd=self.dest, expect_returncode=True,
                    return_full=True)
                if returncode:
                    if 'Reversed (or previously applied) patch detected!  Skipping patch.' in stdout:
                        self.logger.info('Patch already applied.')
                    else:
                        self.logger.error('Patch returned with code %s' % returncode, color='bold red')
                        self.logger.error('Patch file %s applied from directory %s' % (file, self.maker.path(self.dest)))
                        if stdout:
                            self.logger.error('stdout:')
                            self.logger.indent += 2
                            try:
                                self.logger.error(stdout)
                            finally:
                                self.logger.indent -= 2
                        if stderr:
                            self.logger.error('stderr:')
                            self.logger.indent += 2
                            try:
                                self.logger.error(stderr)
                            finally:
                                self.logger.indent -= 2
                        self.logger.debug('Patch contents:')
                        self.logger.indent += 2
                        try:
                            self.logger.debug(open(file).read())
                        finally:
                            self.logger.indent -= 2
                        reject_match = self._rejects_regex.search(stdout)
                        if reject_match:
                            reject_file = os.path.join(self.dest, reject_match.group(1))
                            self.logger.debug('Contents of rejects file %s:' % reject_file)
                            self.logger.indent += 2
                            try:
                                self.logger.debug(open(reject_file).read())
                            finally:
                                self.logger.indent -= 2
                        raise OSError('Patch failed')
            finally:
                self.logger.indent -= 2

    @property
    def expanded_files(self):
        return self.expand_globs(self.files)

    def expand_globs(self, files):
        """
        Expand a list of files, treating each as a glob.
        """
        result = []
        for file_spec in files:
            if '*' not in file_spec:
                result.append(file_spec)
                continue
            result.extend(glob(file_spec))
        return result

class InstallSpec(Task):

    description = """
    Install the packages from {{task.spec_filename}}:
    {{for line in open(maker.path(task.spec_filename)):}}
    {{py: line = line.strip()}}
    {{if line.startswith('-e') or line.startswith('--editable'):}}* svn checkout {{line.split(None, 1)[1]}}{{else}}* {{line}}{{endif}}{{endfor}}
    """

    spec_filename = interpolated('spec_filename')

    def __init__(self, name, spec_filename, stacklevel=1):
        super(InstallSpec, self).__init__(name, stacklevel=stacklevel+1)
        self.spec_filename = spec_filename

    def run(self):
        if self.config.has_option(self.project.name, 'use_pip'):
            use_pip = asbool(self.config.get(self.project.name, 'use_pip'))
        else:
            use_pip = asbool(self.config.getdefault('general', 'use_pip'))
        if use_pip:
            self.run_pip()
            return
        context, commands = self.read_commands()
        context['virtualenv_python'] = self.project.build_properties['virtualenv_python']
        extra_commands = []
        for command, arg in commands:
            result = command(context, arg)
            if result:
                extra_commands.append(result)
        for command, arg in extra_commands:
            command(context, arg)

    def run_pip(self):
        ## FIXME: it would save a tiny bit of effort to do the -E
        ## stuff directly, instead of starting and then replacing the
        ## subprocess like it'll do with this:
        env = os.environ.copy()
        env['PIP_LOG_EXPLICIT_LEVELS'] = '1'
        env['PIP_DEFAULT_VCS'] = 'svn'
        env['PIP_SKIP_REQUIREMENTS_REGEX'] = '^\w+\s*=[^=]'
        self.maker.run_command(
            'pip', '-E', self.venv_property('path'),
            'install', '-r', self.spec_filename,
            '-vvvv',
            log_filter=self.log_explicit_filter,
            env=env,
            extra_path=[self.project.build_properties['virtualenv_bin_path']])

    _log_explicit_re = re.compile(r'^(\d+)\s+')
    def log_explicit_filter(self, line):
        match = self._log_explicit_re.match(line)
        if not match:
            return (line, self.logger.WARN)
        level = int(match.group(1))
        line = line[match.end():]
        return (line, level)

    _setting_re = re.compile(r'^(\w+)\s*=\s*([^=<>\s].*)$')

    def read_commands(self, filename=None):
        """
        Reads the commands in the given file (or self.spec_filename),
        returning ``(context_dictionary, list_of_commands)``, where
        the list of commands is in the form::

          [(function, argument)]

        The functions will be called like ``function(context,
        argument)``, and may return another ``(function, argument)``
        to be called later.
        """
        if filename is None:
            filename = self.spec_filename
        self.logger.debug('Reading spec %s' % filename)
        f = open(self.maker.path(filename))
        context = dict(find_links=[],
                       src_base=os.path.join(self.project.build_properties['virtualenv_path'], 'src'),
                       always_unzip=False)
        commands = []
        uneditable_eggs = []
        # Used to flag state when we are looking for multi-line settings, like:
        # setting = value
        #           line 2
        in_setting = False
        for line in f:
            line = line.rstrip()
            if not line or line.strip().startswith('#'):
                continue
            if in_setting:
                if line.strip() != line:
                    # Leading whitespace; multi-line setting
                    continue
                else:
                    in_setting = False
            if self._setting_re.search(line):
                # We just skip settings here
                in_setting = True
                continue
            if line.startswith('-f') or line.startswith('--find-links'):
                if line.startswith('-f'):
                    line = line[2:]
                else:
                    line = line[len('--find-links'):].lstrip('=')
                context['find_links'].append(line.strip())
                continue
            if line.startswith('--always-unzip') or line.startswith('-Z'):
                context['always_unzip'] = True
                continue
            if line.startswith('-e') or line.startswith('--editable'):
                if uneditable_eggs:
                    commands.append((self.install_eggs, uneditable_eggs))
                    uneditable_eggs = []
                if line.startswith('-e'):
                    line = line[2:]
                else:
                    line = line[len('--editable'):].lstrip('=')
                line = line.strip()
                if line.startswith('svn+') and not line.startswith('svn+ssh'):
                    line = line[4:]
                commands.append((self.install_editable, line))
                continue
            uneditable_eggs.append(line.strip())
        if uneditable_eggs:
            commands.append((self.install_eggs, uneditable_eggs))
        return context, commands

    _rev_svn_re = re.compile(r'@(\d+)$')
    _egg_spec_re = re.compile(r'egg=([^-=&]*)')

    def install_editable(self, context, svn):
        """
        Installs one editable project.  This step does not install any
        dependencies for the project; that is done later by
        ``self.install_finalize_editable``
        """
        ops = []
        name = None
        if '#' in svn:
            svn, fragment = svn.split('#', 1)
            match = self._egg_spec_re.search(fragment)
            if match:
                name = match.group(1)
        revision = None
        match = self._rev_svn_re.search(svn)
        if match:
            svn = svn[:match.start()]
            revision = match.group(1)
        ops.append(svn)
        if name is None:
            parts = [p for p in svn.split('/') if p]
            if parts[-2] in ('tags', 'branches', 'tag', 'branch'):
                name = parts[-3]
            elif parts[-1] == 'trunk':
                name = parts[-2]
            else:
                raise ValueError(
                    "Cannot determine the name of the package from the svn directory %s; "
                    "you should add #egg=Name to the URL" % svn)
        # Normalizing the name, so it's more predictable later:
        name = name.lower()
        dest = os.path.join(context['src_base'], name)
        self.logger.notify('Preparing checkout %s' % name)
        self.logger.indent += 2
        try:
            self.maker.checkout_svn(svn, dest, revision=revision)
            self.maker.run_command(
                'python', 'setup.py', 'develop', '--no-deps',
                cwd=dest,
                script_abspath=self.venv_property('bin_path'),
                log_filter=self.make_log_filter())
            return self.install_finalize_editable, dest
        finally:
            self.logger.indent -= 2

    def install_finalize_editable(self, context, src_dir):
        """
        Finalizes the installation of an editable project.
        """
        cmd = ['python', 'setup.py', 'develop']
        if context['find_links']:
            cmd.extend(['-f', ' '.join(context['find_links'])])
        if context['always_unzip']:
            cmd.append('--always-unzip')
        self.logger.notify('Installing %s (and its dependencies)' % os.path.basename(src_dir))
        self.logger.indent += 2
        try:
            self.maker.run_command(
                cmd,
                cwd=src_dir,
                script_abspath=self.venv_property('bin_path'),
                log_filter=self.make_log_filter())
        finally:
            self.logger.indent -= 2

    def install_eggs(self, context, eggs):
        """
        Installs a set of eggs.
        """
        cmd = ['easy_install']
        if context['find_links']:
            cmd.append('-f')
            cmd.append(' '.join(context['find_links']))
        if context['always_unzip']:
            cmd.append('--always-unzip')
        cmd.extend(eggs)
        self.logger.notify('easy_installing %s' % ', '.join(eggs))
        self.logger.indent += 2
        try:
            self.maker.run_command(
                cmd,
                cwd=self.venv_property('path'),
                script_abspath=self.venv_property('bin_path'),
                log_filter=self.make_log_filter())
        finally:
            self.logger.indent -= 2

    log_filter_debug_regexes = [
        re.compile(r'references __(file|path)__$'),
        re.compile(r'^zip_safe flag not set; analyzing'),
        re.compile(r'MAY be using inspect.[a-zA-Z0-9_]+$'),
        re.compile(r'^Extracting .*to'),
        re.compile(r'^create .*\.egg$'),
        # Stuff from installing as an egg (from python setup.py install):
        re.compile(r'^writing .* to .*\.egg-info/'),
        re.compile(r'^writing .*\.egg-info/PKG-INFO$'),
        re.compile(r'^writing manifest file .*\.egg-info/SOURCES.txt.*'),
        re.compile(r'^running (develop|egg_info|build_ext)$'),
        # Mostly for PIL:
        re.compile(r'lib.*: warning: .* defined but not used'),
        ]
    log_filter_info_regexes = [
        re.compile(r'^Installing .* script to .*/bin$'),
        re.compile(r'^Creating .*\.egg-link [(]link to \.[)]$'),
        re.compile(r'^reading manifest template .MANIFEST\.in.$'),
        ]

    def make_log_filter(self):
        context = []
        hanging_processing = []
        def log_filter(line):
            """
            Filter the output of setup.py develop and easy_install
            """
            level = self.logger.NOTIFY
            adjust = 0
            prefix = 'Processing dependencies for '
            if line.startswith(prefix):
                requirement = line[len(prefix):].strip()
                context.append(requirement)
                hanging_processing[:] = [line]
                return ('', self.logger.VERBOSE_DEBUG)
                # Leave just this one line dedented:
                adjust = -2
            prefix = 'Finished processing dependencies for '
            if line.startswith(prefix):
                requirement = line[len(prefix):].strip()
                if context and context[-1] == 'searching':
                    # The dangling "Searching for ..." message
                    context.pop()
                if not context or context[-1] != requirement:
                    # For some reason the top-level context is often None from
                    # easy_install.process_distribution; so we shouldn't worry
                    # about inconsistency in that case
                    if len(context) != 1 or requirement != 'None':
                        self.logger.warn('Error: Got unexpected "%s%s"' % (prefix, requirement))
                        self.logger.warn('       Context: %s' % context)
                context.pop()
                if hanging_processing:
                    # The start/finish of dependencies was empty
                    last_line = hanging_processing[0]
                    hanging_processing[:] = []
                    return (last_line+'\n'+line, self.logger.DEBUG)
            prefix = 'Searching for '
            if line.startswith(prefix):
                if context and context[-1] == 'searching':
                    context.pop()
                context.append('searching')
                adjust = -2
            if not line.strip():
                level = self.logger.DEBUG
            for regex in self.log_filter_debug_regexes:
                if regex.search(line.strip()):
                    level = self.logger.DEBUG
            for regex in self.log_filter_info_regexes:
                if regex.search(line.strip()):
                    level = self.logger.INFO
            indent = len(context) * 2 + adjust
            line = ' '*indent + line
            if hanging_processing:
                last_line = hanging_processing[-1]
                self.logger.notify(last_line)
                hanging_processing[:] = []
            return (line, level)
        return log_filter

class InstallSpecIfPresent(InstallSpec):

    description = """
    Install the packages from {{task.spec_filename}} if the file exists:
    {{if maker.exists(task.spec_filename)}}
    {{for line in open(maker.path(task.spec_filename)):}}
    {{py: line = line.strip()}}
    {{if line.startswith('-e') or line.startswith('--editable'):}}* svn checkout {{line.split(None, 1)[1]}}{{else}}* {{line}}{{endif}}{{endfor}}
    {{else}}
    The file does not exist, so nothing to do.
    {{endif}}
    """

    def run(self):
        if not self.maker.exists(self.spec_filename):
            self.logger.notify("Skipping %s because %s does not exist" % (
                    self.name, self.spec_filename))
            return
        InstallSpec.run(self)

class ConditionalTask(Task):

    description = """
    Run subtasks based on a condition.  The tasks are:
    {{for cond, subtask in task.conditions}}
    {{if (cond, subtask) != task.conditions[0]}}el{{endif}}if {{cond}} ({{asbool(task.interpolate(cond))}}) {{subtask.name}}
    {{indent(str(subtask), '  ')}}
    {{endfor}}
    """

    def __init__(self, name, *conditions):
        super(ConditionalTask, self).__init__(name, stacklevel=2)
        self.conditions = conditions

    def run(self):
        pass

    def bind(self, *args, **kw):
        super(ConditionalTask, self).bind(*args, **kw)
        for cond, subtask in self.conditions:
            subtask.bind(*args, **kw)

    def iter_subtasks(self):
        for i in range(len(self.conditions)):
            cond, task = self.conditions[i]
            cond_resolved = asbool(self.interpolate(cond))
            if cond_resolved:
                self.logger.debug('%s is True: running %s' % (
                    cond, task.name))
                yield task
                for missed_cond, missed_task in self.conditions[i+1:]:
                    self.logger.debug('Skipping %s' % missed_task.name)
                break
            else:
                self.logger.debug('%s is False: not running %s' % (
                    cond, task.name))

class ForEach(Task):

    description = """
    Iterate over the values in {{task.value}} ({{task.values or 'no values'}}), setting task.{{task.variable}} for
    the task{{if len(task.tasks)>1}}s{{endif}}:
    {{for t in list(task.iter_subtasks()) or task.tasks:}}
      * {{t}}
    {{endfor}}
    """

    variable = interpolated('variable')

    def __init__(self, name, variable, value, tasks, stacklevel=1):
        super(ForEach, self).__init__(name, stacklevel=stacklevel+1)
        self.variable = variable
        self.value = value
        if not isinstance(tasks, (list, tuple)):
            tasks = [tasks]
        self.tasks = tasks

    @property
    def values(self):
        return [l.strip() for l in self.interpolate(self.value).splitlines() if l.strip()]

    def iter_subtasks(self):
        values = self.values
        if not values:
            self.logger.debug('No values in %s' % self.name)
            return
        for line in values:
            line = line.strip()
            if not line:
                continue
            for task in self.tasks:
                task_copy = copy.copy(task)
                setattr(task_copy, self.variable, line)
                yield task_copy

    def run(self):
        pass

class SetDistutilsValue(Task):

    description = """
    Patch {{task.distutils_cfg}}, setting [{{task.section}}] {{task.key}} = {{task.value}}
    {{if task.append}}If {{task.key}} is already defined, append to the current value{{endif}}
    """

    section = interpolated('section')
    key = interpolated('key')
    value = interpolated('value')

    def __init__(self, name, section, key, value, append=False, use_virtualenv=True, stacklevel=1):
        super(SetDistutilsValue, self).__init__(name, stacklevel=stacklevel+1)
        self.section = section
        self.key = key
        self.value = value
        self.append = append
        self.use_virtualenv = use_virtualenv
        self._distutils_filename = None

    def run(self):
        filename = self.distutils_cfg
        self.logger.notify('Patching file %s' % filename)
        if not self.maker.simulate:
            update_distutils_file(filename, self.section, self.key, self.value, self.logger, append=self.append)

    @property
    def distutils_cfg(self):
        if self._distutils_filename is None:
            if self.use_virtualenv:
                base = self.project.build_properties['virtualenv_lib_python']
                self._distutils_filename = os.path.join(base, 'distutils', 'distutils.cfg')
            else:
                self._distutils_filename = find_distutils_file(self.logger)
        return self._distutils_filename


class TestLxml(Task):

    description = """
    Tests that lxml built properly in {{task.path}}
    """

    path = interpolated('path')

    def __init__(self, path, stacklevel=1):
        super(TestLxml, self).__init__('Test lxml build', stacklevel+1)
        self.path = path
    
    def run(self):
        if self.maker.simulate:
            self.logger.notify('Would test lxml build in %s' % self.path)
            return
        if os.path.exists(self.path):
            proc = subprocess.Popen([os.path.join(self.path, 'bin/python'),
                                     '-c', '"from lxml import etree"'],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.communicate()
            if proc.wait() != 0:
                raise Exception('Lxml did not build properly')
            self.logger.notify('Lxml built properly')
        else:
            self.logger.warn('Tried to test lxml build in %s but the '
                             'path does not exist' % self.path)


class SaveCabochonSubscriber(Task):
    def __init__(self, events, use_base_port = False, stacklevel=1):
        super(SaveCabochonSubscriber, self).__init__('Save Cabochon Subscriber', stacklevel+1)
                
        assert events is not None, (
            "You must give a value for events")

        self.events = events
        self.use_base_port = use_base_port
        
    def run(self):
        if self.use_base_port:
            interp = lambda path : self.interpolate('http://{{config.host}}:{{general.base_port}}%s' % path)
        else:
            interp = lambda path : self.interpolate('http://{{config.host}}:{{config.port}}%s' % path)

        #new subscribers
        subscribers = dict()
        for event, subscriber in self.events.items():
            critical = None
            if type(subscriber) not in StringTypes:
                # it might be a tuple or a list to support the 'critical'
                # option
                critical = asbool(subscriber[1])
                subscriber = subscriber[0]
            if not event in subscribers:
                subscribers[event] = set()
            subscribers[event].add((interp(subscriber), critical))

        #existing subscribers
        cfg_filename = self.interpolate("{{env.var}}/cabochon_subscribers.cfg")
        try:
            f = open(cfg_filename, "r")

            for line in f:
                line = line.strip()
                splitline = line.split()
                event, subscriber = splitline[:2]
                critical = None
                if len(splitline) == 3:
                    critical = asbool(splitline[2])
                if not event in subscribers:
                    subscribers[event] = set()
                subscribers[event].add((subscriber, critical))
        except IOError:
            pass
        else:
            f.close()
        
        f = open(cfg_filename, "w")
        for event_type in subscribers:
            for subscriber, critical in subscribers[event_type]:
                if critical is None:
                    f.write("%s %s\n" % (event_type, subscriber))
                else:
                    f.write("%s %s %s\n" % (event_type, subscriber, str(critical)))
        f.close()


class InstallTarball(Task):

    dest_path = interpolated('dest_path')
    _tarball_url = ''
    _src_name = ''

    description = """
    Install {{task._src_name}} into {{task.dest_path}}.

    This downloads {{task._src_name}} from {{task._tarball_url}}.
    """

    def __init__(self, stacklevel=1):
        super(InstallTarball, self).__init__(
            'Install ' + self._src_name, stacklevel=stacklevel+1)
        self.dest_path = '{{env.base_path}}/{{project.name}}/src/{{task._src_name}}'


    def is_up_to_date(self):
        # subclasses can override if they want to be smart about
        # when to run.
        return False

    def post_unpack_hook(self):
        # subclasses can override if they want to do extra work or checks.
        pass
                         
    def run(self):
        if self.is_up_to_date():
            return
        url = self._tarball_url
        tmp_fn = os.path.abspath(os.path.basename(url))
        delete_tmp_fn = False
        try:
            if os.path.exists(tmp_fn):
                self.logger.notify('Source file %s already exists' % tmp_fn)
            else:
                self.logger.notify('Downloading %s to %s' % (url, tmp_fn))
                if not self.maker.simulate:
                    self.maker.retrieve(url, tmp_fn)
            self.maker.ensure_dir(os.path.dirname(self.dest_path))
            if tmp_fn.endswith('gz'):
                tarflags = 'zfx'
            elif tmp_fn.endswith('bz2'):
                tarflags = 'jfx'
            elif tmp_fn.endswith('tar'):
                tarflags = 'fx'
            else:
                raise Exception("Don't know how to untar file %r" % tmp_fn)
            self.maker.run_command(
                'tar', tarflags, tmp_fn,
                cwd=os.path.dirname(self.dest_path))
            self.post_unpack_hook()
            delete_tmp_fn = True
        finally:
            if delete_tmp_fn and os.path.exists(tmp_fn):
                os.unlink(tmp_fn)


class Log(Task):

    """Sometimes you might just want to tell the user something
    without creating an ad-hoc Task subclass.
    """

    def __init__(self, description, message, level='notify', stacklevel=1):
        self.message = message
        self.level = level
        super(Log, self).__init__(description, stacklevel=stacklevel+1)

    def run(self):
        text = self.interpolate(self.message)
        self.logger.log(self.level, text)

class WGetDirectory(Task):
    def __init__(self, name, repository, dest, stacklevel=1):
        super(WGetDirectory, self).__init__(name, stacklevel=stacklevel+1)
        self.repository = repository
        self.dest = dest

    def run(self):
        base = self.repository
        self.maker.run_command(['wget', '--no-check-certificate', '-i', base],
                               cwd=self.maker.path(dest))

class FetchRequirements(ConditionalTask):

    @property
    def requirements_use_wget(self):
        import pdb; pdb.set_trace()
        if self.config.has_option(self.project.name, 'requirements_use_wget'):
            _use_wget = asbool(self.config.get(self.project.name, 'requirements_use_wget'))
        else:
            _use_wget = asbool(self.config.getdefault('general', 'requirements_use_wget'))
        return _use_wget

    def __init__(self, name, *args, **kw):
        conditions = (('{{not task.requirements_use_wget}}',
                       SvnCheckout("%s (using svn checkout)" % name, *args, **kw)),
                      ('{{task.requirements_use_wget}}',
                       WGetDirectory("%s (using wget -i)" % name, *args, **kw)),
                      )
        super(FetchRequirements, self).__init__(name, *conditions)
