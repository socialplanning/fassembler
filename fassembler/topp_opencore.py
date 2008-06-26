"""
Installation of the TOPP OpenCore environment.
"""

from fassembler import tasks
from fassembler.project import Project, Setting
from glob import glob
from time import sleep
from xml.dom import minidom
import os
import shutil
import socket
import subprocess
import sys
import urllib
import warnings
import util

interpolated = tasks.interpolated

if sys.version >= (2, 5):
    raise ImportError(
        "Zope is not compatible with Python 2.5!")

warnings.filterwarnings('ignore', 'tempnam is .*')


class InstallZope(tasks.InstallTarball):

    version_path = interpolated('version_path')
    _tarball_url = interpolated('_tarball_url')
    _orig_source = interpolated('_orig_source')
    _src_name = 'Zope'
    _tarball_version = interpolated('_tarball_version')

    description = """
    Install {{task._src_name}} into {{task.dest_path}}.

    This downloads {{task._src_name}} from {{task._tarball_url}},
    which was itself built from {{task._orig_source}}
    """

    def __init__(self, stacklevel=1):
        super(InstallZope, self).__init__(stacklevel)
        self.version_path = '{{task.dest_path}}/opencore_tarball_version.txt'
        self._tarball_url = '{{config.zope_tarball_url}}'
        self._orig_source = '{{config.zope_orig_source}}'
        self._tarball_version = '{{config.zope_tarball_version}}'

    def is_up_to_date(self):
        if os.path.exists(self.version_path):
            f = open(self.version_path)
            version = f.read().strip()
            f.close()
            if version == self._tarball_version:
                self.logger.notify('Version %s up-to-date' % version)
                return True

    def post_unpack_hook(self):
        self.maker.ensure_file(self.version_path, self._tarball_version,
                               svn_add=False)

    
def make_tarball(tarball_version, tarball_url_dir, orig_zope_source):
    tarball_url = '%s/OpenplansZope-%s.tar.bz2' % (tarball_url_dir,
                                                   tarball_version)
    filename = os.path.basename(tarball_url)
    dir = 'tmp-download'
    if not os.path.exists(dir):
        print 'creating %s' % dir
        os.makedirs(dir)
    tgz_filename = os.path.join(dir, os.path.basename(orig_zope_source))
    if os.path.exists(tgz_filename):
        print '%s already exists; not downloading' % tgz_filename
    else:
        print 'Downloading %s to %s' % (orig_zope_source, tgz_filename)
        util.popen(['wget', '-q', orig_zope_source, '-O', tgz_filename])
        
    print 'Unpacking'
    print 'Running tar zfx %s (in %s)' % (tgz_filename, dir)
    util.popen(['tar', 'zfx', os.path.basename(tgz_filename)], cwd=dir)
    base_name = os.path.splitext(os.path.basename(tgz_filename))[0]
    dest_name = os.path.join(dir, 'Zope')
    if os.path.exists(dest_name):
        print 'Deleting %s' % dest_name
        shutil.rmtree(dest_name)
    print 'Moving %s to %s' % (base_name, dest_name)
    shutil.move(os.path.join(dir, base_name), dest_name)
    patch_dir_prefix = os.path.join(os.path.dirname(__file__),
                                    'opencore-files',
                                    'patches')
    patch_dirs = glob(patch_dir_prefix+'*')
    patch_dir = None
    for pdir in patch_dirs:
        pdir_version = pdir.split('_')[-1]
        if tarball_version.startswith(pdir_version):
            patch_dir = pdir
            break
    if patch_dir is not None:
        # Apply patches.
        for fn in os.listdir(patch_dir):
            fn = os.path.abspath(os.path.join(patch_dir, fn))
            if not os.path.isfile(fn):
                # Skip directories, anything other than a file or link.
                continue
            args = ['patch', '-p0', '--forward', '-i', fn]
            print 'Running %s' % ' '.join(args)
            util.popen(args, cwd=dest_name)
    print 'Creating %s' % filename
    print 'Running tar cfj %s Zope (in %s)' % (filename, dir)
    util.popen(['tar', 'cfj', filename, 'Zope'], cwd=dir)
    print "Removing %s/%s" % (dir, 'Zope')
    shutil.rmtree(os.path.join(dir, 'Zope'))
    # use compileall?
    # upload?
    print 'You may want to run this now:'
    print '  scp %s flow.openplans.org:/www/svn.openplans.org/eggs/' % os.path.join(dir, filename)

