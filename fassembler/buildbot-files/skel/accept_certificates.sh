#!/bin/bash

# ensure the certificates are accepted for svn
# svn should really have the --no-certificate option,
# but since it doesn't we'll work around

yes p | svn ls https://svn.plone.org/svn/plone
yes p | svn ls https://svn.openplans.org/svn