import sys
import os
import urlparse
from tempita import Template
import re
from glob import glob
from fassembler.filemaker import RunCommandError

class Task(object):
    """
    Abstract base class for tasks
    """

    maker = None
    description = None

    def __init__(self, name, stacklevel=1):
        self.name = name
        self.position = self._stacklevel_position(stacklevel+1)

    @property
    def title(self):
        return '%s  (%s.%s)' % (self.name, self.__class__.__module__, self.__class__.__name__)

    def bind(self, maker, environ, logger, config, project):
        self.maker = maker
        self.environ = environ
        self.logger = logger
        self.config = config
        self.project = project
        self.config_section = project.config_section

    def confirm_settings(self):
        # Quick test that bind has been called
        assert self.maker is not None

    def setup_build_properties(self):
        """
        Called early on to set any project.build_properties that other tasks might need.
        """

    def run(self):
        raise NotImplementedError

    def interpolate(self, string, stacklevel=1, name=None):
        if string is None:
            return None
        if isinstance(string, (list, tuple)):
            new_items = []
            for item in string:
                new_items.append(self.interpolate(item, stacklevel+1, name=name))
            return new_items
        if isinstance(string, dict):
            new_dict = {}
            for key in string:
                new_dict[self.interpolate(key, stacklevel+1, name=name)] = self.interpolate(
                    string[key], stacklevel+1, name=name)
            return new_dict
        if not isinstance(string, Template):
            tmpl = Template(string, name=name, stacklevel=stacklevel+1)
        else:
            tmpl = string
        ns = self.create_namespace()
        return ns.execute_template(tmpl)

    def create_namespace(self):
        ns = self.project.create_namespace()
        ns['task'] = self
        return ns

    def copy_dir(self, *args, **kw):
        self._run_fill_method('copy_dir', *args, **kw)
    def copy_file(self, *args, **kw):
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
        prop = self.project.build_properties.get('virtualenv_%s' % name)
        if not prop:
            raise Exception(
                "You must run a VirtualEnv task before this task")
        return prop

    def __str__(self):
        if self.description is None:
            return repr(self)
        if self.maker is None:
            return repr(self).lstrip('>') + ' (unbound)>'
        try:
            return self.interpolate(self.description, name='description of %s' % self.__class__.__name__)
        except Exception, e:
            return '%s (error in description: %s)>' % (repr(self).rstrip('>'), e)

class interpolated(object):
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
    """

    script = interpolated('script')
    cwd = interpolated('cwd')

    def __init__(self, name, script, cwd=None, stacklevel=1, use_virtualenv=False,
                 **extra_args):
        super(Script, self).__init__(name, stacklevel=stacklevel+1)
        self.script = script
        self.cwd = cwd
        self.use_virtualenv = use_virtualenv
        self.extra_args = extra_args

    def run(self):
        script = self.script
        kw = self.extra_args.copy()
        if self.use_virtualenv:
            kw['script_abspath'] = self.venv_property('bin_path')
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

    def __init__(self, name, source, dest, stacklevel=1):
        super(CopyDir, self).__init__(name, stacklevel=stacklevel+1)
        self.source = source
        self.dest = dest

    def run(self):
        self.logger.info(
            'Copying %s to %s' % (self.source, self.dest))
        self.copy_dir(self.source, self.dest)

class EnsureFile(Task):
    """
    Write a single file
    """

    description = """
    Write the file {{task.dest}} with the given content ({{len(task.content)}} bytes/{{len(task.content.splitlines())}} lines).
    {{if not task.overwrite:}}
    If {{task.dest}} already exists{{if maker.exists(task.dest)}} (and it does){{endif}}, do not overwrite it.
    {{endif}}
    {{if task.svn_add}}
    If {{os.path.dirname(task.dest)}} is an svn checkout, this file will be added.
    {{endif}}
    {{if task.executable}}
    The file will be made executable.
    {{endif}}
    """

    dest = interpolated('dest')
    content = interpolated('content')

    def __init__(self, name, dest, content, overwrite=False, svn_add=False,
                 executable=False, stacklevel=1):
        super(EnsureFile, self).__init__(name, stacklevel=stacklevel+1)
        self.dest = dest
        self.content = content
        self.overwrite = overwrite
        self.svn_add = svn_add
        self.executable = executable

    def run(self):
        if not self.overwrite and self.maker.exists(self.dest):
            self.logger.notify('File %s already exists; not overwriting' % self.dest)
            return
        self.maker.ensure_file(self.dest, self.content, svn_add=self.svn_add,
                               overwrite=self.overwrite, executable=self.executable)

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
    """

    repository = interpolated('repository')
    dest = interpolated('dest')
    base_repository = interpolated('base_repository')

    def __init__(self, name, repository, dest, base_repository=None,
                 create_if_necessary=False, stacklevel=1):
        super(SvnCheckout, self).__init__(name, stacklevel=stacklevel+1)
        self.repository = repository
        self.dest = dest
        self.base_repository = base_repository
        self.create_if_necessary = create_if_necessary

    @property
    def full_repository(self):
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
            self.confirm_directory(full_repo)
        self.maker.checkout_svn(full_repo, self.dest)

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
        else:
            self.logger.debug('repository directory %s exists' % repo)


