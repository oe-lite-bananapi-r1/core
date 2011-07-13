# -*- mode:python; -*-

inherit arch
inherit utils
inherit stage
inherit package
inherit mirrors

# FIXME: inherit in specialized classes, so that fx. image does not have
# to have do_fetch
inherit fetch

addtask configure after do_unpack do_patch
addtask compile after do_configure
addtask install after do_compile
addtask fixup after do_install
addtask build after do_fixup
addtask buildall after do_build
addtask clean

addtask listtasks
addtask checkuri
addtask checkuriall after do_checkuri

do_build = ""
do_build[func] = "1"


# Default recipe type is machine, so other recipe type classes must
# override this, and any other recipe type defaults as needed
RECIPE_TYPE = "machine"
RE = ""

CLASS_DEPENDS = ""

#
# Import standard Python modules as well as custom OE modules
# (disabled for now...)
#

#addhandler oe_import

#
# Shell functions for printing out messages in the BitBake output
#

die() {
    oefatal "$*"
}

oenote() {
    echo "NOTE:" "$*"
}

oewarn() {
    echo "WARNING:" "$*"
}

oefatal() {
    echo "FATAL:" "$*"
    exit 1
}

oedebug() {
    test $# -ge 2 || {
        echo "Usage: oedebug level \"message\""
        exit 1
    }

    test ${OEDEBUG:-0} -ge $1 && {
        shift
        echo "DEBUG:" $*
    }
}
oedebug[expand] = "0"


do_listtasks[nostamp] = "1"
python do_listtasks() {
    import sys
    # emit variables and shell functions
    #bb.data.emit_env(sys.__stdout__, d)
    # emit the metadata which isnt valid shell
    for e in d.keys():
        if bb.data.getVarFlag(e, 'task', d):
            sys.__stdout__.write("%s\n" % e)
}


do_clean[dirs] = "${TOPDIR}"
do_clean[nostamp] = "1"
python do_clean() {
    """clear the build and temp directories"""
    import shutil
    workdir = d.getVar("WORKDIR", True)
    bb.note("removing " + workdir)
    shutil.rmtree(workdir)
    stampdir = d.getVar("STAMPDIR", True)
    bb.note("removing " + stampdir)
    shutil.rmtree(stampdir)
}


do_checkuri[nostamp] = "1"
python do_checkuri() {
    import sys

    localdata = bb.data.createCopy(d)
    bb.data.update_data(localdata)

    src_uri = bb.data.getVar('SRC_URI', localdata, 1)

    try:
        bb.fetch.init(src_uri.split(),d)
    except bb.fetch.NoMethodError:
        (type, value, traceback) = sys.exc_info()
        raise bb.build.FuncFailed("No method: %s" % value)

    try:
        bb.fetch.checkstatus(localdata)
    except bb.fetch.MissingParameterError:
        (type, value, traceback) = sys.exc_info()
        raise bb.build.FuncFailed("Missing parameters: %s" % value)
    except bb.fetch.FetchError:
        (type, value, traceback) = sys.exc_info()
        raise bb.build.FuncFailed("Fetch failed: %s" % value)
    except bb.fetch.MD5SumError:
        (type, value, traceback) = sys.exc_info()
        raise bb.build.FuncFailed("MD5  failed: %s" % value)
    except:
        (type, value, traceback) = sys.exc_info()
        raise bb.build.FuncFailed("Unknown fetch Error: %s" % value)
}

do_checkuriall[recadeptask] = "do_checkuri"
do_checkuriall[nostamp] = True
do_checkuriall[func] = True

do_buildall[recadaptask] = "do_build"
do_buildall[func] = True

do_configure[dirs] = "${S} ${B}"

do_compile[dirs] = "${S} ${B}"

do_install[dirs] = "${D} ${S} ${B}"
do_install[cleandirs] = "${D}"

FIXUP_FUNCS += "\
install_strip \
"

def do_fixup(d):
    for funcname in (d.get("FIXUP_FUNCS") or "").split():
        function = d.get_function(funcname)
        if not function.run(os.getcwd()):
            return False

do_fixup[dirs] = "${D}"

python install_strip () {
    import stat
    def isexec(path):
        try:
            s = os.stat(path)
        except (os.error, AttributeError):
            return 0
        return (s[stat.ST_MODE] & stat.S_IEXEC)

    if (bb.data.getVar('INHIBIT_PACKAGE_STRIP', d, True) != '1'):
        for root, dirs, files in os.walk(os.getcwd()):
            for f in files:
               file = os.path.join(root, f)
               if os.path.islink(file) or os.path.isdir(file):
                   continue
               if isexec(file) or ".so" in os.path.basename(file):
                   runstrip(file, d)
}
install_strip[dirs] = "${D}"
install_strip[import] = "runstrip"


