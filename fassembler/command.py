"""
This file represents the entry point for the ``fassembler`` script.

It implements the command-line API, and some of the outermost level of setup.
"""

import sys
import os
import re
from cmdutils import OptionParser, CommandError, main_func
import pkg_resources
from fassembler.filemaker import Maker
from fassembler.config import ConfigParser
from fassembler.text import indent
from fassembler.environ import Environment

description = """\
fassembler assembles files.

All files will be installed under BASE_DIR, typically in a
subdirectory for the project.

To get a list of PROJECTs you can install, use %prog --list-projects

To set a configuration variable, use VARIABLE=VALUE, or
SECTION.VARIABLE=VALUE.  If you do not use SECTION then the
variable will be set globally.

If you give 'all' for a project, then all projects listed in
requirements/all-projects.txt will be built/updated.  If you give
'missing' then just unbuilt projects from all-projects.txt will be
built.
"""

parser = OptionParser(
    usage="%prog [OPTIONS] PROJECT [PROJECT...] VARIABLES",
    version_package='fassembler',
    description=description,
    use_logging=True,
    )

parser.add_option(
    '-b', '--base',
    dest='base_path',
    metavar='DIR',
    default=None,
    help='Base directory to install in; if not run from an fassembler-boot.py path, this argument is required')

parser.add_option(
    '-c', '--config',
    metavar='CONFIG_FILE_OR_URL',
    dest='configs',
    action='append',
    default=[],
    help='Config file to load with overrides (you may use this more than once)')

parser.add_option(
    '-n', '--simulate',
    action='store_true',
    dest='simulate',
    help='Simulate (do not write any files or make changes)')

parser.add_option(
    '--no-interactive',
    action='store_true',
    dest='no_interactive',
    help='Do not ask questions interactively')

parser.add_option(
    '--quick',
    action='store_true',
    dest='quick',
    help='Try to do things quickly (may not be as safe)')

parser.add_option(
    '--beep',
    action='store_true',
    dest='beep',
    help='Beep everytime a question is asked')

parser.add_option(
    '-H', '--project-help',
    action='store_true',
    dest='project_help',
    help='Show information about what the project builders do')

parser.add_option(
    '--list-projects',
    action='store_true',
    dest='list_projects',
    help="List available projects")

parser.add_verbose()

#@main_func runs the parser before calling this function.
@main_func(parser)
def main(options, args):
    """
    This implements the command-line fassembler script.
    """
    if options.list_projects:
        if args:
            raise CommandError(
                "You cannot use arguments with --list-projects")
        list_projects(options)
        return
    if len(args) < 1:
        raise CommandError(
            "You must provide at least one project")
    base_path = options.base_path
    if base_path and base_path.startswith('ase=') or base_path == 'ase':
        # Sign that you used -base instead of --base
        raise CommandError(
            "You gave -b%s; did you mean --base?" % base_path, show_usage=False)
    if not base_path:
        script_path = os.path.abspath(sys.argv[0])
        for possible_base_path in os.path.dirname(os.path.dirname(script_path)), os.getcwd():
            build_ini = os.path.join(possible_base_path, 'etc', 'build.ini')
            if os.path.exists(build_ini):
                base_path = possible_base_path
                break
        else:
            raise CommandError(
                "you must provide the --base value or run fassembler from a build base path")
    project_names, variables = parse_positional(args)
    logger = options.logger
    if 'all' in project_names:
        project_names.remove('all')
        extra_projects = get_all_projects(base_path)
        logger.notify('Building projects: %s' % ', '.join(extra_projects))
        project_names += extra_projects
    if 'missing' in project_names:
        project_names.remove('missing')
        extra_projects = get_missing_projects(base_path)
        logger.notify('Building projects: %s' % ', '.join(extra_projects))
        project_names += extra_projects
    config = load_configs(options.configs)
    for section, name, value in variables:
        section = section or 'DEFAULT'
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, name, value, filename='<cmdline>')
    environ = Environment(base_path, logger=logger)
    # Merge both ways:
    merge_config(environ.config, config)
    merge_config(config, environ.config, overwrite=True)
    maker = Maker(base_path, simulate=options.simulate,
                  interactive=not options.no_interactive, logger=logger,
                  quick=options.quick, beep=options.beep)
    environ.maker = maker
    
    projects = []
    for project_name in project_names:
        logger.debug('Finding package %s' % project_name)
        project_name, ProjectClass = find_project_class(project_name, logger)
        if ProjectClass is None:
            raise CommandError('Could not find project %s' % project_name, show_usage=False)
        project = ProjectClass(project_name, maker, environ, logger, config)
        projects.append(project)
    success = True
    errors = []
    # Needs to be writable for easy_install:
    home = os.environ.get('HOME') or os.path.expanduser('~')
    if not os.access(home, os.W_OK):
        errors.append(
            "Cannot write to $HOME directory (%s); change $HOME?" % home)
    for project in projects:
        try:
            errors.extend(project.confirm_settings(
                all_projects=[p.project_name for p in projects]))
        except KeyboardInterrupt:
            raise
        except CommandError:
            raise
        except Exception, e:
            logger.fatal('Error in project %s' % project.project_name, color='bold red')
            logger.fatal('  Error: %s' % e)
            should_continue = maker.handle_exception(sys.exc_info(), can_continue=True)
            if not should_continue:
                raise CommandError('Aborted', show_usage=False)
            errors.append(e)
    if errors:
        logger.fatal('Errors in configuration:\n%s' % '\n'.join(['  * %s' % e for e in errors]))
        ## FIXME: maybe ask if they want to see effective configuration here?
        #config.write(sys.stdout)
        raise CommandError('Errors in configuration', show_usage=False)
    for phase in ['build','setup']:
        for project in projects:
            if options.project_help:
                description = project.make_description()
                print description
            else:
                if len(projects) > 1:
                    logger.notify(' Starting phase %s for project %s' % (phase, project.project_name), color='black green_bg')
                    logger.indent += 2
                try:
                    try:
                        project.run(phase)
                        logger.notify('Done with phase %s for project %s' % (phase, project.project_name))
                        environ.save()
                    finally:
                        if len(projects) > 1:
                            logger.indent -= 2
                except CommandError:
                    raise
                except KeyboardInterrupt:
                    raise CommandError('^C', show_usage=False)
                except Exception, e:
                    success = False
                    continue_projects = maker.handle_exception(sys.exc_info())
                    if continue_projects:
                        continue
                    else:
                        break
                    ## FIXME: should revert environ here
    if not options.project_help:
        if success:
            logger.notify('Installation successful.')
        else:
            logger.notify('Installation not completely successful.')
    ## FIXME: commit etc/?

