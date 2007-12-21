The mkzeoinstance script doesn't actually support "skeletons" in the same way
that mkzopeinstance does.  The zeo.conf file is put in place by an fassembler
EnsureFile task, overwriting the default file that mkzeoinstance creates.
