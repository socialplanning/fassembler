"""
Builder for TOPP WordPress MU
"""

import os
from fassembler.project import Project, Setting
from fassembler import tasks
from subprocess import Popen, PIPE

class CheckPHP(tasks.Task):
    """Makes sure PHP was built with required modules"""
    required_modules = ['hash']
    php_cgi_exec = tasks.interpolated('php_cgi_exec')

    def __init__(self, php_cgi_exec, stacklevel=1):
        super(CheckPHP, self).__init__('CheckPHP', stacklevel=stacklevel+1)
        self.php_cgi_exec = php_cgi_exec

    def run(self):
        compiled_in_modules = set(Popen([self.php_cgi_exec, '-m'], stdout=PIPE).communicate()[0].split('\n')[1:])
        for m in self.required_modules:
            if m not in compiled_in_modules:
                raise Exception('PHP not compiled with required module: %s' % m)
            
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
        Setting('php_cgi_exec',
                default='{{project.php_cgi_exec()}}',
                help='Location of php cgi executable'),
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
                default='{{env.db_root_password}}',
                help='Database root password'),
        ]

    skel_dir = os.path.join(os.path.dirname(__file__), 'wordpress-files', 'skel')

    actions = [
        CheckPHP('{{config.php_cgi_exec}}'),
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
                     ['{{config.php_cgi_exec}}', '-f', 'dbsetup.php',
                      '{{project.secret()}}'],
                     cwd='{{env.base_path}}/wordpress/src/wordpress-mu'),
        tasks.SaveURI(path='/blog'),
        ]

    depends_on_projects = ['fassembler:topp']
    depends_on_executables = [('httpd', 'apache2')]

    def extra_modules(self):
        required_modules = ['mime', 'dir', 'rewrite']
        major, minor = self.apache_version()

        # access_module changed to authz_host_module between Apache 2.1 and 2.2
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

        # config_log_module changed to log_config_module somewhere between Apache 1.x and 2.x
        # but its .so is called mod_log_config.so in both, which is annoying
        if 'mod_log_config.c' not in compiled_in_modules:
            if major == 1:
                modules_to_load.append('LoadModule config_log_module {{config.apache_module_dir}}/mod_log_config.so')
            elif major == 2:
                modules_to_load.append('LoadModule log_config_module {{config.apache_module_dir}}/mod_log_config.so')

        return self.interpolate('\n'.join(modules_to_load))

    def apache_module_dir(self):
        return self.search(
            ['/usr/local/apache2/modules',
             '/usr/lib/apache2/modules',   # Ubuntu
             '/usr/libexec/apache2',       # Mac OS X 10.5
             '/usr/libexec/httpd',         # Mac OS X 10.4
             '/usr/lib/httpd/modules',     # Red Hat EL and CentOS
             '/usr/lib64/httpd/modules',   # Red Hat EL and CentOS 64-bit
            ],
            'apache modules/')

    def mimetypes_file(self):
        return self.search(
            ['/usr/local/apache2/conf/mime.types',
             '/etc/mime.types',
             '/etc/apache2/mime.types', # Mac OS X 10.5 (comes with Apache 2.2.6 installed in /etc/apache2)
             '/etc/httpd/mime.types',   # Mac OS X 10.4 (comes with Apache 1.3.33 installed in /etc/httpd)
                                        # XXX upgrade from 10.4 to 10.5 leaves /etc/httpd intact,
                                        # therefore installing to a 10.5-upgraded machine relies on
                                        # /etc/apache2 being searched *before* /etc/httpd
             ],
            'mime.types file')
    
    def apache_exec(self):
        return self.find_exec(['httpd', 'apache2'])

    def apache_version(self):
        "Returns a pair of integers [major, minor]"
        major, minor, _ = Popen([self.apache_exec(), "-v"], stdout=PIPE).communicate()[0].split()[2].split('/')[1].split('.')
        return [int(i) for i in (major, minor)]

    def apache_fg_flag(self):
        major, _ = self.apache_version()
        if major < 2:
            ## XXX -F only works for apache 1.3 if not launching from supervisor
            ## due to setsid bug, so use -X instead. Don't use in production!
            return '-X'
        else:
            return '-DFOREGROUND'

    def php_cgi_exec(self):
        return self.find_exec(['php-cgi', 'php', 'php5-cgi', 'php5', 'php4-cgi', 'php4'])

    def php_version(self):
        "Returns major as a string"
        return Popen([self.php_cgi_exec(), '-v'], stdout=PIPE).communicate()[0].split()[1].split('.')[0]

    def find_exec(self, names):
        paths = os.environ['PATH'].split(os.path.pathsep)
        for extra in ['/usr/sbin', '/sbin']:
            if extra not in paths:
                paths.append(extra)
        for name in names:
            for path in paths:
                if os.path.exists(os.path.join(path, name)):
                    return os.path.join(path, name)
        raise OSError(
            "Cannot find any executable with name: %s" % ', '.join(names))

    def search(self, options, name):
        for option in options:
            if os.path.exists(option):
                return option
        raise OSError(
            "Cannot find %s (tried %s)" % (name, ', '.join(options)))

    def secret(self):
        f = open(self.environ.config.get('general', 'topp_secret_filename'), 'rb')
        c = f.read()
        f.close()
        return c
    