## FIXME: I need to find a way to make this faster, and avoid recreating a perfectly fine virtualenv
class VirtualEnv(Task):
    """
    Create a virtualenv environment
    """

    description = """
    Create a virtualenv environment in {{maker.path(task.path or project.name)}}
    {{if not task.path}} ({{project.name}} is the project name){{endif}}

    {{if os.path.exists(task.path_resolved):}}
    Directory already exists.
    {{if project.config.getdefault('DEFAULT', 'force_virtualenv'):}}
    Because force_virtualenv is set, the virtualenv will be recreated.
    {{else}}
    Because force_virtualenv is not set, the virtualenv (re)creation will be skipped.
    {{endif}}
    {{endif}}
    """

    def __init__(self, name='Create virtualenv', path=None, stacklevel=1):
        super(VirtualEnv, self).__init__(name, stacklevel=stacklevel+1)
        self.path = path

    @property
    def path_resolved(self):
        return self.maker.path(self.path or self.project.name)

    def run(self):
        path = self.path_resolved
        if os.path.exists(path) and os.path.exists(os.path.join(path, 'lib')):
            if not self.project.config.getdefault('DEFAULT', 'force_virtualenv'):
                self.logger.notify('Skipping virtualenv creation as directory %s exists' % path)
                return
            else:
                self.logger.notify('Forcing virtualenv recreation')
        import virtualenv
        ## FIXME: kind of a nasty hack
        virtualenv.logger = self.logger
        self.logger.level_adjust -= 2
        try:
            virtualenv.create_environment(path)
        finally:
            self.logger.level_adjust += 2
        self.logger.notify('virtualenv created in %s' % path)

    def setup_build_properties(self):
        path = self.path_resolved
        assert path, "no path (%r)" % path
        props = self.project.build_properties
        ## FIXME: doesn't work on Windows:
        props['virtualenv_path'] = path
        props['virtualenv_bin_path'] = os.path.join(path, 'bin')
        props['virtualenv_python'] = os.path.join(path, 'bin', 'python')
        props['virtualenv_src_path'] = os.path.join(path, 'src')
        props['virtualenv_lib_python'] = os.path.join(path, 'lib', 'python%s' % sys.version[:3])


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
            for find_link in find_links:
                self.reqs[:0] = ['-f', find_link]
        kw['stacklevel'] = kw.get('stacklevel', 1)+1
        super(EasyInstall, self).__init__(name, ['easy_install'] + list(self.reqs), use_virtualenv=True, **kw)

