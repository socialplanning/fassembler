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
        Setting('spec',
                default=os.path.join(os.path.dirname(__file__), 'opencore-files', 'opencore-requirements.txt'),
                help='Specification of packages to install'),
        Setting('zope_instance',
                default='var/opencore/zope',
                help='Instance home for Zope'),
        Setting('zeo_instance',
                default='var/opencore/zeo',
                help='Instance home for ZEO'),
        Setting('zope_user',
                default='{{env.parse_auth(env.config.get("general", "admin_info_filename")).username}}',
                help='Default admin username'),
        Setting('zope_password',
                default='{{env.parse_auth(env.config.get("general", "admin_info_filename")).password}}',
                help='Admin password'),
        Setting('port',
                default='{{env.config.getint("general", "base_port")+int(config.port_offset)}}',
                help="Port to install Zope on"),
        Setting('port_offset',
                default='1',
                help='Offset from base_port for Zope'),
        Setting('host',
                default='localhost',
                help='Interface/host to serve Zope on'),
        Setting('zeo_port',
                default='{{env.config.getint("general", "base_port")+int(config.zeo_port_offset)}}',
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
        Setting('zope_svn_repo',
                default='http://svn.zope.de/zope.org/Zope/branches/2.9',
                help='Location of Zope svn'),
        Setting('zope_egg',
                default='Zope==2.98_final',
                help='Requirement for installing Zope'),
        ## FIXME: not sure if this is right:
        ## FIXME: should also be more global
        ## FIXME: also, type check on bool-ness
        Setting('debug',
                default='0',
                help='Whether to start Zope in debug mode'),
        Setting('email_confirmation',
                default='0',
                help='Whether to send email configuration'),
        ]

    files_dir = os.path.join(os.path.dirname(__file__), 'opencore-files')
    patch_dir = os.path.join(files_dir, 'patches')
    skel_dir = os.path.join(files_dir, 'zope_skel')

    ## FIXME: I don't think this is the right way to start Zope, even under
    ## Supervisor:
    start_script_template = """\
#!/bin/sh
exec {{env.base_path}}/bin/zopectl fg
"""

    actions = [
        tasks.VirtualEnv(),
        tasks.InstallSpec('Install Zope',
                          '{{config.spec}}'),
        #tasks.Patch('Patch Zope', os.path.join(patch_dir, '*.diff'), '{{config.zope_source}}'),
        tasks.CopyDir('Create custom skel',
                      skel_dir, '{{project.name}}/src/Zope/custom_skel'),
        #tasks.Script('Configure Zope', [
        #'./configure', '--prefix', '{{project.build_properties["virtualenv_path"]}}'],
        #cwd='{{config.zope_source}}'),
        tasks.Script('Make Zope', ['make'], cwd='{{config.zope_source}}'),
        tasks.Script('Install Zope', ['make', 'inplace'], cwd='{{config.zope_source}}'),
        tasks.Script('Make Zope Instance', [
        'python', '{{config.zope_source}}/bin/mkzopeinstance.py', '--dir', '{{config.zope_instance}}',
        '--user', '{{config.zope_user}}:{{config.zope_password}}',
        '--skelsrc', '{{config.zope_source}}/custom_skel'],
                     use_virtualenv=True),
        tasks.Script('Make ZEO Instance', [
        'python', '{{config.zope_source}}/bin/mkzeoinstance.py', '{{config.zeo_instance}}', '{{config.zeo_port}}'],
                     use_virtualenv=True),
        ## FIXME: linkzope and linkzopebinaries?
        ## FIXME: Write start script
        tasks.InstallSupervisorConfig(),
        tasks.EnsureFile('Write the start script',
                         '{{env.base_path}}/bin/start-{{project.name}}',
                         content=start_script_template,
                         svn_add=True,
                         executable=True),
        tasks.SaveURI(),
        # ZEO doesn't really have a uri
        ]
