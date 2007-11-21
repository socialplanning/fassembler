"""
Builder for TOPP WordPress MU
"""

import os
from fassembler.project import Project, Setting
from fassembler import tasks

class WordPressProject(Project):
    """
    Install WordPress
    """

    name = 'wordpress'
    title = 'Install WordPress'

    settings = [
        Setting('port',
                default='{{env.config.getint("general", "base_port")+int(config.port_offset)}}',
                help="Port to install Apache/WordPress on"),
        Setting('port_offset',
                default='3',
                help='Offset from base_port for Apache/WordPress'),
        Setting('host',
                default='localhost',
                help='Interface/host to serve Apache/WordPress on'),
        ## FIXME: this repo should be moved sometime
        Setting('wordpress_repo',
                default='https://svn.openplans.org/svn/build/topp.build.wordpress/trunk/topp/build/wordpress/wordpress-mu',
                help='Location of WordPress MU repository'),
        Setting('wordpress_scripts_repo',
                default='https://svn.openplans.org/svn/build/wordpress/trunk/scripts',
                help='Location of scripts for WordPress'),
        Setting('apache_exe',
                default='{{project.apache_exec()}}',
                help='Location of apache executable'),
        Setting('apache_module_dir',
                default='{{project.apache_module_dir()}}',
                help='Location of apache modules'),
        Setting('server_admin',
                default='{{env.environ["USER"]}}@{{env.fq_hostname}}',
                help='Server admin for Apache'),
        Setting('db_name',
                default='wordpress',
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
                default=None,
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
        tasks.CheckMySQLDatabase('Check database'),
        tasks.Script('Setup database tables',
                     '{{env.base_path}}/wordpress/bin/setup-database.sh'),
        tasks.InstallSupervisorConfig(),
        tasks.SaveURI(path='/blog'),
        ]

    def extra_modules(self):
        dist, version = get_platform()
        if dist == 'Ubuntu':
            if version == '6.10':
                # Edgy:
                return self.interpolate('LoadModule rewrite_module {{config.apache_module_dir}}/mod_rewrite.so')
            else:
                # Feisty, probably
                return self.interpolate('''\
    LoadModule mime_module {{config.apache_module_dir}}/mod_mime.so 
    LoadModule dir_module {{config.apache_module_dir}}/mod_dir.so
    LoadModule authz_host_module {{config.apache_module_dir}}/mod_authz_host.so
    LoadModule rewrite_module {{config.apache_module_dir}}/mod_rewrite.so''')
        elif dist == 'Gentoo':
            # If apache isn't built with the static-modules USE flag, we need these.
                return self.interpolate('''\
    LoadModule mime_module {{config.apache_module_dir}}/mod_mime.so 
    LoadModule dir_module {{config.apache_module_dir}}/mod_dir.so
    LoadModule authz_host_module {{config.apache_module_dir}}/mod_authz_host.so
    LoadModule rewrite_module {{config.apache_module_dir}}/mod_rewrite.so
    LoadModule log_config_module {{config.apache_module_dir}}/mod_log_config.so''')
        elif dist == 'Darwin': # Mac OS X
            return self.interpolate('''\
    LoadModule mime_module {{config.apache_module_dir}}/mod_mime.so 
    LoadModule dir_module {{config.apache_module_dir}}/mod_dir.so
    LoadModule access_module {{config.apache_module_dir}}/mod_access.so
    LoadModule rewrite_module {{config.apache_module_dir}}/mod_rewrite.so
    LoadModule log_config_module {{config.apache_module_dir}}/mod_log_config.so''')
        else:
            raise OSError(
                "Cannot automatically determine extra_modules from OS")

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


def get_platform():
    """
    Returns (distribution, version)

    Guesses this from looking in different files on the system.
    """
    if os.path.exists('/etc/lsb-release'):
        # Probably Ubuntu-ish
        vars = {}
        f = open('/etc/lsb-release')
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            var, value = line.split('=', 1)
            vars[var] = value
        f.close()
        return (vars['DISTRIB_ID'], vars['DISTRIB_RELEASE'])
    if os.path.exists('/etc/gentoo-release'):
        f = open('/etc/gentoo-release')
        parts = f.readline().split()
        f.close()
        return (parts[0], parts[-1])

    # detect Mac OS X
    platform, version = Popen(["uname", "-sr"], stdout=PIPE).communicate()[0].split()
    if platform == 'Darwin':
        if os.path.exists('/Applications/MAMP'):
            return platform, version
        raise OSError('Mac build requires MAMP installed to /Applications/MAMP (www.mamp.info)')
    raise OSError(
        "Cannot determine the platform")
