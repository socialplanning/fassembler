This is fassembler, the build system for OpenCore
Home page: http://www.coactivate.org/projects/fassembler/project-home


Overview
========

This could be general-purpose build software a la GNU Make, Buildit,
et al.  But it's developed specifically for the build and deployment
needs of the software that runs CoActivate.org.


How to Use Fassembler
=====================

See http://www.coactivate.org/projects/fassembler/howto

Requirements
============

Python >= 2.4

... and?


License
========

See doc/license.txt


Hacking Fassembler
===================


To add a project
----------------

* Create a subclass of fassembler.project:Project

* Add an entry point to setup() in setup.py

* Update doc/ports.txt and fassembler.topp:CheckBasePorts.port_range
  if needed.