class SourceInstall(SvnCheckout):
    """
    Install from svn source
    """
    ## FIXME: this should support other version control systems someday,
    ## maybe using the setuptools entry point for version control.

    description = """
    Checkout out {{task.repository}} into src/{{task.checkout_name}}/,
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
    Install a Paste configuration file in etc/{{project.name}}/{{project.name}}.ini
    from {{if task.template}}a static template{{else}}the file {{task.path}}{{endif}}
    """

    def __init__(self, template=None, path=None, name='Install Paste configuration',
                 stacklevel=1):
        super(InstallPasteConfig, self).__init__(name, stacklevel=stacklevel+1)
        assert path or template, "You must give one of path or template"
        self.path = path
        self.template = template

    def run(self):
        dest = os.path.join('etc', self.project.name, self.project.name+'.ini')
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

    def __init__(self, name='Install Paste startup script', stacklevel=1):
        super(InstallPasteStartup, self).__init__(name, stacklevel=stacklevel+1)

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
exec paster serve {{env.base_path}}/etc/{{project.name}}/{{project.name}}.ini "$@"
"""

class InstallSupervisorConfig(Task):

    description = """
    Install standard supervisor template into {{task.conf_path}}
    """

    def __init__(self, name='Install supervisor startup script', stacklevel=1):
        super(InstallSupervisorConfig, self).__init__(name, stacklevel=stacklevel+1)

    @property
    def conf_path(self):
        return os.path.join('etc', 'supervisor.d', self.project.name + '.ini')

    def run(self):
        self.maker.ensure_file(
            self.conf_path,
            self.content,
            executable=True)
        self.logger.notify('Supervisor config written to %s' % self.conf_path)

    @property
    def content(self):
        return self.interpolate(self.content_template, name=__name__+'.InstallSupervisorConfig.content_template')

    content_template = """\