class GetBundleTarball(tasks.Task):

    description = """
    Get the bundle {{config.opencore_bundle_tar_info}} (name {{config.opencore_bundle_name}})
    and unpack it to {{task.dest}}
    """

    dest = interpolated('dest')

    def __init__(self, name='Get opencore bundle tarball',
                 dest='{{env.base_path}}/{{project.name}}/src/opencore-bundle'):
        super(GetBundleTarball, self).__init__(name, stacklevel=1)
        self.dest = dest

    def run(self):
        url = self.interpolate('{{config.opencore_bundle_tar_info}}')
        self.logger.debug('Getting tarball info at %s' % url)
        f = urllib.urlopen(url)
        latest_id = f.read().strip()
        f.close()
        tarball_id_fn = os.path.join(self.dest, 'tarball-id.txt')
        if os.path.exists(tarball_id_fn):
            f = open(tarball_id_fn)
            tarball_name, current_id = f.read().strip().split(':', 1)
            f.close()
            if tarball_name != self.interpolate('{{config.opencore_bundle_name}}'):
                response = self.maker.ask(
                    'Current bundle is named "%s"; the build wants to install "%s"\n'
                    'Overwrite current bundle?' % (tarball_name, self.interpolate('{{config.opencore_bundle_name}}')),
                    default='n')
                if response == 'n':
                    self.logger.notify('Aborting bundle installation')
                    return
            self.logger.info('Checked id in %s: %s' % (tarball_id_fn, current_id))
            if current_id == latest_id:
                self.logger.notify('Current bundle is up-to-date (%s)' % latest_id)
                return
            else:
                self.logger.notify('Current bundle is not up-to-date (currently: %s; latest: %s)'
                                   % (current_id, latest_id))
        else:
            self.logger.info('No tarball-id.txt file in %s' % tarball_id_fn)
        url = self.interpolate('{{config.opencore_bundle_tar_dir}}/openplans-bundle-{{config.opencore_bundle_name}}-%s.tar.bz2' % latest_id)
        tmp_fn = os.path.abspath(os.path.basename(url))
        self.logger.notify('Downloading tarball from %s to %s' % (url, tmp_fn))
        delete_tmp_fn = False
        try:
            if not self.maker.simulate:
                self.maker.retrieve(url, tmp_fn)
            self.maker.ensure_dir(self.dest)
            self.logger.notify('Unpacking into %s' % self.dest)
            ## FIXME: is it really okay just to unpack right over whatever might already be there?
            ## Should we warn or something?
            self.maker.run_command(
                'tar', 'jfx', tmp_fn,
                cwd=self.dest)
            delete_tmp_fn = True
        finally:
            if delete_tmp_fn and os.path.exists(tmp_fn):
                self.logger.info('Deleting %s' % tmp_fn)
        

class SymlinkProducts(tasks.Task):

    source_glob = interpolated('source_glob')
    dest_dir = interpolated('dest_dir')
    exclude_glob = interpolated('exclude_glob')

    description = """
    Symlink the files {{task.source_glob}} ({{len(task.source_files)}} files and directories total)
    to {{task.dest_dir}}
    {{if task.exclude_glob}}
    Also exclude any files matching {{task.exclude_glob}} ({{task.exclude_count}} files and directories excluded)
    {{endif}}
    """

    def __init__(self, name, source_glob, dest_dir, exclude_glob=None, stacklevel=1):
        super(SymlinkProducts, self).__init__(name, stacklevel=stacklevel+1)
        self.source_glob = source_glob
        self.dest_dir = dest_dir
        self.exclude_glob = exclude_glob

    @property
    def source_files(self):
        results  =[]
        if self.exclude_glob:
            exclude = glob(self.exclude_glob)
        else:
            exclude = []
        for filename in glob(self.source_glob):
            if filename not in exclude:
                results.append(filename)
        return results

    @property
    def exclude_count(self):
        return len(glob(self.exclude_glob))

    def run(self):
        for filename in self.source_files:
            dest = os.path.join(self.dest_dir, os.path.basename(filename))
            self.maker.ensure_symlink(filename, dest)


class ZopeConfigTask(tasks.Task):
    """
    Abstract base class that stores the Zope config directories.
    """
    zope_etc_path = interpolated('zope_etc_path')
    build_etc_path = interpolated('build_etc_path')
    zope_profiles_dir = interpolated('zope_profiles_dir')
    build_profile_path = interpolated('build_profile_path')

    def __init__(self, name, stacklevel=1):
        super(ZopeConfigTask, self).__init__(name, stacklevel=stacklevel+1)
        self.zope_etc_path = '{{config.zope_instance}}/etc'
        self.build_etc_path = '{{env.base_path}}/etc/{{project.name}}/zope_etc'
        # FIXME: is there a better way to get to this directory?
        relative_profiles_dir = 'src/opencore/opencore/configuration/profiles'
        self.zope_profiles_dir = '{{project.build_properties["virtualenv_path"]}}/%s' % relative_profiles_dir
        self.build_profile_path = '{{env.base_path}}/etc/{{project.name}}/gs_profile'


