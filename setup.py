from setuptools import setup, find_packages
import sys, os

version = '0.7.1'

long_description = (
    open("README.rst").read()
    + '\n' +
    'Changes\n'
    '=======\n'
    + '\n' +
    open("docs/CHANGES.txt").read()
    + '\n' +
    'Contributors\n'
    '************\n'
    + '\n' +
    open("docs/CONTRIBUTORS.rst").read()
    + '\n')


setup(name='fassembler',
      version=version,
      description="Builder for OpenCore",
      long_description=long_description,
      # Get strings from https://pypi.org/pypi?:action=list_classifiers
      classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Environment :: Plugins",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Natural Language :: English",
        "Operating System :: Unix",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.4",
        "Programming Language :: Python :: 2 :: Only",
        "Topic :: Desktop Environment :: File Managers",
        "Topic :: Software Development :: Assemblers",
        "Topic :: System :: Systems Administration",
      ],
      keywords='builder opencore site deployments socialplanning fassembler bootstrap console scripts setup',
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
          'virtualenv==1.5.2',
          'Pygments==1.6',
          'MySQL-python==1.2.3', # At least, some projects require MySQL access
          'pip==1.1',
      ],
      ## FIXME: release all of these once fassembler stabilizes:
      dependency_links=[
          #'http://svn.pythonpaste.org/CmdUtils/trunk#egg=CmdUtils-dev',
          #'http://svn.pythonpaste.org/Tempita/trunk#egg=Tempita-dev',
          'https://dist.socialplanning.org/eggs/virtualenv-1.5.2.tar.gz#egg=virtualenv-1.5.2',
          'https://dist.socialplanning.org/eggs/Pygments-1.6.tar.gz#egg=Pygments-1.6',
          'https://dist.socialplanning.org/eggs/MySQL-python-1.2.3.tar.gz#egg=MySQL-python-1.2.3',
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
