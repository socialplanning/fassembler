import subprocess

def asbool(obj):
    if isinstance(obj, (str, unicode)):
        obj = obj.strip().lower()
        if obj in ['true', 'yes', 'on', 'y', 't', '1']:
            return True
        elif obj in ['false', 'no', 'off', 'n', 'f', '0']:
            return False
        else:
            raise ValueError(
                "String is not true/false: %r" % obj)
    return bool(obj)

def popen(args, raise_on_returncode=True, **kw):
    # Got tired of writing this over and over.
    kw.setdefault('stdout', subprocess.PIPE)
    kw.setdefault('stderr', subprocess.STDOUT)
    proc = subprocess.Popen(args, **kw)
    stdout, stderr = proc.communicate()
    if raise_on_returncode and proc.returncode:
        raise OSError("Running %r failed.\nOutput:\n%s" %
                      (' '.join(args), stderr or stdout))
    return proc.returncode, stdout, stderr