class PlaceZopeConfig(ZopeConfigTask):

    description = """
    Finds specific Zope configuration files in their default locations
    and copies these into the build's etc directory for svn
    management, if this has not already been done.
    """

    def run(self):
        if not os.path.islink(self.zope_etc_path):
            self.maker.copy_dir(self.zope_etc_path,
                                self.build_etc_path,
                                add_dest_to_svn=True)

        self.maker.copy_dir('%s/default' % self.zope_profiles_dir,
                            self.build_profile_path,
                            add_dest_to_svn=True)

        pas_obj_file_path = '%s/default/PAS/.objects' % self.zope_profiles_dir
        if os.path.exists(pas_obj_file_path):
            self.maker.copy_file(pas_obj_file_path,
                                 '%s/PAS/.objects' % self.build_profile_path,
                                 svn_add=True)

        # fix values in properties.xml and propertiestool.xml
        # XXX these settings should eventually live in build.ini and
        # opencore should retrieve them via the IProvideSiteConfig utility

        def get_from_config(option, section='general'):
            if self.environ.config.has_option(section, option):
                return self.environ.config.get(section, option)
            return self.project.get_req_setting(option)

        properties_path = '%s/properties.xml' % self.build_profile_path
        doc = minidom.parse(properties_path)

        email_from_address = get_from_config('email_from_address')
        opencore_site_title = get_from_config('opencore_site_title')

        for node in doc.getElementsByTagName('property'):
            name = node.getAttribute('name')
            if name == u'title':
                node.firstChild.data = unicode(opencore_site_title)
            elif name == u'email_from_address':
                node.firstChild.data = unicode(email_from_address)
        doc.writexml(open(properties_path, 'w'))

        
        propertiestool_path = '%s/propertiestool.xml' % self.build_profile_path
        doc = minidom.parse(propertiestool_path)

        mailing_list_fqdn = get_from_config('mailing_list_fqdn')

        for node in doc.getElementsByTagName('property'):
            name = node.getAttribute('name')
            if name == u'mailing_list_fqdn':
                node.firstChild.data = unicode(mailing_list_fqdn)
            
        doc.writexml(open(propertiestool_path, 'w'))


class SymlinkZopeConfig(ZopeConfigTask):

    description = """
    Delete certain configuration files from the standard Zope location
    and symlink them back into place from the fassembler location.
    Assumes files already exist in the fassembler locations, i.e. that
    PlaceZopeConfig is run first.
    """
    zope_profile_path = interpolated('zope_profile_path')

    def run(self):
        if not os.path.islink(self.zope_etc_path):
            self.maker.rmtree(self.zope_etc_path)
        self.maker.ensure_symlink(self.build_etc_path, self.zope_etc_path)

        self.zope_profile_path = '%s/{{env.config.get("general", "etc_svn_subdir")}}' \
                                 % self.zope_profiles_dir
        if os.path.exists(self.zope_profile_path) and \
               not os.path.islink(self.zope_profile_path):
            self.maker.rmtree(self.zope_profile_path)
        self.maker.ensure_symlink(self.build_profile_path,
                                  self.zope_profile_path)



class RunZopectlScript(tasks.Task):

    description = """
    Given the path of a python file {{task.script_path}},
    executes 'zopectl run {{task.script_path}} {{task.script_args}}'
    from within opencore's virtualenv.
    """

    script_path = interpolated('script_path')
    script_args = interpolated('script_args')

    def __init__(self, script_path, script_args='',
                 name='Run zopectl script', stacklevel=1):
        super(RunZopectlScript, self).__init__(name, stacklevel=stacklevel+1)
        self.script_path = script_path
        self.script_args = ' '.join(script_args.split())

    def run(self):
        if self.maker.simulate:
            self.logger.notify('Would run "zopectl run %s %s"' %
                               (self.script_path, self.script_args))
            return
        if os.path.exists(self.script_path):
            zopectl_path = self.interpolate('{{env.base_path}}/opencore/zope/bin/zopectl')
            process_args = [zopectl_path, 'run', self.script_path]
            process_args.append(self.script_args)
            self.maker.run_command(process_args)
        else:
            self.maker.beep_if_necessary()
            self.logger.warn('Tried to run zopectl script at %s but the '
                             'path does not exist' % self.script_path,
                             color='red')


