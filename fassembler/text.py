import textwrap

__all__ = ['indent', 'indent', 'underline']

def indent(text, indent_text, dedent=True):
    if dedent:
        text = _dedent(text)
    lines = text.splitlines(True)
    return ''.join([indent_text+line for line in lines])

def underline(text, char='='):
    text = text.strip()
    return '%s\n%s' % (text, char*len(text))

def dedent(text):
    return textwrap.dedent(text).strip()

_dedent = dedent
