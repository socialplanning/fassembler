import sys
import os
import urlparse
from tempita import Template
import re
from glob import glob

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

    def run(self, quick):
        raise NotImplementedError

    def interpolate(self, string, stacklevel=1, name=None):
        if string is None:
            return None
        if isinstance(string, (list, tuple)):
            new_items = []
            for item in string:
                new_items.append(self.interpolate(item, stacklevel+1, name=name))
            return new_items
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
      {{if task.cwd}}in {{task.cwd}}{{endif}}
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

    def run(self, quick):
        script = self.script
        if self.use_virtualenv:
            venv_path = self.project.build_properties.get('virtualenv_bin_path')
            if not venv_path:
                raise Exception(
                    "You must run a VirtualEnv task before Script if use_virtualenv=True")
            script = self.abspath_script(venv_path, script)
        self.maker.run_command(script, cwd=self.cwd, **self.extra_args)

    def abspath_script(self, path, script):
        is_string = isinstance(script, basestring)
        if is_string:
            # Shell-style string command
            try:
                first, rest = script.split(None, 1)
            except ValueError:
                first, rest = script, ''
        else:
            first, rest = script[0], script[1:]
        first = os.path.join(path, first)
        if is_string:
            return '%s %s' % (first, rest)
        else:
            return [first] + rest


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

    def run(self, quick):
        self.copy_dir(self.source, self.dest)

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
    If the directory at {{task.full_repository}} does not exist, it will be created.
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

    def run(self, quick):
        base = self.base_repository
        if base and self.create_if_necessary and base.startswith('file:'):
            self.confirm_repository(base)
        full_repo = self.full_repository
        if self.create_if_necessary:
            self.confirm_directory(full_repo)
        dest = self.dest
        if self.maker.exists(dest):
            if quick:
                self.logger.notify('Checkout %s exists; skipping update' % dest)
                return
            current_repo = self.get_repo_url(dest)
            self.logger.debug('There is a repository at %s from %s'
                              % (dest, current_repo))
            if current_repo != full_repo:
                self.logger.debug("The repository at %s isn't from the expected location %s"
                                  % (dest, full_repo))
                if self.maker.interactive:
                    response = self.maker.ask(
                        'At %s there is already a checkout from %s\n'
                        'The expected repository is %s\n'
                        'What should I do?'
                        % (dest, current_repo, full_repo),
                        responses=['(i)gnore',
                                   '(s)witch',
                                   '(b)ackup',
                                   '(w)ipe'])
                    if response == 'i':
                        self.logger.warn('Ignoring svn repository differences')
                    elif response == 's':
                        self.logger.warn('Switching repository locations')
                        self.maker.run_command(
                            ['svn', 'switch', '--relocate',
                             current_repo, full_repo, dest])
                    elif response == 'b' or response == 'w':
                        if response == 'b':
                            self.maker.backup(dest)
                        else:
                            self.logger.warn('Deleting checkout %s' % dest)
                        self.maker.rmtree(dest)
                    else:
                        assert 0, response
        if os.path.exists(dest):
            self.maker.run_command(['svn', 'update', dest])
            self.logger.notify('Updated repository at %s' % dest)
        else:
            ## FIXME: dot progress?
            self.maker.run_command(['svn', 'checkout', full_repo, dest])
            self.logger.notify('Checked out repository to %s' % dest)

    _repo_url_re = re.compile(r'^URL:\s+(.*)$', re.MULTILINE)

    def get_repo_url(self, path):
        """
        Get the subversion URL that path was checked out from
        """
        ## FIXME: ideally we'd set LANG or something, as the output
        ## can get i18n'd
        stdout = self.maker.run_command(['svn', 'info', path])
        match = self._repo_url_re.search(stdout)
        if not match:
            raise ValueError(
                "Could not determine svn URL of %s; output:\n%s"
                % (path, stdout))
        return match.group(1).strip()

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


class VirtualEnv(Task):
    """
    Create a virtualenv environment
    """

    description = """
    Create a virtualenv environment in {{maker.path(task.path or project.name)}}
    {{if not task.path}} ({{project.name}} is the project name){{endif}}
    """

    def __init__(self, name='Create virtualenv', path=None, stacklevel=1):
        super(VirtualEnv, self).__init__(name, stacklevel=stacklevel+1)
        self.path = path

    def run(self, quick):
        path = self.maker.path(self.path or self.project.name)
        if quick and os.path.exists(path):
            self.logger.notify('Skipping virtualenv creation as directory %s exists' % path)
            self.set_props(path)
            return
        import virtualenv
        ## FIXME: kind of a nasty hack
        virtualenv.logger = self.logger
        self.logger.level_adjust -= 2
        try:
            virtualenv.create_environment(path)
        finally:
            self.logger.level_adjust += 2
        self.set_props(path)

    def set_props(self, path):
        props = self.project.build_properties
        ## FIXME: doesn't work on Windows:
        props['virtualenv_path'] = path
        props['virtualenv_bin_path'] = os.path.join(path, 'bin')
        props['virtualenv_src_path'] = os.path.join(path, 'src')
        self.logger.notify('virtualenv created in %s' % path)


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

    def run(self, quick):
        super(SourceInstall, self).run(quick)
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

    def run(self, quick):
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
    ## FIXME: should also create supervisor file

    def __init__(self, name='Install Paste startup script', stacklevel=1):
        super(InstallPasteStartup, self).__init__(name, stacklevel=stacklevel+1)

    def run(self, quick):
        path = os.path.join('bin', self.project.name+'.rc')
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

    def run(self, quick):
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
    Save the setting [{{task.section}}] {{task.var_name}} = {{repr(tast.value)}} in build.ini
    """

    value = interpolated('value')
    var_name = interpolated('var_name')
    section = interpolated('section')

    def __init__(self, name, var_name, value, section='general', stacklevel=1):
        super(SaveSetting, self).__init__(name, stacklevel=stacklevel+1)
        self.var_name = var_name
        self.value = value
        self.section = section

    def run(self, quick):
        if not self.environ.config.has_section(self.section):
            self.environ.config.add_section(self.section)
        self.environ.config.set(self.section, self.var_name, self.value)

class SaveURL(SaveSetting):

    def __init__(self, name='Save URL setting', var_name='{{project.name}}_url',
                 value='http://{{config.host}}:{{config.port}}', section='urls',
                 stacklevel=1):
        super(SaveURL, self).__init__(name, var_name=var_name,
                                      value=value, section=section, stacklevel=stacklevel+1)
class Patch(Task):

    files = interpolated('files')
    dest = interpolated('dest')
    strip = interpolated('strip')

    description = """
    Patch the files {{', '.join(config.files)}}
    {{if config.expanded_files != config.files}}(expanded to {{', '.join(config.expanded_files)}}){{endif}}
    Patches applied to {{config.dest}}, -p {{task.strip}}.
    """

    def __init__(self, name, files, dest, strip='0', stacklevel=1):
        super(Patch, self).__init__(name, stacklevel=stacklevel+1)
        if isinstance(files, basestring):
            files = [files]
        self.files = files
        self.dest = dest
        self.strip = strip

    _rejects_regex = re.compile('rejects to file (.*)')

    def run(self, quick):
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