class RunZopeScriptsWithZeo(tasks.Task):

    description = "Start zeo, run all zopectl scripts, stop zeo"

    script_path = interpolated('script_path')
    script_args = interpolated('script_args')

    def __init__(self, *subtasks, **kw):
        stacklevel = kw.get('stacklevel', 1)
        super(RunZopeScriptsWithZeo, self).__init__(self.description,
                                                    stacklevel=stacklevel+1)
        self.subtasks = subtasks

    def iter_subtasks(self):
        # We do NOT want the project to iterate over our subtasks,
        # because we want to treat everything atomically: eg. if zeo
        # doesn't start and the user hits 'c', we should not run any
        # scripts.
        # This means we have to define bind() and run() specially
        # to handle the subtasks.
        return []

    def bind(self, *args, **kw):
        super(RunZopeScriptsWithZeo, self).bind(*args, **kw)
        subtasks = []
        for task in self.subtasks:
            self._bind_tasks(task, *args, **kw)

    def _bind_tasks(self, task, *args, **kw):
        task.bind(*args, **kw)
        task.confirm_settings()
        task.setup_build_properties()
        for subtask in task.iter_subtasks():
            self._bind_tasks(subtask, *args, **kw)

    def run(self):
        self.start_zeo()
        try:
            for task in self.subtasks:
                self._run_task(task)
        finally:
            self.stop_zeo()

    def _run_task(self, task):
        self.logger.notify("running subtask: %s" % task.title)
        self.logger.indent += 2
        try:
            task.run()
            for subtask in task.iter_subtasks():
                self._run_task(subtask)
        finally:
            self.logger.indent -= 2


    ## ZEO start/stop methods: ##

    @property
    def zeo_port(self):
        return int(self.interpolate('{{config.zeo_port}}'))

    @property
    def zeo_host(self):
        return self.interpolate('{{config.zeo_host}}')

    @property
    def zeoctl_path(self):
        return self.interpolate('{{env.base_path}}/opencore/zeo/bin/zeoctl')


    def start_zeo(self):
        if self.maker.simulate:
            return
        port = self.zeo_port
        host = self.zeo_host
        sock = socket.socket()
        try:
            try:
                sock.bind((host, port))
            except socket.error, exc:
                if exc.args[0] == 48: # address in use
                    self.logger.warn('Note: ports can sometimes take a minute to be freed after stopping ZEO')
                    self.logger.warn('Retry if you think the port should be free')
                    raise Exception('The ZEO Address %s:%s is already in use: %s' % (host, port, exc))
                else:
                    raise Exception('Cannot bind to ZEO port at %s:%s: %s' % (host, port, exc))
        finally:
            sock.close()
        if self.zeo_status_contains('pid'):
            raise Exception('Zeo is running already. Please stop zeo before running.')
        self.maker.run_command([self.zeoctl_path, 'start'])
        self.check_zeoctl_timeout('pid', 'starts')
        self.logger.notify('Zeo started')

    def stop_zeo(self):
        if self.maker.simulate:
            return
        if self.zeo_status_contains('not running'):
            raise Exception('Expected Zeo to be running but it is not.')
        self.maker.run_command([self.zeoctl_path, 'stop'])
        self.check_zeoctl_timeout('not running', 'stops')
        self.logger.notify('Zeo stopped')

    zeoctl_timeout = 30
    
    def check_zeoctl_timeout(self, check_for_status, action):
        elapsed = 0
        while elapsed < self.zeoctl_timeout and not self.zeo_status_contains(check_for_status):
            self.logger.notify('Sleeping while zeo %s...' % action)
            sleep(1)
            elapsed += 1
            if elapsed == self.zeoctl_timeout:
                raise Exception("Could not start zeo after trying for %d seconds" % self.zeoctl_timeout)

    def zeo_status_contains(self, substr):
        return substr in subprocess.Popen([self.zeoctl_path, 'status'], stdout=subprocess.PIPE).communicate()[0]


class PatchTwill(tasks.Task):
    """
    patch twill so it doesn't print out those horrible AT LINE commands;
    this should be removed if upstream fix is committed
    """
    def run(self):
        
        # get around readline printing strange things 
        # see: http://www.openplans.org/projects/opencore/lists/openplans-svn/archive/2008/04/1207154035776
        env = os.environ.copy()
        env['TERM'] = ''
        err, stdout, stderr = util.popen(
            ["%s" % os.path.join(self.venv_property(), 'bin', 'python'), 
             '-c', 'import twill.parse; print twill.parse.__file__.rstrip("c")'], 
            env=env)
        filename = stdout.strip()
        parse = file(filename)
        lines = parse.readlines()
        parse.close()

        lines = [ line for line in lines if "print 'AT LINE:'" not in line ]

        parse = file(filename, 'w')
        print >> parse, ''.join(lines)
        parse.close()


