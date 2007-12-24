from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='fassembler',
      version=version,
      description="Builder for TOPP",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Ian Bicking',
      author_email='ianb@openplans.org',
      url='http://openplans.org/projects/fassembler',
      license='GPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'CmdUtils',
          #'ScriptTest',
          'Tempita==dev,>=0.1.1dev',
          'INITools==dev,>=0.2.1dev-r3168',
          'virtualenv',
          'MySQL-python', # At least, some projects require MySQL access
      ],
      ## FIXME: release all of these once fassembler stabilizes:
      dependency_links=[
          'http://internap.dl.sourceforge.net/sourceforge/mysql-python/MySQL-python-1.2.2.tar.gz',
          'http://svn.pythonpaste.org/CmdUtils/trunk#egg=CmdUtils-dev',
          'http://svn.colorstudy.com/INITools/trunk#egg=INITools-dev',
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
      zeo = fassembler.topp_opencore:ZEOProject
      wordpress = fassembler.topp_wordpress:WordPressProject
      cabochon = fassembler.topp_products:CabochonProject
      twirlip = fassembler.topp_products:TwirlipProject
      """,
      )
