"""
Builder for TOPP WordPress MU
"""

import os
from fassembler.project import Project, Setting
from fassembler import tasks
from subprocess import Popen, PIPE

class WordPressProject(Project):
    """
    Install WordPress
    """

    name = 'wordpress'
    title = 'Install WordPress'

    settings = [
        Setting('port',
                default='{{env.base_port+int(config.port_offset)}}',
                help="Port to install Apache/WordPress on"),
        Setting('port_offset',
                default='3',
                help='Offset from base_port for Apache/WordPress'),
        Setting('host',
                default='localhost',
                help='Interface/host to serve Apache/WordPress on'),
        ## FIXME: this repo should be moved sometime
        Setting('wordpress_repo',
                default='https://svn.openplans.org/svn/vendor/wordpress-mu/openplans/trunk',
                help='Location of WordPress MU repository'),
        Setting('wordpress_scripts_repo',
                default='https://svn.openplans.org/svn/build/wordpress/trunk/scripts',
                help='Location of scripts for WordPress'),
        Setting('apache_exec',
                default='{{project.apache_exec()}}',
                help='Location of apache executable'),
        Setting('apache_module_dir',
                default='{{project.apache_module_dir()}}',
                help='Location of apache modules'),
        Setting('server_admin',
                default='{{env.environ["USER"]}}@{{env.fq_hostname}}',
                help='Server admin for Apache'),
        Setting('db_name',
                default='{{env.config.getdefault("general", "db_prefix", "")}}wordpress',
                help='Database name'),
        Setting('db_username',
                default='wordpress',
                help='Database user'),
        Setting('db_password',
                default='wordpress',
                help='Database password'),
        Setting('db_host',
                default='localhost',
                help='Database host'),
        Setting('db_root_password',
                default='',
                help='Database root password'),
        ]

    skel_dir = os.path.join(os.path.dirname(__file__), 'wordpress-files', 'skel')

    actions = [
        tasks.CopyDir('Create layout',
                      skel_dir, './'),
        tasks.SvnCheckout('Checkout wordpress-mu',
                          '{{config.wordpress_repo}}', '{{env.base_path}}/wordpress/src/wordpress-mu'),
        tasks.SvnCheckout('Checkout scripts',
                          '{{config.wordpress_scripts_repo}}',
                          '{{env.base_path}}/wordpress/src/scripts'),
        tasks.EnsureFile('Fill in wp-config.php',
                         '{{env.base_path}}/wordpress/src/wordpress-mu/wp-config.php',
                         content_path='{{env.base_path}}/wordpress/src/wordpress-mu/wp-config.php_tmpl',
                         svn_add=False, overwrite=True),
        tasks.InstallSupervisorConfig(),
        tasks.EnsureDir('Create var subdirectory',
                        '{{env.var}}/wordpress'),
        tasks.CheckMySQLDatabase('Check database'),
        tasks.Script('Setup database tables',
                     '{{env.base_path}}/wordpress/bin/setup-database.sh'),
        tasks.SaveURI(path='/blog'),
        ]

    depends_on_projects = ['fassembler:topp']
    depends_on_executables = [('httpd', 'apache2')]

    def extra_modules(self):
        required_modules = ['mime', 'dir', 'rewrite', 'log_config']
        apache_version = Popen([self.apache_exec(), "-v"], stdout=PIPE).communicate()[0].split()[2].split('/')[1].split('.')
        major, minor, revision = map(lambda x: int(x), apache_version)
        if major == 2 and minor >= 2:
            required_modules.append('authz_host')
        elif major == 1 or (major == 2 and minor < 2):
            required_modules.append('access')
        compiled_in_modules = set(Popen([self.apache_exec(), "-l"], stdout=PIPE).communicate()[0].split()[3:])
        modules_to_load = []
        for r in required_modules:
            rc = 'mod_%s.c' % r
            if rc not in compiled_in_modules:
                modules_to_load.append('LoadModule %s_module {{config.apache_module_dir}}/mod_%s.so' % (r, r))
        return self.interpolate('\n'.join(modules_to_load))

    def apache_module_dir(self):
        return self.search(
            ['/usr/local/apache2/modules', '/usr/lib/apache2/modules', '/Applications/MAMP/Library/modules'],
            'apache modules/')

    def mimetypes_file(self):
        return self.search(
            ['/usr/local/apache2/conf/mime.types', '/etc/mime.types', '/Applications/MAMP/conf/apache/mime.types'],
            'mime.types file')
    
    def apache_exec(self):
        names = ['httpd', 'apache2']
        paths = os.environ['PATH'].split(os.path.pathsep)
        for name in names:
            for path in paths:
                if os.path.exists(os.path.join(path, name)):
                    return name
        raise OSError(
            "Cannot find apache_exec")

    def search(self, options, name):
        for option in options:
            if os.path.exists(option):
                return option
        raise OSError(
            "Cannot find %s (tried %s)" % (name, ', '.join(options)))