class PatchFive(tasks.Patch):
    """
    The Five product might be in the opencore bundle, or we might be
    using the one in the Zope tree, depending on the Zope version.
    The Zope version will already have been patched; we want this one
    to fail silently if there's no Five in the bundle.
    """
    def run(self):
        if not os.path.exists(self.dest):
            self.logger.notify('No Five in opencore bundle, skipping patch')
            return
        return tasks.Patch.run(self)


class OpenCoreBase(Project):
    defaults = dict(opencore_site_id='openplans',
                    opencore_site_title='OpenCore Site',
                    mailing_list_fqdn='lists.openplans.org',
                    email_from_address='{{env.environ["USER"]}}@{{env.fq_hostname}}',
                    )

    files_dir = os.path.join(os.path.dirname(__file__), 'opencore-files')

    def get_req_setting(self, setting):
        return self.req_settings.get(setting, self.interpolate(self.defaults[setting]))


class OpenCoreProject(OpenCoreBase):
    """
    Install OpenCore
    """

    name = 'opencore'
    title = 'Install OpenCore'

    settings = [
        Setting('spec',
                default='requirements/opencore-req.txt',
                help='Specification of packages to install'),
        Setting('zope_instance',
                default='{{project.build_properties["virtualenv_path"]}}/zope',
                help='Instance home for Zope'),
        Setting('zope_user',
                default='{{env.parse_auth(env.config.get("general", "admin_info_filename")).username}}',
                help='Default admin username'),
        Setting('zope_password',
                default='{{env.parse_auth(env.config.get("general", "admin_info_filename")).password}}',
                help='Admin password'),
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help="Port to install Zope on"),
        Setting('port_offset',
                default='1',
                help='Offset from base_port for Zope'),
        Setting('host',
                default='localhost',
                help='Interface/host to serve Zope on'),
        Setting('zeo_port',
                default='{{env.base_port+int(config.zeo_port_offset)}}',
                help="Port to install ZEO on"),
        Setting('zeo_port_offset',
                default='2',
                help='Offset from base_port for ZEO'),
        Setting('zeo_host',
                default='localhost',
                help='Interface/host to serve ZEO on'),
        Setting('zope_source',
                default='{{project.build_properties["virtualenv_path"]}}/src/Zope',
                help='Location of Zope source'),
        Setting('zope_install',
                default='{{project.build_properties["virtualenv_path"]}}/lib/zope',
                help='Location of Zope installation'),
        Setting('zope_instance',
                default='{{project.build_properties["virtualenv_path"]}}/zope',
                help='Location of Zope instance home'),
        ## FIXME: not sure if this is right:
        ## FIXME: should also be more global
        ## FIXME: also, type check on bool-ness
        Setting('debug',
                default='0',
                help='Whether to start Zope in debug mode'),
        Setting('email_confirmation',
                default='1',  # opencore ftests expect it turned on!
                help='Whether to send email configuration'),
        Setting('zope_tarball_version',
                default='2.9.9openplans.1',
                help='Version suffix for the Zope source tarball'),
        Setting('zope_tarball_url',
                default='{{config.opencore_bundle_tar_dir}}/OpenplansZope-{{config.zope_tarball_version}}.tar.bz2',
                help='URL of the Zope source tarball'),
        Setting('zope_orig_source',
                default='http://www.zope.org/Products/Zope/2.9.9/Zope-2.9.9-final.tgz',
                help='URL of the original Zope source tarball upon which the OpenPlans tarball is based'),
        ## FIXME: this could differ for different profiles
        ## e.g., there's another bundle at:
        ##   https://svn.openplans.org/svn/deployment/products-plone25
        Setting('opencore_bundle_name',
                default='{{project.req_settings.get("opencore_bundle_name", "opencore-plone25")}}',
                help='Name of the bundle to use'),
        Setting('opencore_bundle_tar_dir',
                default='https://svn.openplans.org/eggs/',
                help='Directory/URL where the bundle tarball is kept'),
        Setting('opencore_bundle_svn_repo_dir',
                default='https://svn.openplans.org/svn/bundles',
                help='SVN location of bundles'),
        Setting('opencore_bundle_use_svn',
                default='false',
                help='Use the svn repo instead of a tarball to install the bundle'),
        Setting('opencore_bundle_tar_info',
                default='{{config.opencore_bundle_tar_dir}}/openplans-bundle-{{config.opencore_bundle_name}}.txt',
                help='Location of the pointer to the real tarball'),
        Setting('opencore_bundle_svn_repo',
                default='{{config.opencore_bundle_svn_repo_dir}}/{{config.opencore_bundle_name}}',
                help='Full svn repository for checkouts'),
        Setting('ftests_path',
                default='{{project.req_settings.get("ftests_path", "opencore/src/opencore/ftests")}}',
                help='Relative path to ftests'),
        Setting('opencore_vacuum_whitelist',
                inherit_config=('general', 'opencore_vacuum_whitelist'),
                default='',
                help='whitelist of safe sites for javascript authentication api'),
        Setting('opencore_embed_whitelist',
                inherit_config=('general', 'opencore_embed_whitelist'),
                default='www.youtube.com,video.google.com,www.streetsblog.org,streetsblog.org,p.streetsblog.org,www.streetfilms.org,streetfilms.org,p.streetfilms.org,www.vimeo.com,static.slideshare.net,widget-57.slide.com,www.mindmeister.com,mindmeister.com',
                help='whitelist of safe sites to embed objects, embed, param, iframe, and layer tags'),
        ]

    files_dir = os.path.join(os.path.dirname(__file__), 'opencore-files')
    patch_dir = os.path.join(files_dir, 'patches')
    skel_dir = os.path.join(files_dir, 'zope_skel')

    start_script_template = """\
#!/bin/sh
cd {{env.base_path}}
source ./opencore/bin/activate
exec {{config.zope_instance}}/bin/runzope -X debug-mode=off
"""

    flunc_globals_template = """\
setglobal admin      '{{config.zope_user}}'
setglobal adminpw    '{{config.zope_password}}'
setglobal projtxt    '{{env.config.get("general", "projtxt")}}'
setglobal projprefs    '{{env.config.get("general", "projprefs")}}'
"""


    actions = [
        tasks.SaveSetting('Save application settings',
                          {'opencore_vacuum_whitelist': '{{config.opencore_vacuum_whitelist}}',
                           'opencore_embed_whitelist':  '{{config.opencore_embed_whitelist}}',},
                          section='applications'),
        tasks.VirtualEnv(),
        tasks.SetDistutilsValue('Disable zipped eggs',
                                'easy_install', 'zip_ok', 'False'),
        tasks.EnsureDir('Create src/ directory', '{{project.name}}/src'),
        tasks.EnsureDir('Create OpenCore var/ directory',
                        '{{env.var}}/opencore'),
        InstallZope(),
        tasks.InstallSpec('Install OpenCore',
                          '{{config.spec}}'),
        tasks.TestLxml('{{env.base_path}}/opencore'),
        tasks.CopyDir('Create custom skel',
                      skel_dir, '{{project.name}}/src/Zope/custom_skel'),
        tasks.Script('Configure Zope', [
        './configure', '--with-python={{project.build_properties["virtualenv_bin_path"]}}/python',
        '--prefix={{config.zope_install}}'],
                     cwd='{{config.zope_source}}'),
        tasks.Script('Make Zope', ['make'], cwd='{{config.zope_source}}'),
        tasks.Script('Install Zope', ['make', 'install'], cwd='{{config.zope_source}}'),
        # this could maybe be a ConditionalTask, but the -fr ensures
        # it won't fail
        tasks.Script('Delete zope instance binaries',
                     ['rm', '-fr', '{{config.zope_instance}}/bin'],
                     cwd='{{config.zope_install}}'),
        tasks.Script('Make Zope Instance', [
        'python', '{{config.zope_install}}/bin/mkzopeinstance.py', '--dir', '{{config.zope_instance}}',
        '--user', '{{config.zope_user}}:{{config.zope_password}}',
        '--skelsrc', '{{config.zope_source}}/custom_skel'],
                     use_virtualenv=True),
        tasks.ConditionalTask('Create bundle',
                              ('{{config.opencore_bundle_use_svn}}',
                               tasks.SvnCheckout('Check out bundle',
                                                 '{{config.opencore_bundle_svn_repo}}',
                                                 '{{env.base_path}}/opencore/src/opencore-bundle')),
                              (True,
                               GetBundleTarball())),
        SymlinkProducts('Symlink Products',
                        '{{env.base_path}}/opencore/src/opencore-bundle/*',
                        '{{config.zope_instance}}/Products',
                        exclude_glob='{{env.base_path}}/opencore/src/opencore-bundle/ClockServer'),
        ## FIXME: linkzope and linkzopebinaries?
        PlaceZopeConfig('Copy Zope etc into build etc'),
        PatchFive(name='Patch Five viewlet security acquisition (see http://trac.openplans.org/openplans/ticket/2026)',
                  files='{{env.base_path}}/fassembler/src/fassembler/fassembler/opencore-files/five-viewletmanager.patch',
                  dest='{{env.base_path}}/src/opencore-bundle/Five'),
        SymlinkZopeConfig('Symlink Zope configuration'),
        tasks.ForEach('Run zinstalls',
                      'package_name',
                      '{{project.req_settings.get("zinstall_packages")}}',
                      tasks.Script('zinstall {{task.package_name}}',
                                  ['python', 'setup.py', 'zinstall', '{{env.base_path}}/opencore/zope'],
                                  cwd='{{env.base_path}}/opencore/src/{{task.package_name}}',
                                  use_virtualenv=True)),
        tasks.InstallSupervisorConfig(),
        tasks.EnsureFile('Write the start script',
                         '{{env.base_path}}/bin/start-{{project.name}}',
                         content=start_script_template,
                         svn_add=True, executable=True, overwrite=True),
        tasks.SaveURI(uri='http://{{config.host}}:{{config.port}}/openplans',
                      uri_template='http://{{config.host}}:{{config.port}}/VirtualHostBase/{wsgi.url_scheme}/{HTTP_HOST}/openplans/projects/{project}/VirtualHostRoot{vh_SCRIPT_NAME}',
                      uri_template_main_site='http://{{config.host}}:{{config.port}}/VirtualHostBase/{wsgi.url_scheme}/{HTTP_HOST}/openplans/VirtualHostRoot/projects/{project}',
                      path='/',
                      header_name='zope',
                      theme='not-main-site'),
        tasks.SaveURI(project_name='opencore_global',
                      uri='http://{{config.host}}:{{config.port}}/openplans',
                      uri_template='http://{{config.host}}:{{config.port}}/VirtualHostBase/{wsgi.url_scheme}/{HTTP_HOST}/openplans/VirtualHostRoot{vh_SCRIPT_NAME}',
                      path='/',
                      project_local=False,
                      header_name='zope',
                      theme='not-main-site',
                      ),
        tasks.SaveSetting('Save SSL-only path settings',
                          variables={'opencore_global sslonly':
                                     '/join /login /forgot /acl_users/credentials_signed_cookie_auth/require_login regex:^/people/.*/account',
                                     },
                          section='applications'
                          ),
        tasks.EnsureFile(
            'Overwrite the flunc global info',
            '{{env.base_path}}/{{config.ftests_path}}/globals.conf',
            content=flunc_globals_template,
            svn_add=False, overwrite=True),
        PatchTwill('Patch twill configuration to avoid printing extraneous "AT LINE"s'),
        ]


    depends_on_projects = ['fassembler:topp']



