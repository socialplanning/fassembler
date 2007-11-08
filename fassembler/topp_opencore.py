import os
from fassembler.project import Project, Setting
from fassembler import tasks

class OpenCoreProject(Project):
    """
    Install OpenCore
    """

    name = 'opencore'
    title = 'Install OpenCore'

    settings = [
        # zope_source
        Setting('zope_instance',
                default='var/opencore/zope',
                help='Instance home for Zope'),
        Setting('zeo_instance',
                default='var/opencore/zeo',
                help='Instance home for ZEO'),
        Setting('zope_user',
                default='admin',
                help='Default admin username'),
        Setting('zope_password',
                ## FIXME: random?
                default='admin',
                help='Default admin password'),
        Setting('port',
                default='{{env.config.getint("general", "base_port")+int(config.port_offset)}}',
                help="Port to install Zope on"),
        Setting('port_offset',
                default='1',
                help='Offset from base_port for Zope'),
        Setting('zeo_port',
                default='{{env.config.getint("general", "base_port")+int(config.zeo_port_offset)}}',
                help="Port to install ZEO on"),
        Setting('zeo_port_offset',
                default='2',
                help='Offset from base_port for ZEO'),
        Setting('zope_source',
                default='{{project.build_properties["virtualenv_path"]}}/src/Zope',
                help='Location of Zope source'),
        Setting('zope_svn_repo',
                default='svn://svn.zope.org/repos/main/Zope/tags/2.9.8',
                help='Location of Zope svn'),
        ]

    patch_dir = os.path.join(os.path.dirname(__file__), 'opencore-patches')

    actions = [
        tasks.VirtualEnv(),
        tasks.EasyInstall('Install PIL', 'PIL', find_links=['http://dist.repoze.org/simple/PIL/']),
        tasks.SvnCheckout('Check out Zope', '{{config.zope_svn_repo}}',
                          '{{config.zope_source}}'),
        tasks.Patch('Patch Zope', os.path.join(patch_dir, '*.diff'), '{{config.zope_source}}'),
        tasks.Script('Configure Zope', [
        './configure', '--prefix', '{{project.build_properties["virtualenv_path"]}}'],
        cwd='{{config.zope_source}}'),
        tasks.Script('Make Zope', ['make'], cwd='{{config.zope_source}}'),
        tasks.Script('Install Zope', ['make', 'inplace'], cwd='{{config.zope_source}}'),
        tasks.Script('Make Zope Instance', [
        'mkzopeinstance.py', '--dir', '{{config.zope_instance}}'
        '--user', '{{config.zope_user}}:{{config.zope_password}}',
        '--skelsrc', '{{config.zope_source}}/custom_skel'],
                     use_virtualenv=True),
        tasks.Script('Make ZEO Instance', [
        'mkzeoinstance.py', '{{config.zeo_instance}}', '{{config.zeo_port}}'],
                     use_virtualenv=True),
        ## FIXME: linkzope and linkzopebinaries?
        ]