_var_re = re.compile(r'^(?:\[(\w+)\])?\s*(\w+)=(.*)$')
_dot_var_re = re.compile(r'^(\w+)\.(\w+)=([^=>].*)$')

def parse_positional(args):
    """
    Parses out the positional arguments into fassembler projects and
    variable assignments.
    """
    project_names = []
    variables = []
    for arg in args:
        match = _var_re.search(arg)
        if match:
            variables.append((match.group(1), match.group(2), match.group(3)))
        else:
            match = _dot_var_re.search(arg)
            if match:
                variables.append((match.group(1), match.group(2), match.group(3)))
            else:
                project_names.append(arg)
    return project_names, variables

def get_all_projects(base_path):
    path = os.path.join(base_path, 'requirements', 'all-projects.txt')
    if not os.path.exists(path):
        raise CommandError(
            'You cannot use the project "all" because %s does not exist (maybe you have to do the base build?)' % path,
            show_usage=False)
    f = open(path)
    all_projects = []
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        all_projects.append(line)
    f.close()
    return all_projects

def get_missing_projects(base_path):
    try:
        all = get_all_projects(base_path)
    except CommandError, e:
        raise CommandError(str(e).replace('"all"', '"missing"'))
    path = os.path.join(base_path, 'etc', 'projects.txt')
    if os.path.exists(path):
        f = open(path)
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name = line.split()[0]
            if name in all:
                all.remove(name)
        f.close()
    return all

def find_project_class(project_name, logger):
    """
    Takes a project name (like 'fassembler:opencore') and loads the
    class that is being referred to, using entry points.
    """
    if ':' in project_name:
        dist_name, ep_name = project_name.split(':', 1)
    else:
        dist_name, ep_name = project_name, 'main'
    try:
        dist = pkg_resources.get_distribution(dist_name)
    except pkg_resources.DistributionNotFound, e:
        if ep_name != 'main':
            ## FIXME: log something?
            return project_name, None
        logger.debug('Could not get distribution %s: %s' % (dist_name, e))
        options = list(pkg_resources.iter_entry_points('fassembler.project', project_name))
        if not options:
            logger.fatal('NO entry points in [fassembler.project] found with name %s' % project_name)
            return project_name, None
        if len(options) > 1:
            logger.fatal('More than one entry point in [fassembler.project] found with name %s: %s'
                         % (project_name, ', '.join(map(repr, options))))
            return project_name, None
        return ep_to_name(options[0]), options[0].load()
    else:
        ep = dist.get_entry_info('fassembler.project', ep_name)
        if not ep:
            logger.fatal('Distribution %s (at %s) does not have an entry point %r'
                         % (dist.project_name, dist.location, ep_name))
            return project_name, None
        logger.debug('Found entry point %s:main = %s' % (dist, ep))
        return project_name, ep.load()

def load_configs(configs):
    """
    Load up the configuration files.

    (Configuration files aren't being used for much of anything currently)
    """
    conf = ConfigParser()
    conf.read(configs)
    return conf

def merge_config(source, dest, overwrite=False):
    """
    Merge configuration from config source to config dest

    If overwrite is false then values already set in dest are not
    overwritten.
    """
    for section in source.sections():
        for option in source.options(section):
            if not overwrite and dest.has_option(section, option):
                continue
            if not dest.has_section(section):
                dest.add_section(section)
            source_filename, source_lineno = source.setting_location(section, option)
            dest.set(section, option, source.get(section, option),
                     filename=source_filename, line_number=source_lineno)

############################################################
## Project listing
############################################################

def list_projects(options):
    """
    Implements --list-projects
    """
    import traceback
    from cStringIO import StringIO
    entry_points = [(ep_to_name(ep), ep) for ep in
                    pkg_resources.iter_entry_points('fassembler.project')]
    for name, ep in sorted(entry_points):
        print '%s (from %s:%s)' % (name, ep.module_name, '.'.join(ep.attrs))
        try:
            obj = ep.load()
        except:
            out = StringIO()
            out.write('Exception loading entry point:\n')
            traceback.print_exc(file=out)
            desc = out.getvalue()
        else:
            desc = obj.__doc__
        desc = indent(desc, '  ') or '(undocumented)'
        print desc
        print

def ep_to_name(ep):
    """
    Given a pkg_resources.EntryPoint object, return the name that can
    be used to load that entry point.
    """
    if ep.name == 'main':
        return str(ep.dist.project_name)
    else:
        return ep.name # '%s:%s' % (ep.dist.project_name, ep.name)

if __name__ == '__main__':
    main()