class ZEOProject(OpenCoreBase):
    """
    Install ZEO
    """

    name = 'zeo'
    title = 'Install ZEO'

    spec_filename = 'opencore'  # Re-use opencore-req.txt.

    settings = [
        Setting('zeo_instance',
                default='{{project.build_properties["virtualenv_path"]}}/zeo',
                help='Instance home for ZEO'),
        Setting('zeo_port',
                default='{{env.base_port+int(config.zeo_port_offset)}}',
                help="Port to install ZEO on"),
        Setting('zeo_port_offset',
                default='2',
                help='Offset from base_port for ZEO'),
        Setting('zeo_host',
                default='localhost',
                help='Interface/host to serve ZEO on'),
        Setting('zope_install',
                default='{{project.build_properties["virtualenv_path"]}}/lib/zope',
                help='Location of Zope software'),
        Setting('opencore_site_id',
                inherit_config=('general', 'opencore_site_id'),
                default='{{project.get_req_setting("opencore_site_id")}}',
                help='id of opencore site object'),
        Setting('opencore_site_title',
                inherit_config=('general', 'opencore_site_title'),
                default='{{project.get_req_setting("opencore_site_title")}}',
                help='title of opencore site object'),
        Setting('email_from_address',
                inherit_config=('general', 'email_from_address'),
                default='{{project.get_req_setting("email_from_address")}}',
                help='address from which autogenerated site emails are sent'),
        Setting('mailing_list_fqdn',
                inherit_config=('general', 'mailing_list_fqdn'),
                default='{{project.get_req_setting("mailing_list_fqdn")}}',
                help='fqdn of mailing list addresses'),
        ]

    files_dir = os.path.join(os.path.dirname(__file__), 'opencore-files')
    skel_dir = os.path.join(files_dir, 'zeo_skel')

    start_script_template = """\
#!/bin/sh
cd {{env.base_path}}
exec {{config.zeo_instance}}/bin/runzeo
"""

    actions = [
        tasks.SaveSetting('Save global settings',
                          {'opencore_site_id': '{{config.opencore_site_id}}',
                           'opencore_site_title': '{{config.opencore_site_title}}',
                           'email_from_address': '{{config.email_from_address}}',
                           'mailing_list_fqdn': '{{config.mailing_list_fqdn}}',
                          }),
        ## FIXME: this is kind of lame (recreating a venv we know exists),
        #  but needed for later steps:
        tasks.VirtualEnv(path='opencore'),
        tasks.Script('Make ZEO Instance', [
        'python', '{{config.zope_install}}/bin/mkzeoinstance.py', '{{config.zeo_instance}}', '{{config.zeo_port}}'],
                     use_virtualenv=True),
        tasks.EnsureFile('Overwrite the zeo.conf file',
                         '{{config.zeo_instance}}/etc/zeo.conf',
                         content_path='%s/etc/zeo.conf' % skel_dir,
                         force_overwrite=True),
        tasks.EnsureFile('Write the ZEO start script',
                         '{{env.base_path}}/bin/start-opencore-{{project.name}}',
                         content=start_script_template,
                         svn_add=True, executable=True, overwrite=True),
        tasks.EnsureDir('Create var/zeo directory for Data.fs file',
                        '{{env.var}}/zeo'),
        # ZEO doesn't really have a uri
        tasks.InstallSupervisorConfig(script_name='opencore-zeo'),
        RunZopeScriptsWithZeo(
            RunZopectlScript('{{env.base_path}}/opencore/src/opencore/do_nothing.py',
                             name='Run initial zopectl to bypass failure-on-first-start'),
            RunZopectlScript('{{env.base_path}}/opencore/src/opencore/add_openplans.py',
                             name='Add OpenPlans site'),
            tasks.ForEach('Run additional opencore-req.txt zopectl scripts',
                          'script_name',
                          '{{project.req_settings.get("zopectl_scripts")}}',
                          RunZopectlScript('{{os.path.join(env.base_path, "opencore/", task.script_name)}}',
                                           name="Additional zopectl script {{task.script_name}}"),
                          ),
            ),
        
        ]


    depends_on_projects = ['fassembler:opencore']