def runstrip(file, d):
    # Function to strip a single file, called from populate_packages below
    # A working 'file' (one which works on the target architecture)
    # is necessary for this stuff to work, hence the addition to do_package[depends]

    import commands, stat, re, magic

    pathprefix = "export PATH=%s; " % bb.data.getVar('PATH', d, True)
    print "pathprefix =",pathprefix

    filemagic = magic.open(magic.MAGIC_NONE)
    filemagic.load()
    filetype = filemagic.file(file)

    if "not stripped" not in filetype:
        print "runstrip() skip %s"%(file)
        return
    target_elf = d.getVar('TARGET_ELF', True)
    if target_elf:
        target_elf = re.compile(target_elf)
    host_elf = d.getVar('HOST_ELF', True)
    if host_elf:
        host_elf = re.compile(host_elf)
    build_elf = d.getVar('BUILD_ELF', True)
    if build_elf:
        build_elf = re.compile(build_elf)

    if host_elf and host_elf.match(filetype):
        varprefix = ""
    elif target_elf and target_elf.match(filetype):
        varprefix = "TARGET_"
    elif build_elf and build_elf.match(filetype):
        varprefix = "BUILD_"
    else:
        return

    strip = d.getVar("%sSTRIP"%(varprefix), True)
    if not strip:
        bb.error("runstrip() no or empty %sSTRIP var"%(varprefix))
        return

    objcopy = d.getVar("%sOBJCOPY"%(varprefix), True)
    if not objcopy:
        bb.error("runstrip() no or empty %sOBJCOPY var"%(varprefix))
        return

    # If the file is in a .debug directory it was already stripped,
    # don't do it again...
    if os.path.dirname(file).endswith(".debug"):
        bb.note("Already ran strip")
        return

    newmode = None
    if not os.access(file, os.W_OK):
        origmode = os.stat(file)[stat.ST_MODE]
        newmode = origmode | stat.S_IWRITE
        os.chmod(file, newmode)

    extraflags = ""
    if ".so" in file and "shared" in filetype:
        extraflags = "--remove-section=.comment --remove-section=.note --strip-unneeded"
    elif "shared" in filetype or "executable" in filetype:
        extraflags = "--remove-section=.comment --remove-section=.note"

    bb.utils.mkdirhier(os.path.join(os.path.dirname(file), ".debug"))
    debugfile=os.path.join(os.path.dirname(file), ".debug", os.path.basename(file))

    stripcmd = "'%s' %s '%s'"                       % (strip, extraflags, file)
    objcpcmd = "'%s' --only-keep-debug '%s' '%s'"   % (objcopy, file, debugfile)
    objlncmd = "'%s' --add-gnu-debuglink='%s' '%s'" % (objcopy, debugfile, file)

    print "runstrip() %s"%(objcpcmd)
    print "runstrip() %s"%(stripcmd)
    print "runstrip() %s"%(objlncmd)

    ret, result = commands.getstatusoutput("%s%s" % (pathprefix, objcpcmd))
    if ret:
        bb.note("runstrip() '%s' %s" % (objcpcmd,result))

    ret, result = commands.getstatusoutput("%s%s" % (pathprefix, stripcmd))
    if ret:
        bb.note("runstrip() '%s' %s" % (stripcmd,result))

    ret, result = commands.getstatusoutput("%s%s" % (pathprefix, objlncmd))
    if ret:
        bb.note("runstrip() '%s' %s" % (objlncmd,result))

    if newmode:
        os.chmod(file, origmode)


# Make sure TARGET_ARCH isn't exported
# (breaks Makefiles using implicit rules, e.g. quilt, as GNU make has this
# in them, undocumented)
TARGET_ARCH[unexport] = "1"

# Make sure MACHINE isn't exported
# (breaks binutils at least)
MACHINE[unexport] = "1"

# Make sure DISTRO isn't exported
# (breaks sysvinit at least)
DISTRO[unexport] = "1"