[program:{{task.project.name}}]
command = {{env.base_path}}/bin/start-{{task.project.name}}
{{#FIXME: should set user=username}}
stdout_logfile = {{env.base_path}}/logs/{{task.project.name}}/{{task.project.name}}-supervisor.log
stdout_logfile_maxbytes = 1MB
stdout_logfile_backups = 10
stderr_logfile = {{env.base_path}}/logs/{{task.project.name}}/{{task.project.name}}-supervisor-errors.log
stderr_logfile_maxbytes = 1MB
stderr_logfile_backups = 10
"""

class CheckMySQLDatabase(Task):

    db_name = interpolated('db_name')
    db_host = interpolated('db_host')
    db_username = interpolated('db_username')
    db_password = interpolated('db_password')
    db_root_password = interpolated('db_root_password')

    description = """
    Check that the database {{task.db_name}}@{{task.db_host}} exists
    (accessing it with u/p {{config.db_username}}/{{repr(config.db_password)}}).
    If it does not exist, create the database.  If the databsae does
    exist, make sure that the user has full access.

    This will connect as root to create the database if necessary,
    using {{if not task.db_root_password}}no password{{else}}the password {{repr(task.db_root_password)}}{{endif}}
    """

    def __init__(self, name, db_name='{{config.db_name}}',
                 db_host='{{config.db_host}}', db_username='{{config.db_username}}',
                 db_password='{{config.db_password}}', db_root_password='{{config.db_root_password}}',
                 stacklevel=1):
        super(CheckMySQLDatabase, self).__init__(name, stacklevel=stacklevel+1)
        self.db_name = db_name
        self.db_host = db_host
        self.db_username = db_username
        self.db_password = db_password
        self.db_root_password = db_root_password

    password_error = 1045
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
            elif code == self.password_error:
                # Could be a database name problem, or access
                self.logger.notify(
                    "Cannot connect to %s@%s"
                    % (self.db_name, self.db_host))
            elif code == self.unknown_database:
                self.logger.notify(
                    "Database %s does not exist" % self.db_name)
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
        import MySQLdb
        try:
            conn = self.root_connection()
        except MySQLdb.OperationalError, e:
            code = e.args[0]
            if code == self.password_error:
                self.logger.fatal("The root password %r is incorrect" % (self.db_root_password or '(no password)'))
                ## FIXME: I don't like raise here:
                raise
            elif code == self.unknown_database:
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
            **self.passkw(self.db_root_password))
        plan = 'CREATE DATABASE %s' % self.db_name
        self.logger.info('Executing %s' % plan)
        if not self.maker.simulate:
            conn.cursor().execute(plan)
        conn.close()

    def change_permissions(self):
        conn = self.root_connection()
        plan = "GRANT ALL PRIVILEGES ON %s.* TO %s IDENTIFIED BY %r" % (
            self.db_name, self.db_username, self.db_password)
        self.logger.info('Executing %s' % plan)
        if not self.maker.simulate:
            conn.cursor().execute(
                "GRANT ALL PRIVILEGES ON %s.* TO %s IDENTIFIED BY %%s"
                % (self.db_name, self.db_username),
                (self.db_password,))
        conn.close()

    def root_connection(self):
        import MySQLdb
        return MySQLdb.connect(
            host=self.db_host,
            db=self.db_name,
            user='root',
            **self.passkw(self.db_root_password))
        
        
class SaveSetting(Task):
    """
    Save a setting in build.ini
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
                 overwrite_if_empty=True, stacklevel=1):
        assert isinstance(variables, dict), (
            "The variables parameter should be a dictionary")
        super(SaveSetting, self).__init__(name, stacklevel=stacklevel+1)
        self.variables = variables
        self.section = section
        self.overwrite_if_empty = overwrite_if_empty

    def run(self):
        if not self.environ.config.has_section(self.section):
            self.environ.config.add_section(self.section)
        for key, value in self.variables.items():
            if isinstance(key, (tuple, list)):
                section, key = key
            else:
                section = self.section
            self.environ.config.set(section, key, value)

    def format_variables(self, variables):
        keys = sorted(variables)
        default_section = self.section
        output = []
        for key in keys:
            if isinstance(key, (tuple, list)):
                section, key = key
            else:
                section = default_section
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
                 theme=True,
                 trailing_slash=True,
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
        if not theme:
            variables['{{task.project_name}} theme'] = 'false'
        if not trailing_slash:
            variables['{{task.project_name}} trailing_slash'] = 'false'
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
                ## FIXME: on failure, it would be nice to show the patch and dest file
            finally:
                self.logger.indent -= 2

    @property
    def expanded_files(self):
        return self.expand_globs(self.files)

    def expand_globs(self, files):
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
    {{for line in open(task.spec_filename):}}
    {{py: line = line.strip()}}
    {{if line.startswith('-e') or line.startswith('--editable'):}}* svn checkout {{line.split(None, 1)[1]}}{{else}}* {{line}}{{endif}}{{endfor}}
    """

    spec_filename = interpolated('spec_filename')

    def __init__(self, name, spec_filename, stacklevel=1):
        super(InstallSpec, self).__init__(name, stacklevel=stacklevel+1)
        self.spec_filename = spec_filename

    def run(self):
        context, commands = self.read_commands()
        context['virtualenv_python'] = self.project.build_properties['virtualenv_python']
        extra_commands = []
        for command, arg in commands:
            result = command(context, arg)
            if result:
                extra_commands.append(result)
        for command, arg in extra_commands:
            command(context, arg)

    def read_commands(self, filename=None):
        if filename is None:
            filename = self.spec_filename
        self.logger.debug('Reading spec %s' % filename)
        f = open(filename)
        context = dict(find_links=[],
                       src_base=os.path.join(self.project.build_properties['virtualenv_path'], 'src'))
        commands = []
        uneditable_eggs = []
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('-f') or line.startswith('--find-links'):
                if line.startswith('-f'):
                    line = line[2:]
                else:
                    line = line[len('--find-links'):].lstrip('=')
                context['find_links'].append(line.strip())
                continue
            if line.startswith('-e') or line.startswith('--editable'):
                if uneditable_eggs:
                    commands.append((self.install_eggs, uneditable_eggs))
                    uneditable_eggs = []
                if line.startswith('-e'):
                    line = line[2:]
                else:
                    line = line[len('--editable'):].lstrip('=')
                commands.append((self.install_editable, line.strip()))
                continue
            uneditable_eggs.append(line.strip())
        if uneditable_eggs:
            commands.append((self.install_eggs, uneditable_eggs))
        return context, commands

    _rev_svn_re = re.compile(r'@(\d+)$')
    _egg_spec_re = re.compile(r'egg=([^-=&]*)')

    def install_editable(self, context, svn):
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
        self.maker.checkout_svn(svn, dest, revision=revision)
        self.maker.run_command(
            'python', 'setup.py', 'develop', '--no-deps',
            cwd=dest,
            script_abspath=self.venv_property('bin_path'))
        return self.install_finalize_editable, dest

    def install_finalize_editable(self, context, src_dir):
        cmd = ['python', 'setup.py', 'develop']
        for link in context['find_links']:
            cmd.extend(['-f', link])
        self.maker.run_command(
            cmd,
            cwd=src_dir,
            script_abspath=self.venv_property('bin_path'))

    def install_eggs(self, context, eggs):
        cmd = ['easy_install']
        for link in context['find_links']:
            cmd.extend(['-f', link])
        cmd.extend(eggs)
        self.maker.run_command(
            cmd,
            cwd=self.venv_property('path'),
            script_abspath=self.venv_property('bin_path'))
            
