# (c) 2005 Ian Bicking and contributors; written for Paste (http://pythonpaste.org)
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
import os
import glob
import subprocess
from difflib import unified_diff, context_diff

class Maker(object):
    """
    Enhance the ease of file copying/processing from a package into a target
    project
    """
    
    def __init__(self, base_dir, logger,
                 simulate=False, 
                 interactive=True):
        """
        Initialize the Maker.  Files go under base_dir.
        """
        self.base_dir = self._normpath(base_dir)
        self.logger = logger
        self.simulate = simulate
        self.interactive = interactive
    
    def copy_file(self, src, dest=None, dest_dir=None, template_vars=None):
        """
        Copy a file from the source location to somewhere in the
        destination.

        If the file ends with _tmpl, then that suffix will be removed
        and the file will be filled as a template.  You must provide
        template_vars in this case.
        """
        assert not dest or not dest_dir
        assert dest or dest_dir
        if dest_dir:
            dest = os.path.join(dest_dir, os.path.basename(src))
            if src.endswith('_tmpl'):
                dest = dest[:-5]
        dest = self.path(self.base_dir, dest)
        self._warn_filename(dest)
        contents, raw_contents = self.get_contents(src, template_vars)
        if os.path.exists(dest):
            existing = self.get_raw_contents(dest)
            if existing == contents:
                self.logger.notify('File %s exists with same content' % self.display_path(dest))
            else:
                message = 'File %s already exists (with different content)' % self.display_path(dest)
                if os.path.exists(dest + '.orig'):
                    existing_raw = self.get_raw_contents(dest + '.orig')
                    if existing_raw == raw_contents:
                        message = (
                            'File %s already exists (with different substitutions, but same original template)'
                            % self.display_path(dest))
                if self.interactive:
                    response = self.ask_difference(dest, message, contents, existing)
                    if not response:
                        self.logger.notify('Aborting copy')
                        return

        self.ensure_file(dest, content)
        if contents != raw_contents:
            self.ensure_file(dest+'.orig', raw_contents)

    def get_contents(self, filename, template_vars=None):
        is_tmpl = filename.endswith('_tmpl')
        if is_tmpl and template_vars is None:
            raise ValueError(
                "You must provide template_vars to fill a file (filename=%r)"
                % filename)
        raw_contents = contents = self.get_raw_contents(filename)
        if is_tmpl:
            contents = self.fill(contents, template_vars, filename=filename)
        return contents, raw_contents

    def get_raw_contents(self, filename):
        f = open(filename, 'rb')
        try:
            return f.read()
        finally:
            f.close()

    def _writefile(self, filename, contents):
        self.logger.debug('Writing %i bytes to %s' %
                          (len(contents), filename))
        f = open(filename, 'wb')
        f.write(contents)
        f.close()

    def fill(self, contents, template_vars, filename=filename):
        ## FIXME: catch expected errors here, show available variables
        tmpl = tempita.Template(content, name=filename)
        return tmpl.substitute(template_vars)

    def path(self, path):
        return os.path.join(self.base_path, path)

    def display_path(self, path):
        path = self._normpath(path)
        if path.startswith(self.base_path):
            path = path[len(self.base_path):].lstrip(os.path.sep)
        return path

    def _warn_filename(self, filename):
        """
        Issues a warning if the filename is outside base_dir
        """
        filename = self._normpath(filename)
        if not filename.startswith(self.base_dir):
            self.logger.warn('Writing to file outside base directory: %s' % filename)

    def _normpath(self, path):
        return os.path.normcase(os.path.abspath(path))
    
    def copy_dir(self, src, dest, sub_filenames=True, template_vars=None, include_hidden=False):
        """
        Copy a directory recursively, processing any files within it
        that need to be processed (end in _tmpl).
        """
        if template_vars is None:
            sub_filenames = False
        for dirpath, dirnames, filenames in os.walk(src):
            for dirname in dirnames:
                if not include_hidden and self.is_hidden(dirname):
                    self.logger.debug('Skipping hidden directory %s' % dirname)
                    continue
                destdir = self.path(os.path.join(dirpath, dirname))
                if sub_filenames:
                    orig_destdir = destdir
                    destdir = self.fill_filename(destdir, template_vars)
                    if orig_destdir != destdir:
                        logger.debug('Filling name %s to %s' % (orig_destdir, destdir))
                self.ensure_dir(destdir)
            for filename in filenames:
                if not include_hidden and self.is_hidden(filename):
                    self.logger.debug('Skipping hidden file %s' % filename)
                    continue
                destfn = self.path(os.path.join(dirpath, filename))
                if sub_filenames:
                    orig_destfn = destfn
                    destfn = self.fill_filename(destfn, template_vars)
                    if orig_destfn != destfn:
                        logger.debug('Filling name %s to %s' % (orig_destfn, destfn))
                self.copy_file(os.path.join(src, dirpath, filename), destfn, template_vars=template_vars)

    _filename_var_re = re.compile(r'[+](.*?)[+]')

    def fill_filename(self, filename, template_vars):
        ## FIXME: should add standard variables
        def subber(match):
            name = match.group(1)
            if name not in template_vars:
                raise NameError(
                    "Variable +%s+ not in variables, in filename %s"
                    % (name, filename))
            return template_vars[name]
        return self._filename_var.sub(subber, filename)
    
    def ensure_dir(self, dir, svn_add=True, package=False):
        """
        Ensure that the directory exists, creating it if necessary.
        Respects verbosity and simulation.

        Adds directory to subversion if ``.svn/`` directory exists in
        parent, and directory was created.
        
        package
            If package is True, any directories created will contain a
            __init__.py file.
        
        """
        dir = dir.rstrip(os.sep)
        if not dir:
            # we either reached the parent-most directory, or we got
            # a relative directory
            # @@: Should we make sure we resolve relative directories
            # first?  Though presumably the current directory always
            # exists.
            return
        if not os.path.exists(dir):
            self.ensure_dir(os.path.dirname(dir), svn_add=svn_add, package=package)
            if self.verbose:
                print 'Creating %s' % self.display_path(dir)
            if not self.simulate:
                os.mkdir(dir)
            if (svn_add and
                os.path.exists(os.path.join(os.path.dirname(dir), '.svn'))):
                self.svn_command('add', dir)
            if package:
                initfile = os.path.join(dir, '__init__.py')
                f = open(initfile, 'wb')
                f.write("#\n")
                f.close()
                print 'Creating %s' % self.display_path(initfile)
                if (svn_add and
                    os.path.exists(os.path.join(os.path.dirname(dir), '.svn'))):
                    self.svn_command('add', initfile)
        else:
            if self.verbose > 1:
                print "Directory already exists: %s" % self.display_path(dir)

    def ensure_file(self, filename, content, svn_add=True, package=False):
        """
        Ensure a file named ``filename`` exists with the given
        content.  If ``--interactive`` has been enabled, this will ask
        the user what to do if a file exists with different content.
        """
        global difflib
        self.ensure_dir(os.path.dirname(filename), svn_add=svn_add, package=package)
        if not os.path.exists(filename):
            if self.verbose:
                print 'Creating %s' % filename
            if not self.simulate:
                f = open(filename, 'wb')
                f.write(content)
                f.close()
            if svn_add and os.path.exists(os.path.join(os.path.dirname(filename), '.svn')):
                self.svn_command('add', filename)
            return
        f = open(filename, 'rb')
        old_content = f.read()
        f.close()
        if content == old_content:
            if self.verbose > 1:
                print 'File %s matches expected content' % filename
            return
        if not self.options.overwrite:
            print 'Warning: file %s does not match expected content' % filename
            if difflib is None:
                import difflib
            diff = difflib.context_diff(
                content.splitlines(),
                old_content.splitlines(),
                'expected ' + filename,
                filename)
            print '\n'.join(diff)
            if self.interactive:
                while 1:
                    s = raw_input(
                        'Overwrite file with new content? [y/N] ').strip().lower()
                    if not s:
                        s = 'n'
                    if s.startswith('y'):
                        break
                    if s.startswith('n'):
                        return
                    print 'Unknown response; Y or N please'
            else:
                return
                    
        if self.verbose:
            print 'Overwriting %s with new content' % filename
        if not self.simulate:
            f = open(filename, 'wb')
            f.write(content)
            f.close()

    _svn_failed = False

    def svn_command(self, *args, **kw):
        """
        Run an svn command, but don't raise an exception if it fails.
        """
        try:
            return self.run_command('svn', *args, **kw)
        except OSError, e:
            if not self._svn_failed:
                print 'Unable to run svn command (%s); proceeding anyway' % e
                self._svn_failed = True

    def run_command(self, cmd, *args, **kw):
        """
        Runs the command, respecting verbosity and simulation.
        Returns stdout, or None if simulating.
        """
        cwd = popdefault(kw, 'cwd', self.base_dir)
        capture_stderr = popdefault(kw, 'capture_stderr', False)
        expect_returncode = popdefault(kw, 'expect_returncode', False)
        assert not kw, ("Arguments not expected: %s" % kw)
        if capture_stderr:
            stderr_pipe = subprocess.STDOUT
        else:
            stderr_pipe = subprocess.PIPE
        try:
            proc = subprocess.Popen([cmd] + list(args),
                                    cwd=cwd,
                                    stderr=stderr_pipe,
                                    stdout=subprocess.PIPE)
        except OSError, e:
            if e.errno != 2:
                # File not found
                raise
            raise OSError(
                "The expected executable %s was not found (%s)"
                % (cmd, e))
        if self.verbose:
            print 'Running %s %s' % (cmd, ' '.join(args))
        if self.simulate:
            return None
        stdout, stderr = proc.communicate()
        if proc.returncode and not expect_returncode:
            if not self.verbose:
                print 'Running %s %s' % (cmd, ' '.join(args))
            print 'Error (exit code: %s)' % proc.returncode
            if stderr:
                print stderr
            raise OSError("Error executing command %s" % cmd)
        if self.verbose > 2:
            if stderr:
                print 'Command error output:'
                print stderr
            if stdout:
                print 'Command output:'
                print stdout
        return stdout

    all_answer = None

    def ask_difference(self, dest_fn, new_contents, cur_content):
        u_diff = list(unified_diff(
            new_content.splitlines(),
            cur_content.splitlines(),
            dest_fn, dest_fn))
        c_diff = list(context_diff(
            new_content.splitlines(),
            cur_content.splitlines(),
            dest_fn, dest_fn))
        added = len([l for l in u_diff if l.startswith('+')
                       and not l.startswith('+++')])
        removed = len([l for l in u_diff if l.startswith('-')
                       and not l.startswith('---')])
        if added > removed:
            msg = '; %i lines added' % (added-removed)
        elif removed > added:
            msg = '; %i lines removed' % (removed-added)
        else:
            msg = ''
        print 'Replace %i bytes with %i bytes (%i/%i lines changed%s)' % (
            len(cur_content), len(new_content),
            removed, len(cur_content.splitlines()), msg)
        prompt = 'Overwrite %s [y/n/d/B/?] ' % dest_fn
        while 1:
            if self.all_answer is None:
                response = raw_input(prompt).strip().lower()
            else:
                response = self.all_answer
            if not response or response[0] == 'b':
                import shutil
                new_dest_fn = dest_fn + '.bak'
                n = 0
                while os.path.exists(new_dest_fn):
                    n += 1
                    new_dest_fn = dest_fn + '.bak' + str(n)
                print 'Backing up %s to %s' % (dest_fn, new_dest_fn)
                if not self.simulate:
                    shutil.copyfile(dest_fn, new_dest_fn)
                return True
            elif response.startswith('all '):
                rest = response[4:].strip()
                if not rest or rest[0] not in ('y', 'n', 'b'):
                    print self.query_usage
                    continue
                response = self.all_answer = rest[0]
            if response[0] == 'y':
                return True
            elif response[0] == 'n':
                return False
            elif response == 'dc':
                print '\n'.join(c_diff)
            elif response[0] == 'd':
                print '\n'.join(u_diff)
            else:
                if response[0] != '?':
                    print 'Unknown command: %s' % response
                print query_usage

    query_usage = '''\
Responses:
  Y(es):    Overwrite the file with the new content.
  N(o):     Do not overwrite the file.
  D(iff):   Show a unified diff of the proposed changes (dc=context diff)
  B(ackup): Save the current file contents to a .bak file
            (and overwrite)
  Type "all Y/N/B" to use Y/N/B for answer to all future questions
'''
        

def popdefault(dict, name, default=None):
    if name not in dict:
        return default
    else:
        v = dict[name]
        del dict[name]
        return v

