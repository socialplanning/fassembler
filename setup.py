from setuptools import setup, find_packages
import sys, os

version = '0.7'

readme = open("docs/README.txt").read()
changes = open("docs/CHANGES.txt").read()

desc = """
%s

Changes
=======

%s
""" % (readme, changes)

setup(name='fassembler',
      version=version,
      description="Builder for OpenCore",
      long_description=desc,
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Ian Bicking, Paul Winkler, Josh Bronson, Ethan Jucovy',
      author_email='opencore-dev@lists.coactivate.org',
      url='http://www.coactivate.org/projects/fassembler',
      license='GPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'CmdUtils',
          #'ScriptTest',
          'Tempita==dev,>=0.1.1dev',
          'INITools>=0.3',
          'virtualenv',
          'Pygments',
          'MySQL-python', # At least, some projects require MySQL access
          'pip',
      ],
      ## FIXME: release all of these once fassembler stabilizes:
      dependency_links=[
          'http://svn.pythonpaste.org/CmdUtils/trunk#egg=CmdUtils-dev',
          'http://svn.pythonpaste.org/Tempita/trunk#egg=Tempita-dev',
      ],
      entry_points="""
      [console_scripts]
      fassembler = fassembler.command:main

      [fassembler.project]
      topp = fassembler.topp:ToppProject
      supervisor = fassembler.topp:SupervisorProject
      scripttranscluder = fassembler.topp_products:ScriptTranscluderProject
      tasktracker = fassembler.topp_products:TaskTrackerProject
      deliverance = fassembler.topp_products:DeliveranceProject
      opencore = fassembler.topp_opencore:OpenCoreProject

      extrazope = fassembler.topp_opencore:ExtraZopeProject

      i18ndude = fassembler.topp_opencore:I18nDude
      zeo = fassembler.topp_opencore:ZEOProject
      maildrop = fassembler.topp_opencore:MaildropProject
      wordpress = fassembler.topp_wordpress:WordPressProject
      cabochon = fassembler.topp_products:CabochonProject
      twirlip = fassembler.topp_products:TwirlipProject
      nymap = fassembler.topp_nymap:NYMapProject
      proxy = fassembler.topp_nymap:ProxyProject
      buildmaster = fassembler.topp_buildbot:BuildMasterProject
      buildslave = fassembler.topp_buildbot:BuildSlaveProject
      errorlistener = fassembler.topp_erroreater:ErrorListenerProject
      erroreater = fassembler.topp_erroreater:ErrorEaterProject
      relateme = fassembler.topp_products:RelateMeProject
      brainpower = fassembler.topp_brainpower:BrainpowerProject
      windmill = fassembler.topp_windmill:WindmillProject
      bureau = fassembler.topp_products:BureauProject
      henge = fassembler.topp_products:HengeProject
      feedbacker = fassembler.topp_products:FeedBackerProject
      """,
      )
