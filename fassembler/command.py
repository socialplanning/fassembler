import sys
from cmdutils import OptionParser, CommandError, main_func
import pkg_resources
from fassembler.filemaker import Maker

## The long description of how this command works:
description = """\
fassembler assembles files.

All files will be installed under BASE_DIR, typically in a
subdirectory for the project.
"""

parser = OptionParser(
    usage="%prog [OPTIONS] BASE_DIR PROJECT [PROJECT...]",
    version_package='fassembler',
    description=description,
    use_logging=True,
    )

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
    '-i', '--interactive',
    action='store_true',
    dest='interactive',
    help='Ask questions interactively')

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
    if len(args) < 2:
        raise CommandError(
            "You must provide at least a base directory and one project")
    base_dir = args[0]
    project_names = args[1:]
    logger = options.logger
    config = load_configs(options.configs)
    maker = Maker(base_dir, simulate=options.simulate,
                  interactive=options.interactive, logger=logger)
    projects = []
    for project_name in project_names:
        logger.debug('Finding package %s' % project_name)
        ProjectClass = find_project_class(project_name, logger)
        if ProjectClass is None:
            raise BadCommand('Could not find project %s' % project_name)
        project = ProjectClass(maker, logger, config)
        projects.append(project)
    for project in projects:
        project.run()
        logger.notify('Done with project %s' % project_name)
    logger.notify('Installation successful.')

def find_project_class(project_name, logger):
    try:
        dist = pkg_resources.get_distribution(project_name)
    except pkg_resources.DistributionNotFound, e:
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
        ep = dist.get_entry_point('fassembler.project', 'main')
        logger.debug('Found entry point %s:main = %s' % (dist, ep))
        return ep.load()


if __name__ == '__main__':
    main()
