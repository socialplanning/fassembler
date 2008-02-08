#!/bin/bash

ZOPETEST=<<build-location>>/zope/bin/zopetest

sed 's/^ *exec.*$//g' <<build-location>>/zope/bin/zopectl > $ZOPETEST
echo '"$PYTHON" "$ZOPE_HOME"/bin/test.py -v --config-file "$CONFIG_FILE" "$@"' >> $ZOPETEST
chmod u+x $ZOPETEST

