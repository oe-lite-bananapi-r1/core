from oebakery import info
import tarfile
import os
import sys
import subprocess
import datetime


def format_textblock(text, indent=2, width=78, first_indent=None):
    """
    Format a text block.

    This function formats a block of text. The text is broken into
    tokens. (Whitespace is NOT preserved.) The tokens are reassembled
    at the specified level of indentation and line width.  A string is
    returned.

    Arguments:
        `text`   -- the string to be reformatted.
        `indent` -- the integer number of spaces to indent by.
        `width`  -- the maximum width of formatted text (including indent).
    """
    if first_indent is None:
        line_width = width - indent
    else:
        line_width = width - first_indent
    out = []
    stack = [word for word in text.replace("\n", " ").split(" ") if word]
    while stack:
        line = ""
        #width = width - indent
        while stack:
            if line and (len(line) + len(" " + stack[0]) > line_width):
                break
            if line: line += " "
            line += stack.pop(0)
        if first_indent is None:
            out.append(" "*indent + line)
        else:
            out.append(" "*first_indent + line)
            line_width = width - indent
            first_indent = None
    return "\n".join(out)


class NullStream:
    def write(self, text):
        pass


class TeeStream:
    def __init__(self, files):
        self.files = files
        return
    def write(self, text):
        for file in self.files:
            file.write(text)
        return


def shcmd(cmd, dir=None, quiet=False, success_returncode=0,
          silent_errorcodes=[], **kwargs):

    if isinstance(cmd, basestring):
        cmdstr = cmd
        cmdname = cmd.split(None, 1)[0]
        kwargs["shell"] = True
    else:
        cmdstr = " ".join(cmd)
        cmdname = cmd[0]

    if dir:
        pwd = os.getcwd()
        os.chdir(dir)

    if not quiet:
        if dir:
            print '%s> %s'%(dir, cmdstr)
        else:
            print '> %s'%(cmdstr,)

    try:
        retval = None
        if quiet:
            process = subprocess.Popen(cmd, stdin=sys.stdin,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, **kwargs)
            output = process.communicate()[0]
            if process.returncode == success_returncode:
                retval = output
            elif not process.returncode in silent_errorcodes:
                print "Error: Command failed: %r: %d"%(
                    cmdstr, process.returncode)
        else:
            returncode = subprocess.call(cmd, stdin=sys.stdin, **kwargs)
            if returncode == success_returncode:
                retval = True
            elif not returncode in silent_errorcodes:
                print "Error: Command failed: %r: %d"%(cmdstr, returncode)
    except OSError, e:
        if e.errno == 2:
            print "Error: Command not found:", cmdname
        else:
            print "Error: Command failed: %r"%(cmdstr)

    if dir:
        os.chdir(pwd)

    return retval


class TarFile(tarfile.TarFile):
    def __enter__(self):
        try:
            return tarfile.TarFile.__enter__(self)
        except AttributeError:
            if self.fileobj is None:
                raise ValueError("Read Error")
            return self
    def __exit__(self, *args):
        try:
            tarfile.TarFile.__exit__(self, *args)
        except AttributeError:
            self.close()


def progress_info(msg, total, current):
    if os.isatty(sys.stdout.fileno()):
        fieldlen = len(str(total))
        template = "\r%s: %%%dd / %%%dd [%2d %%%%]"%(msg, fieldlen, fieldlen,
                                                 current*100//total)
        #sys.stdout.write("\r%s: %04d/%04d [%2d %%]"%(
        sys.stdout.write(template%(current, total))
        if current == total:
            sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        if current == 0:
            sys.stdout.write("%s, please wait..."%(msg))
        elif current == total:
            sys.stdout.write("done.\n")
        sys.stdout.flush()


def unique_list(seq):
    seen = set()
    seen_add = seen.add
    return [ x for x in seq if x not in seen and not seen_add(x)]


def makedirs(path, mode=0777):
    if os.path.exists(path):
        return
    os.makedirs(path, mode)
    return


def touch(path, makedirs=False, truncate=False):
    if truncate:
        mode = 'w'
    else:
        mode = 'a'
    if makedirs:
        globals()['makedirs'](os.path.dirname(path))
    with open(path, mode):
        os.utime(path, None)


def timing_info(msg, start):
    msg += " time "
    delta = datetime.datetime.now() - start
    hours = delta.seconds // 3600
    minutes = delta.seconds // 60 % 60
    seconds = delta.seconds % 60
    milliseconds = delta.microseconds // 1000
    if hours:
        msg += "%dh%02dm%02ds"%(hours, minutes, seconds)
    elif minutes:
        msg += "%dm%02ds"%(minutes, seconds)
    else:
        msg += "%d.%03d seconds"%(seconds, milliseconds)
    info(msg)
    return
