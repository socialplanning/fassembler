"""
Builder for TOPP WordPress MU
"""

import MySQLdb
import os
from fassembler.project import Project, Setting
from fassembler import tasks
from subprocess import Popen, PIPE
from fassembler.apache import ApacheMixin

class CheckPHP(tasks.Task):
    """Makes sure PHP was built with required modules"""
    required_modules = ['hash']
    recommended_modules = ['openssl']
    php_cgi_exec = tasks.interpolated('php_cgi_exec')

    def __init__(self, php_cgi_exec, stacklevel=1):
        super(CheckPHP, self).__init__('Check PHP', stacklevel=stacklevel+1)
        self.php_cgi_exec = php_cgi_exec

    def run(self):
        compiled_in_modules = set(Popen([self.php_cgi_exec, '-m'], stdout=PIPE).communicate()[0].split('\n')[1:])
        missing_required = []
        for m in self.required_modules:
            if m not in compiled_in_modules:
                missing_required.append(m)
        missing_recommended = []
        for m in self.recommended_modules:
            if m not in compiled_in_modules:
                missing_recommended.append(m)
        if missing_recommended:
            self.logger.warn('PHP not compiled with recommended modules: %s' % missing_recommended)
        if missing_required:
            raise Exception('PHP not compiled with required modules: %s' % missing_required)

            
class DeleteExtraWPSiteRows(tasks.Task):
    """Sometimes fassembling WordPress erroneously adds a row to the
    wp_site table."""

    db = tasks.interpolated('db')
    user = tasks.interpolated('user')
    passwd = tasks.interpolated('passwd')

    def __init__(self, db, user, passwd, stacklevel=1):
        super(DeleteExtraWPSiteRows, self).__init__('Delete extra rows in wp_site', stacklevel=stacklevel+1)
        self.db = db
        self.user = user
        self.passwd = passwd

    def run(self):
        db = MySQLdb.connect(db=self.db, user=self.user, passwd=self.passwd)
        c = db.cursor()
        c.execute('delete from wp_site where id > 1')


class WordPressProject(Project, ApacheMixin):
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
                default='{{project.req_settings.get("wordpress_repo", \
                    "https://svn.openplans.org/svn/vendor/wordpress-mu/openplans/trunk")}}',
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
        Setting('topp_wordpress_theme',
                default='{{project.req_settings.get("topp_wordpress_theme", "openplans")}}',
                help='Theme for wordpress (template option)'),
        ]

    skel_dir = os.path.join(os.path.dirname(__file__), 'wordpress-files', 'skel')

    actions = [
        tasks.SaveSetting('Save the wordpress theme (template)',
                          {'topp_wordpress_theme': '{{config.topp_wordpress_theme}}'},
                          section='applications'),
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
        DeleteExtraWPSiteRows(db='{{config.db_name}}',
                              user='{{config.db_username}}',
                              passwd='{{config.db_password}}'),
        ]

    depends_on_projects = ['fassembler:topp']
    depends_on_executables = [('httpd', 'apache2')]

    def secret(self):
        f = open(self.environ.config.get('general', 'topp_secret_filename'), 'rb')
        c = f.read()
        f.close()
        return c
    