addhook base_after_parse to post_recipe_parse first
def base_after_parse(d):
    source_mirror_fetch = bb.data.getVar('SOURCE_MIRROR_FETCH', d, 0)

    if not source_mirror_fetch:
        need_host = bb.data.getVar('COMPATIBLE_HOST', d, 1)
        if need_host:
            import re
            this_host = bb.data.getVar('HOST_SYS', d, 1)
            if not re.match(need_host, this_host):
                raise bb.parse.SkipPackage("incompatible with host %s" % this_host)

        need_machine = bb.data.getVar('COMPATIBLE_MACHINE', d, 1)
        if need_machine:
            import re
            this_machine = bb.data.getVar('MACHINE', d, 1)
            if this_machine and not re.match(need_machine, this_machine):
                raise bb.parse.SkipPackage("incompatible with machine %s" % this_machine)

    pn = bb.data.getVar('PN', d, 1)

    use_nls = bb.data.getVar('USE_NLS_%s' % pn, d, 1)
    if use_nls != None:
        bb.data.setVar('USE_NLS', use_nls, d)

    fetcher_depends = ""

    # Git packages should DEPEND on git-native
    srcuri = bb.data.getVar('SRC_URI', d, 1)
    if "git://" in srcuri:
        fetcher_depends += " git-native "

    # Mercurial packages should DEPEND on mercurial-native
    elif "hg://" in srcuri:
        fetcher_depends += " mercurial-native "

    # OSC packages should DEPEND on osc-native
    elif "osc://" in srcuri:
        fetcher_depends += " osc-native "

    bb.data.setVar('FETCHER_DEPENDS', fetcher_depends[1:], d)

    # FIXME: move to insane.bbclass
    provides = bb.data.getVar('PROVIDES', d, True)
    if provides:
        bb.note("Ignoring PROVIDES as it does not make sense with OE-core (PROVIDES='%s')"%provides)


addhook core_machine_override to post_recipe_parse first after fetch_init
def core_machine_override(d):

    machine = d.get("MACHINE")
    if not machine:
        return

    recipe_arch = d.get("RECIPE_ARCH")

    def src_uri_machine_override():
        file_dirname = d.get("FILE_DIRNAME")
        filespaths = []
        for p in d.get("FILESPATHPKG").split(":"):
            path = os.path.join(file_dirname, p, machine)
            if os.path.isdir(path):
                filespaths.append(path)
        if len(paths) != 0:
            for fetcher in d["__fetch"]:
                if not fetcher.scheme == "file":
                    continue
                path = fetcher.fetcher.fullpath()
                for filespath in filespaths:
                    if path.startswith(filespath):
                        return True
        return False

    if src_uri_machine_override():
        if d.get("TARGET_ARCH") == d.get("MACHINE_ARCH"):
            d["MACHINE_OVERRIDE"] = ".${MACHINE}"
        else:
            raise Exception("Machine override of %s recipe"%(d["RECIPE_TYPE"]))

addhook blacklist to post_recipe_parse first after preconditions
def blacklist(d):
    import re
    blacklist_var = (d.getVar("BLACKLIST_VAR", True) or "").split()
    blacklist_prefix = (d.getVar("BLACKLIST_PREFIX", True) or "").split()
    blacklist = "$|".join(blacklist_var) + "$"
    if blacklist_prefix:
        blacklist += "|" + "|".join(blacklist_prefix)
    if not blacklist:
        return
    sre = re.compile(blacklist)
    for var in d.keys():
        if sre.match(var):
            d.delVar(var)

addhook preconditions to post_recipe_parse first after set_useflags
def preconditions(d):
    for var in d.get_vars("precondition"):
        del d[var]

inherit useflags
inherit sanity

addhook core_varname_expansion to post_recipe_parse first
def core_varname_expansion(d):
    for varname in d.keys():
        try:
            expanded_varname = d.expand(varname)
        except oelite.meta.ExpansionError as e:
            print "Unable to expand variable name:", varname
            e.print_details()
            raise Exception(42)
        if expanded_varname != varname:
            flags = d.get_flags(varname, prune_var_value=False)
            #print "flags =",flags
            for flag in flags:
                if flag == "__overrides":
                    overrides = flags[flag]
                    old_overrides = d.get_flag(expanded_varname, flag)
                    if not old_overrides:
                        d.set_flag(expanded_varname, flag, overrides)
                        continue
                    for type in overrides:
                        for override_name in overrides[type]:
                            old_overrides[type][override_name] = \
                                overrides[type][override_name]
                    d.set_flag(expanded_varname, flag, old_overrides)
                    continue
                d.set_flag(expanded_varname, flag, flags[flag])
            del d[varname]

REBUILDALL_SKIP[nohash] = True
RELAXED[nohash] = True