class MaildropProject(OpenCoreBase):
    """
    Setup maildrop
    """

    name = 'maildrop'
    title = 'Setup maildrop'

    settings = [
        Setting('smtp_host',
                default='localhost',
                help='Host to send mail to'),
        Setting('smtp_port',
                default='25',
                help='Port to send mail to'),
        Setting('smtp_tls',
                default='0',
                help='TLS usage with: 0, don\'t use; 1, try to use; 2, force TLS'),
        Setting('smtp_auth_filename',
                default='',
                help='A file that contains username:password, for SMTP authentication'),
        Setting('maildrop_interval',
                default='120',
                help='How long to wait between spool checks'),
        Setting('debug_receiver',
                default='',
                help='An email address (or comma-separated multiple addresses) '
                'where all email will be sent, overriding normal delivery'),
        Setting('zeo_port',
                default='{{env.base_port+int(config.zeo_port_offset)}}',
                help="Port to install ZEO on"),
        Setting('zeo_port_offset',
                default='2',
                help='Offset from base_port for ZEO'),
        Setting('zeo_host',
                default='localhost',
                help='Interface/host to serve ZEO on'),
        ]

    maildrop_start_script_template = """\
#!/bin/sh

BASE="{{env.base_path}}"
MAILDROPHOME="$BASE/opencore/src/opencore-bundle/MaildropHost/maildrop"
CONFIG="$BASE/etc/opencore/maildrop/config.py"

exec $BASE/opencore/bin/python $MAILDROPHOME/maildrop.py "$CONFIG"
"""

    replacement_config = """\
import os
base_path = {{repr(env.base_path)}}
config_location = os.path.join(base_path, 'etc', 'opencore', 'maildrop', 'config.py')
execfile(config_location)
"""

    actions = [
        tasks.EnsureFile('Copy maildrop config',
                         '{{env.base_path}}/etc/opencore/maildrop/config.py',
                         content_path='{{project.files_dir}}/maildrop_config.py_tmpl',
                         svn_add=True),
        tasks.EnsureFile('Overwrite MaildropHost config.py',
                         '{{env.base_path}}/opencore/src/opencore-bundle/MaildropHost/config.py',
                         content=replacement_config,
                         overwrite=True),
        tasks.EnsureFile('Write maildrop start script',
                         '{{env.base_path}}/bin/start-maildrop',
                         content=maildrop_start_script_template,
                         svn_add=True, executable=True, overwrite=True),
        tasks.EnsureDir('Create spool directory',
                        '{{env.var}}/maildrop-spool'),
        tasks.InstallSupervisorConfig(),
        RunZopeScriptsWithZeo(
            RunZopectlScript('{{env.base_path}}/opencore/src/opencore/add_maildrop.py',
                             name='Add a MaildropHost object'),
        ),
        ]


    depends_on_projects = ['fassembler:zeo']
        

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print 'Usage: %s TARBALL_VERSION TARBALL_URL_DIR ZOPE_SOURCE_URL' % sys.argv[0]
        sys.exit()
    make_tarball(sys.argv[1], sys.argv[2], sys.argv[3])
