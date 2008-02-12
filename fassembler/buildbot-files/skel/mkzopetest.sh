#!/bin/bash

ZOPETEST={{config.oc_basedir}}/opencore/zope/bin/zopetest

sed 's/^ *exec.*$//g' {{config.oc_basedir}}/opencore/zope/bin/zopectl > $ZOPETEST
echo '"$PYTHON" "$ZOPE_HOME"/bin/test.py -v --config-file "$CONFIG_FILE" "$@"' >> $ZOPETEST
chmod u+x $ZOPETEST

