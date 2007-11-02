import sys
import os
import urlparse
from tempita import Template
import re

class Task(object):
    """
    Abstract base class for tasks
    """

    maker = None
    description = None

    def __init__(self, name, stacklevel=1):
        self.name = name
        self.position = self._stacklevel_position(stacklevel+1)

    def bind(self, maker, logger, config, project):
        self.maker = maker
        self.logger = logger
        self.config = config
        self.project = project
        self.config_section = project.config_section

    def confirm_settings(self):
        # Quick test that bind has been called
        assert self.maker is not None

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
        tmpl = Template(string, name=name, stacklevel=stacklevel+1)
        ns = self.create_namespace()
        ## FIXME: show the ns if this fails:
        return tmpl.substitute(ns.dict)

    def create_namespace(self):
        ns = self.project.create_namespace()
        ns['task'] = self
        return ns

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
        return self.interpolate(self.description)

class interpolated(object):
    def __init__(self, name):
        self.name = name
    def __get__(self, obj, type=None):
        ## FIXME: I *could* return a string subclass that gives access to the raw value too
        if obj is None:
            return self
        raw_value = getattr(obj, '_' + self.name)
        return obj.interpolate(raw_value, name=obj.position + (' attribute %s' % self.name))
    def __set__(self, obj, value):
        ## FIXME: nice to compile the template here too
        setattr(obj, '_' + self.name, value)
    def __del__(self, obj, value):
        delattr(obj, '_' + self.name)
    def __repr__(self):
        return '<%s for attribute %s>' % (
            self.__class__.__name__, self.name)

class Process(Task):
    """
    Run a process
    """

    description = """
    Run the process {{task.script}}{{if task.cwd}} in {{task.cwd}}{{endif}}.
    {{if task.extra_args}}Also call run_command with keyword arguments {{task.extra_args}}{{endif}}
    """

    script = interpolated('script')
    cwd = interpolated('cwd')

    def __init__(self, name, script, cwd=None, stacklevel=1,
                 **extra_args):
        super(Process, self).__init__(name, stacklevel=stacklevel+1)
        self.script = script
        self.cwd = cwd
        self.extra_args = extra_args

    def run(self):
        self.maker.run_command(self.script, cwd=self.cwd, **self.extra_args)


class CopyDir(Task):
    """
    Copy files
    """

    description = """
    Copy the files from {{task.source}} to {{task.dest}}.
    """

    source = interpolated('source')
    dest = interpolated('dest')

    def __init__(self, name, source, dest, stacklevel=1):
        super(CopyDir, self).__init__(name, stacklevel=stacklevel+1)
        self.source = source
        self.dest = dest

    def run(self):
        self.maker.copy_dir(self.source, self.dest, template_vars=self.create_namespace().dict)

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
                 create_if_necessary=True, stacklevel=1):
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
        dest = self.dest
        if self.maker.exists(dest):
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
        else:
            self.maker.run_command(['svn', 'checkout', full_repo, dest])

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
