"""
Support for creating stub egg-info so easy_install or pip can know about
packages that don't have any.

LIMITATIONS:

 - This is rather Zope-specific at the moment.

 - Assumes all Zope 2.N versions are equivalent - eg. 2.10.1 == 2.10.8

 - These fake eggs do not support entry points.

 - Doesn't detect correct versions of some things, eg. mechanize.

 - You still can't import directly from normal python interpreter
  (but you can from zopectl of course) 

"""

##############################################################################
#
# Based on plone.recipe.zope2install,
# which is Copyright (c) 2007 Zope Corporation and Contributors.
# All Rights Reserved under the Zope Public License, Version 2.1 (ZPL).
#
##############################################################################

import os
import re
import sys

EGG_INFO_CONTENT = """Metadata-Version: 1.0
Name: %s
Version: %s
"""

DEFAULT_FAKE_EGGS = [
    'Acquisition',
    'ClientForm',
    'DateTime',
    'docutils',
    'ExtensionClass',
    'mechanize',
    'pytz',
    'RestrictedPython',
    'Persistence',
    'tempstorage',
    'ZConfig',
    'zLOG',
    'zodbcode',
    'ZODB3',
    'zdaemon',
    'Zope2',
]

class FakeLibInfo(object):
    """
    a really simple to store informations about libraries to be faked
    as eggs.
    """
    version = ''
    name = ''

    def __init__(self, name, version='0.0'):
        self.version = version
        self.name = name


class FakeEggsInstaller(object):

    def __init__(self, zopelocation, sitebase):
        self.fake_eggs_folder = os.path.join(sitebase, 'lib',
                                             "python%d.%d"  % (sys.version_info[:2]), 
                                             'site-packages')
        self.options = {'zopelocation': zopelocation, # root of zope source
                        }
        self.zope2version = self._getZope2Version()
        additional = [] #XXX read more fake egg names from args?
        additional_names = []
        # Build up a list of all fake egg names without a version spec
        for line in additional:
            if '=' in line:
                spec = line.strip().split('=')
                name = spec[0].strip()
            else:
                name = line.strip()
            additional_names.append(name)
        # Add defaults to the specified set if the egg is not specified
        # in the additional-fake-eggs option, so you can overwrite one of
        # the default eggs with one including a version spec
        for name in DEFAULT_FAKE_EGGS:
            if name not in additional_names:
                additional.append(name)
        self.additional_fake_eggs = additional
        
    def _getInstalledLibs(self, location, prefix):
        installedLibs = []
        for lib in os.listdir(location):
            if lib.startswith('.'):
                # Skip hidden dirs, eg. '.svn'
                continue
            if prefix:
                name = '%s.%s' % (prefix, lib)
            else:
                name = lib
            if (os.path.isdir(os.path.join(location, lib)) and
                name not in [libInfo.name for libInfo in self.libsToFake]):
                # Only add the package if it's not yet in the list
                version = self._getVersion(name)
                installedLibs.append(FakeLibInfo(name, version))
        return installedLibs

    def fakeEggs(self, location=None, prefix=None):
        if location is None:
            self._getZopeLibs()
        else:
            assert prefix is not None
            self.libsToFake = self._getInstalledLibs(location, prefix)
        self._doFakeEggs()

    def _getZopeLibs(self):
        zope2Location = self.options['zopelocation']
        zopeLibZopeLocation = os.path.join(zope2Location, 'lib', 'python',
                                           'zope')
        zopeLibZopeAppLocation = os.path.join(zope2Location, 'lib', 'python',
                                              'zope', 'app')
        fakeEggsFolderLocation = self.fake_eggs_folder
        if not os.path.isdir(fakeEggsFolderLocation):
            os.mkdir(fakeEggsFolderLocation)

        self.libsToFake = []
        for lib in self.additional_fake_eggs:
            # 2 forms available:
            #  * additional-fake-eggs = myEgg
            #  * additional-fake-eggs = myEgg=0.4
            if '=' in lib:
                lib = lib.strip().split('=')
                eggName = lib[0].strip()
                version = lib[1].strip()
                libInfo = FakeLibInfo(eggName, version)
            else:
                eggName = lib.strip()
                version = self._getVersion(eggName, fallback=None)
                if version is not None:
                    libInfo = FakeLibInfo(eggName, version)
                else:
                    libInfo = FakeLibInfo(eggName)

            self.libsToFake.append(libInfo)

        self.libsToFake += self._getInstalledLibs(zopeLibZopeLocation, 'zope')
        self.libsToFake += self._getInstalledLibs(zopeLibZopeAppLocation,
                                                  'zope.app')

    def _doFakeEggs(self):
        fakeEggsFolderLocation = self.fake_eggs_folder
        for libInfo in self.libsToFake:
#             fakeLibDirLocation = os.path.join(fakeEggsFolderLocation,
#                                               libInfo.name)
            # XXX easy_install doesn't seem to find them that way.
            # If we put the info files directly in site-packages, it does.
            # Or at least, it decides not to reinstall, in a kind of odd way...
            # we might be relying on bogus behavior?
            # OTOH, this satisfies Pip too.
            fakeLibDirLocation = fakeEggsFolderLocation
            if not os.path.isdir(fakeLibDirLocation):
                os.mkdir(fakeLibDirLocation)
            # Might as well put version info in the egg-info filename.
            name = '%s-%s.egg-info' % (libInfo.name, libInfo.version)
            fakeLibEggInfoFile = os.path.join(fakeLibDirLocation, name)
            fd = open(fakeLibEggInfoFile, 'w')
            fd.write(EGG_INFO_CONTENT % (libInfo.name, libInfo.version))
            fd.close()


    def _getZope2Version(self):
        changes = open(os.path.join(self.options['zopelocation'],
                                    'doc', 'CHANGES.txt'))
        version_re = re.compile(r'^\s+Zope\s+2\.([0-9]+)\.([0-9]+)')
        for line in changes:
            line_has_version = version_re.search(line)
            if line_has_version:
                major = 2
                minor = int(line_has_version.group(1))
                point = int(line_has_version.group(2))
                return major, minor #, point
        raise RuntimeError("Could not guess Zope version")

    def _getVersion(self, name, fallback=True):
        z2_version = self.zope2version
        if name == 'Zope2':
            return '.'.join([str(i) for i in z2_version])
        if name.startswith('zope.'):
            default_version = self.zope2_versions_map[z2_version]['_z3']
        else:
            default_version = '0.0'
        version = self.zope2_versions_map[z2_version].get(name)
        if version is None and fallback:
            return default_version
        return version
                
    # I could get really detailed here, but eh.
    # XXX Does not handle manually upgraded Five.
    zope2_versions_map = {(2, 11):
                              {'_z3': '3.3', 'ZODB3': '3.8',
                               },
                          (2, 10):
                              {'_z3': '3.3', 'ZODB3': '3.7',
                               },
                          (2, 9):
                              {'_z3': '3.2', 'ZODB3': '3.6'},
                          (2, 8):
                              {'_z3': '3.0', 'ZODB3': '3.4'},
                          }

