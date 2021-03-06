==========
fassembler
==========

This is fassembler, the build system for OpenCore
Home page: https://www.coactivate.org/projects/fassembler/project-home


Overview
========

This could be general-purpose build software a la GNU Make, Buildit,
et al.  But it's developed specifically for the build and deployment
needs of the software that runs CoActivate.org.


How to Use Fassembler
=====================

See https://www.coactivate.org/projects/fassembler/howto


Hacking Fassembler
===================


To add a project
----------------

* Create a subclass of fassembler.project:Project

* Add an entry point to setup() in setup.py

* Update doc/ports.txt and fassembler.topp:CheckBasePorts.port_range
  if needed.


Requirements
============

Python >= 2.4

... and?


Installation
============

For install the latest released for this package, execute the following command:

::

  $ pip-2.4 install fassembler

For install this package from development branch, execute the following command:

::

  $ git clone https://github.com/socialplanning/fassembler.git
  $ cd ./fassembler
  $ pip-2.4 install -f https://dist.socialplanning.org/eggs/ \
                    -r requirements.txt
  $ python2.4 setup.py install


Contribute
==========

- Issue Tracker: https://github.com/socialplanning/fassembler/issues
- Source Code: https://github.com/socialplanning/fassembler
- Documentation: https://www.coactivate.org/projects/fassembler


License
=======

The project is licensed under the **GPLv2**, more details see ``docs/LICENSE.txt`` file.
