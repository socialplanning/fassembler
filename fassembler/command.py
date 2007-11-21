import sys
import os
import re
from cmdutils import OptionParser, CommandError, main_func
import pkg_resources
from fassembler.filemaker import Maker
from fassembler.config import ConfigParser
from fassembler.text import indent
from fassembler.environ import Environment

## The long description of how this command works:
description = """\
fassembler assembles files.

All files will be installed under BASE_DIR, typically in a
subdirectory for the project.

To get a list of PROJECTs you can install, use %prog --list-projects

To set a configuration variable, use VARIABLE=VALUE, or
[SECTION]VARIABLE=VALUE.  If you do not use [SECTION] then the
variable will be set globally.
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
    metavar='CONFIG_FILE',
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

@main_func(parser)
def main(options, args):
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
    if base_path.startswith('ase=') or base_path == 'ase':
        # Sign that you used -base instead of --base
        raise CommandError(
            "You gave -b%s; did you mean --base?" % base_path, show_usage=False)
    if not base_path:
        script_path = os.path.abspath(sys.argv[0])
        base_path = os.path.dirname(os.path.dirname(script_path))
        build_ini = os.path.join(base_path, 'etc', 'build.ini')
        if not os.path.exists(build_ini):
            raise CommandError(
                "%s not found; you must provide the --base value" % build_ini)
    project_names, variables = parse_positional(args)
    logger = options.logger
    config = load_configs(options.configs)
    for section, name, value in variables:
        section = section or 'DEFAULT'
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, name, value, filename='<cmdline>')
    maker = Maker(base_path, simulate=options.simulate,
                  interactive=not options.no_interactive, logger=logger,
                  quick=options.quick)
    environ = Environment(base_path, logger=logger)
    projects = []
    for project_name in project_names:
        logger.debug('Finding package %s' % project_name)
        ProjectClass = find_project_class(project_name, logger)
        if ProjectClass is None:
            raise CommandError('Could not find project %s' % project_name, show_usage=False)
        project = ProjectClass(project_name, maker, environ, logger, config)
        projects.append(project)
    success = True
    errors = []
    for project in projects:
        try:
            errors.extend(project.confirm_settings())
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
        raise CommandError('Errors in configuration', show_usage=False)
    for project in projects:
        if options.project_help:
            description = project.make_description()
            print description
        else:
            if len(projects) > 1:
                logger.notify(' Starting project %s' % project.project_name, color='black green_bg')
                logger.indent += 2
            try:
                try:
                    project.run()
                    logger.notify('Done with project %s' % project_name)
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
    if not options.project_help:
        if success:
            logger.notify('Installation successful.')
            environ.save()
        else:
            logger.notify('Installation not completely successful.')
    ## FIXME: commit etc/?

_var_re = re.compile(r'^(?:\[(\w+)\])?\s*(\w+)=(.*)$')

def parse_positional(args):
    project_names = []
    variables = []
    for arg in args:
        match = _var_re.search(arg)
        if match:
            variables.append((match.group(1), match.group(2), match.group(3)))
        else:
            project_names.append(arg)
    return project_names, variables

def find_project_class(project_name, logger):
    if ':' in project_name:
        project_name, ep_name = project_name.split(':', 1)
    else:
        ep_name = 'main'
    try:
        dist = pkg_resources.get_distribution(project_name)
    except pkg_resources.DistributionNotFound, e:
        if ep_name != 'main':
            ## FIXME: log something?
            return None
        logger.debug('Could not get distribution %s: %s' % (project_name, e))
        options = pkg_resources.iter_entry_points('fassembler.project', project_name)
        if not options:
            logger.fatal('NO entry points in [fassembler.project] found with name %s' % project_name)
            return None
        if len(options) > 1:
            logger.fatal('More than one entry point in [fassembler.project] found with name %s: %s'
                         % (project_name, ', '.join(map(repr, options))))
            return None
        return options[0].load()
    else:
        ep = dist.get_entry_info('fassembler.project', ep_name)
        if not ep:
            logger.fatal('Distribution %s (at %s) does not have an entry point %r'
                         % (dist.project_name, dist.location, ep_name))
            return None
        logger.debug('Found entry point %s:main = %s' % (dist, ep))
        return ep.load()

def load_configs(configs):
    conf = ConfigParser()
    ## FIXME: test that all configs exist
    conf.read(configs)
    return conf

############################################################
## Project listing
############################################################

def list_projects(options):
    import traceback
    from cStringIO import StringIO
    for ep in pkg_resources.iter_entry_points('fassembler.project'):
        print '%s (from %s:%s)' % (ep_name(ep), ep.module_name, '.'.join(ep.attrs))
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

def ep_name(ep):
    if ep.name == 'main':
        return str(ep.dist.project_name)
    else:
        return '%s:%s' % (ep.dist.project_name, ep.name)

if __name__ == '__main__':
    main()
