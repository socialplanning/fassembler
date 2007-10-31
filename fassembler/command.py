import sys
from cmdutils import OptionParser, CommandError, main_func

## The long description of how this command works:
description = """\
"""

parser = OptionParser(
    usage="%prog [OPTIONS] ARGS",
    version_package='fassembler',
    description=description,
    ## Set these to require a minimum or maximum number of arguments:
    #max_args=None,
    #min_args=None,
    ## Set this to true to create a logger:
    use_logging=False,
    )

#parser.add_option(
#    '-s', '--long',
#    help="help message",
#    metavar="VAR_NAME",
#    dest="options_var",
#    )

parser.add_verbose()

@main_func(parser)
def main(options, args):
    ## Do stuff here; raise CommandError if the arguments don't make
    ## sense
    pass

if __name__ == '__main__':
    main()
