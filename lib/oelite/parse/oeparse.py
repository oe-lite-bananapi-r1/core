import ply.yacc
import os
import string
import oelite.parse
import oelite.meta
import oelite.path
import oelite.util

class OEParser(object):

    def __init__(self, meta=None, parent=None, lexer=None):
        import oelite
        if lexer is None:
            import oelite.parse
            lexer = oelite.parse.oelexer
        self.lexer = lexer.clone()
        self.lexer.parser = self
        if type(lexer.lextokens) == set:
            # ply >= 3.6
            self.tokens = list(lexer.lextokens)
        else:
            # ply <= 3.4
            self.tokens = lexer.lextokens.keys()
        oelite.util.makedirs("tmp/ply")
        picklefile = "tmp/ply/" + self.__class__.__module__ + ".p"
        self.yacc = ply.yacc.yacc(module=self, debug=0, picklefile=picklefile)
        if meta is not None:
            self.meta = meta
        else:
            self.meta = oelite.meta.DictMeta()
        self.parent = parent
        return


    def reset_lexstate(self):
        while self.lexer.lexstate != "INITIAL":
            self.lexer.pop_state()
        # FIXME: or perhaps use self.lexer.begin("INITIAL")
        return


    def set_metadata(self, meta):
        self.meta = meta
        return


    def lextest(self, meta, debug=False):
        self.lexer.input(meta)
        tokens = []
        for tok in self.lexer:
            if debug:
                print tok.type, repr(tok.value), tok.lineno, tok.lexpos
            tokens.append((tok.type, tok.value))
        return tokens


    start = 'syntax'


    def p_syntax(self, p):
        '''syntax : statement
                  | statement syntax'''
        return

    def p_statement(self, p):
        '''statement : NEWLINE
                     | assignment NEWLINE
                     | export_variable NEWLINE
                     | include NEWLINE
                     | require NEWLINE
                     | inherit NEWLINE
                     | func NEWLINE
                     | fakeroot_func NEWLINE
                     | python_func NEWLINE
                     | def_func
                     | addtask NEWLINE
                     | addhook NEWLINE
                     | prefer NEWLINE
                     | COMMENT'''
        return

    def p_variable(self, p):
        '''variable : VARNAME
                    | export_variable'''
        try:
            # FIXME: come up with different syntax for
            # immediate-expansion variable names and delayed-expansion
            # variable names, fx. DEPENDS_$:{PN} and DEPENDS_${PN},
            # and implement immediate expansion here, and delayed
            # expansion in core_varname_expansion hook expansion.  It
            # would seem convenient to use the normal variable
            # expansion syntax for immediate expansion, as we could
            # just simply expand here, and then translate the delayed
            # expansion variable syntax in core_varname_expansion
            # before expanding it.
            #p[0] = self.meta.expand(p[1], oelite.meta.PARTIAL_EXPANSION)
            p[0] = p[1]
        except oelite.meta.ExpansionError, e:
            print "Metadata expansion failed:", e
            e.print_details()
            raise oelite.parse.ParseError(self, "Failed to expand variable name", p)
        return
    
    def p_export_variable(self, p):
        '''export_variable : EXPORT VARNAME'''
        p[0] = intern(self.meta.expand(p[2]))
        self.meta.set_flag(p[0], "export", "1")
        return

    def p_flag(self, p):
        '''varflag : VARNAME FLAG'''
        p[0] = (p[1], p[2])
        return
    
    def p_override(self, p):
        '''varoverride : VARNAME OVERRIDE'''
        try:
            p[0] = (self.meta.expand(p[1]), p[2])
        except oelite.meta.ExpansionError as e:
            raise oelite.parse.ParseError(self, str(e), p)
        return

    def p_string(self, p):
        '''string : empty_string
                  | quoted_string
                  | STRING'''
        p[0] = p[1]
        return

    def p_empty_string(self, p):
        '''empty_string : QUOTE QUOTE'''
        p[0] = ""
        return

    def p_quoted_string(self, p):
        '''quoted_string : QUOTE string_value QUOTE'''
        p[0] = p[2]
        return

    def p_string_value1(self, p):
        '''string_value : STRING'''
        p[0] = p[1]
        return

    def p_string_value2(self, p):
        '''string_value : STRING string_value'''
        p[0] = intern(p[1] + p[2])
        return

    def p_simple_var_assignment(self, p):
        '''assignment : variable ASSIGN string'''
        self.meta.set(p[1], p[3])
        return

    def p_simple_flag_assignment(self, p):
        '''assignment : varflag ASSIGN string'''
        self.meta.set_flag(p[1][0], p[1][1], p[3])
        return

    def p_simple_override_assignment(self, p):
        '''assignment : varoverride ASSIGN string'''
        self.meta.set_override(p[1][0], p[1][1], p[3])
        return

    def p_exp_var_assignment(self, p):
        '''assignment : variable EXPASSIGN string'''
        self.meta.set(p[1], self.meta.expand(p[3]))
        return

    def p_exp_flag_assignment(self, p):
        '''assignment : varflag EXPASSIGN string'''
        self.meta.set_flag(p[1][0], p[1][1], self.meta.expand(p[3]))
        return

    def p_exp_override_assignment(self, p):
        '''assignment : varoverride EXPASSIGN string'''
        self.meta.set_override(p[1][0], p[1][1], self.meta.expand(p[3]))
        return

    def p_defaultval_assignment(self, p):
        '''assignment : variable LAZYASSIGN string'''
        self.meta.set_flag(p[1], "defaultval", p[3])
        return

    def p_weak_var_assignment(self, p):
        '''assignment : variable WEAKASSIGN string'''
        if not p[1] in self.meta:
            self.meta.set(p[1], p[3])
        return

    def p_weak_flag_assignment(self, p):
        '''assignment : varflag WEAKASSIGN string'''
        if self.meta.get_flag(p[1][0], p[1][1]) == None:
            self.meta.set_flag(p[1][0], p[1][1], p[3])
        return

    def p_weak_override_assignment(self, p):
        '''assignment : varoverride WEAKASSIGN string'''
        if self.meta.get_override(p[1][0], p[1][1]) == None:
            self.meta.set_override(p[1][0], p[1][1], p[3])
        return

    def p_append_var_assignment(self, p):
        '''assignment : variable APPEND string'''
        self.meta.append(p[1], p[3], separator=" ")
        return

    def p_append_flag_assignment(self, p):
        '''assignment : varflag APPEND string'''
        self.meta.append_flag(p[1][0], p[1][1], p[3], separator=" ")
        return

    def p_append_override_assignment(self, p):
        '''assignment : varoverride APPEND string'''
        self.meta.append_override(p[1][0], p[1][1], p[3], separator=" ")
        return

    def p_prepend_var_assignment(self, p):
        '''assignment : variable PREPEND string'''
        self.meta.prepend(p[1], p[3], separator=" ")
        return

    def p_prepend_flag_assignment(self, p):
        '''assignment : varflag PREPEND string'''
        self.meta.prepend_flag(p[1][0], p[1][1], p[3], separator=" ")
        return

    def p_prepend_override_assignment(self, p):
        '''assignment : varoverride PREPEND string'''
        self.meta.prepend_override(p[1][0], p[1][1], p[3], separator=" ")
        return

    def p_predot_var_assignment(self, p):
        '''assignment : variable PREDOT string'''
        self.meta.append(p[1], p[3])
        return

    def p_predot_flag_assignment(self, p):
        '''assignment : varflag PREDOT string'''
        self.meta.append_flag(p[1][0], p[1][1], p[3])
        return

    def p_predot_override_assignment(self, p):
        '''assignment : varoverride PREDOT string'''
        self.meta.append_override(p[1][0], p[1][1], p[3])
        return

    def p_postdot_var_assignment(self, p):
        '''assignment : variable POSTDOT string'''
        self.meta.prepend(p[1], p[3])
        return

    def p_postdot_flag_assignment(self, p):
        '''assignment : varflag POSTDOT string'''
        self.meta.prepend_flag(p[1][0], p[1][1], p[3])
        return

    def p_postdot_override_assignment(self, p):
        '''assignment : varoverride POSTDOT string'''
        self.meta.prepend_override(p[1][0], p[1][1], p[3])
        return

    def p_include(self, p):
        '''include : INCLUDE INCLUDEFILE'''
        self.include(p[2], p)
        return

    def p_require(self, p):
        '''require : REQUIRE INCLUDEFILE'''
        try:
            self.include(p[2], p, require=True)
        except oelite.parse.FileNotFound, e:
            # ParseError-2
            raise oelite.parse.ParseError(
                self, "File not found: require %s"%(p[2]), p)
        return

    def p_inherit(self, p):
        '''inherit : INHERIT inherit_classes'''
        for inherit_classes in p[2]:
            try:
                inherit_classes = self.meta.expand(inherit_classes,
                                                   method=oelite.meta.FULL_EXPANSION)
            except oelite.meta.ExpansionError, e:
                # ParseError-3
                raise oelite.parse.ParseError(
                    self, str(e), p, more_details=e)

            for inherit_class in (inherit_classes or "").split():
                try:
                    self.inherit(inherit_class, p)
                except oelite.parse.FileNotFound, e:
                    # ParseError-4
                    raise oelite.parse.ParseError(
                        self, "Class not found: inherit %s"%(inherit_class), p)
        return

    def p_inherit_classes(self, p):
        '''inherit_classes : INHERITCLASS'''
        p[0] = [ p[1] ]
        return

    def p_inherit_classes2(self, p):
        '''inherit_classes : INHERITCLASS inherit_classes'''
        p[0] = [ p[1] ] + p[2]
        return

    def p_addtask(self, p):
        '''addtask : addtask_task'''
        self.meta.set_flag(p[1], "task", True)
        #print "addtask %s"%(p[1])
        return

    def p_addtask_w_dependencies(self, p):
        '''addtask : addtask_task addtask_dependencies'''
        #print "addtask %s after %s before %s"%(p[1], p[2][0], p[2][1])
        self.p_addtask(p)
        self.meta.append_flag(p[1], "deps", " ".join(p[2][0]), " ")
        for before_task in p[2][1]:
            self.meta.append_flag(before_task, "deps", p[1], " ")
        return

    def taskname(self, s):
        if not s.startswith("do_"):
            return "do_" + s
        return s

    def p_addtask_task(self, p):
        '''addtask_task : ADDTASK TASK'''
        p[0] = self.taskname(p[2])
        return

    def p_addtask_dependencies1(self, p):
        '''addtask_dependencies : addtask_dependency'''
        p[0] = p[1]
        return

    def p_addtask_dependencies2(self, p):
        '''addtask_dependencies : addtask_dependency addtask_dependencies'''
        p[0] = (set(p[1][0] + p[2][0]), set(p[1][1] + p[2][1]))
        return

    def p_addtask_dependency(self, p):
        '''addtask_dependency : addtask_after
                              | addtask_before'''
        p[0] = p[1]
        return

    def p_addtask_after(self, p):
        '''addtask_after : AFTER tasks'''
        p[0] = (p[2], [])
        return

    def p_addtask_before(self, p):
        '''addtask_before : BEFORE tasks'''
        p[0] = ([], p[2])
        return

    def p_tasks(self, p):
        '''tasks : TASK'''
        p[0] = [ self.taskname(p[1]) ]
        return

    def p_tasks2(self, p):
        '''tasks : TASK tasks'''
        p[0] = [ self.taskname(p[1]) ] + p[2]
        return


    def p_addhook1(self, p):
        '''addhook : ADDHOOK HOOK TO HOOKNAME'''
        self.meta.add_hook(p[4], p[2])
        return

    def p_addhook2(self, p):
        '''addhook : ADDHOOK HOOK TO HOOKNAME HOOKSEQUENCE'''
        self.meta.add_hook(p[4], p[2], p[5])
        return

    def p_addhook3(self, p):
        '''addhook : ADDHOOK HOOK TO HOOKNAME addhook_dependencies'''
        self.meta.add_hook(p[4], p[2], after=p[5][0], before=p[5][1])
        return

    def p_addhook4(self, p):
        '''addhook : ADDHOOK HOOK TO HOOKNAME HOOKSEQUENCE addhook_dependencies'''
        self.meta.add_hook(p[4], p[2], p[5], after=p[6][0], before=p[6][1])
        return

    def p_addhook_dependencies1(self, p):
        '''addhook_dependencies : addhook_dependency'''
        p[0] = p[1]
        return

    def p_addhook_dependencies2(self, p):
        '''addhook_dependencies : addhook_dependency addhook_dependencies'''
        p[0] = (set(p[1][0] + list(p[2][0])), set(p[1][1] + list(p[2][1])))
        return

    def p_addhook_dependency(self, p):
        '''addhook_dependency : addhook_after
                              | addhook_before'''
        p[0] = p[1]
        return

    def p_addhook_after(self, p):
        '''addhook_after : AFTER hooks'''
        p[0] = (p[2], [])
        return

    def p_addhook_before(self, p):
        '''addhook_before : BEFORE hooks'''
        p[0] = ([], p[2])
        return

    def p_hooks(self, p):
        '''hooks : HOOK'''
        p[0] = [ p[1] ]
        return

    def p_hooks2(self, p):
        '''hooks : HOOK hooks'''
        p[0] = [ p[1] ] + p[2]
        return


    def p_prefer_recipe(self, p):
        '''prefer : PREFER recipe maybe_layer maybe_version'''
        self.meta.set_preference(recipe=p[2], layer=p[3], version=p[4])
        return

    def p_prefer_package(self, p):
        '''prefer : PREFER packages maybe_recipe maybe_layer maybe_version'''
        self.meta.set_preference(packages=p[2], recipe=p[3], layer=p[4],
                                 version=p[5])
        return

    def p_recipe(self, p):
        '''recipe : RECIPE RECIPENAME'''
        p[0] = p[2]
        return

    def p_maybe_recipe1(self, p):
        '''maybe_recipe : '''
        p[0] = None
        return

    def p_maybe_recipe2(self, p):
        '''maybe_recipe : recipe'''
        p[0] = p[1]
        return

    def p_layer(self, p):
        '''layer : LAYER LAYERNAME'''
        p[0] = p[2]
        return

    def p_maybe_layer1(self, p):
        '''maybe_layer : '''
        p[0] = None
        return

    def p_maybe_layer2(self, p):
        '''maybe_layer : layer'''
        p[0] = p[1]
        return

    def p_version(self, p):
        '''version : VERSION VERSIONNAME'''
        p[0] = p[2]
        return

    def p_maybe_version1(self, p):
        '''maybe_version : '''
        p[0] = None
        return

    def p_maybe_version2(self, p):
        '''maybe_version : version'''
        p[0] = p[1]
        return

    def p_packages(self, p):
        '''packages : PACKAGE package'''
        p[0] = p[2]
        return

    def p_package1(self, p):
        '''package : PACKAGENAME'''
        p[0] = [ p[1] ]
        return

    def p_packages2(self, p):
        '''package : PACKAGENAME package'''
        p[0] = [ p[1] ] + p[2]
        return


    def p_func(self, p):
        '''func : VARNAME FUNCSTART func_body FUNCSTOP'''
        self.meta.set(p[1], p[3])
        self.meta.set_flag(p[1], "bash", True)
        p[0] = p[1]
        return

    def p_func_body(self, p):
        '''func_body : FUNCLINE'''
        p[0] = p[1]
        return

    def p_func_body2(self, p):
        '''func_body : FUNCLINE func_body'''
        p[0] = p[1] + p[2]
        return

    def p_fakeroot_func(self, p):
        '''fakeroot_func : FAKEROOT func'''
        self.meta.set_flag(p[2], "fakeroot", True)
        p[0] = p[2]
        return

    def p_python_func(self, p):
        '''python_func : python_func_start func_body FUNCSTOP'''
        self.meta.set(p[1][0], p[2])
        self.meta.set_flag(p[1][0], "python", True)
        self.meta.set_flag(p[1][0], "args", "d")
        self.meta.set_flag(p[1][0], "filename", p[1][1])
        self.meta.set_flag(p[1][0], "lineno", p[1][2])
        p[0] = p[1][0]
        return

    def p_python_func_start(self, p):
        '''python_func_start : PYTHON VARNAME FUNCSTART'''
        p[0] = (p[2], self.filename, p.lexer.lineno - 1)
        return

    #def p_python_anonfunc(self, p):
    #    '''python_func : PYTHON FUNCSTART func_body FUNCSTOP'''
    #    #funcname = "__anon_%s_%d"%(self.filename.translate(
    #    #        string.maketrans('/.+-', '____')), p.lexer.funcstart + 1)
    #    funcname = "__%s_%d__"%(
    #        self.filename.translate(string.maketrans('/+-.', '____')),
    #        p.lexer.funcstart + 1)
    #    #print "anonymous python %s"%(funcname)
    #    #self.meta.addAnonymousFunction(self.filename, p.lexer.funcstart + 1,
    #    #                               p[3])
    #    self.meta.set(funcname, p[3])
    #    self.meta.set_flag(funcname, 'python', True)
    #    self.meta.set_flag(funcname, 'args', "d")
    #    self.meta.add_hook("post_recipe_parse", funcname)
    #    return

    def p_def_func(self, p):
        '''def_func : DEF VARNAME def_funcargs NEWLINE func_body
                    | DEF VARNAME def_funcargs NEWLINE func_body FUNCSTOP'''
        self.meta.set(p[2], p[5])
        self.meta.set_flag(p[2], "python", True)
        if p[3][0]:
            self.meta.set_flag(p[2], "args", p[3][0])
        self.meta.set_flag(p[2], "filename", p[3][1])
        self.meta.set_flag(p[2], "lineno", p[3][2])
        return

    def p_def_args1(self, p):
        '''def_funcargs : ARGSTART STRING ARGSTOP'''
        p[0] = (p[2], self.filename, p.lexer.lineno)
        return

    def p_def_args2(self, p):
        '''def_funcargs : ARGSTART ARGSTOP'''
        p[0] = (None, self.filename, p.lexer.lineno)
        return

    def p_error(self, p):
        # ParseError-1
        raise oelite.parse.ParseError(self, "Syntax error", p)


    def inherit(self, filename, p):
        #print "inherit", filename
        if not filename:
            return
        if not os.path.isabs(filename) and not filename.endswith(".oeclass"):
            filename = os.path.join("classes", "%s.oeclass"%(filename))
        __inherits = self.meta.get("__inherits")
        if __inherits:
            if filename in __inherits:
                return
            __inherits.append(filename)
        else:
            self.meta["__inherits"] = [filename]
        self.include(filename, p, require=True)


    def include(self, filename, p, require=False):
        try:
            filename = self.meta.expand(filename)
        except oelite.meta.ExpansionError, e:
            #print "ignoring include of in-expandable filename:", filename
            return None
        #print "including", filename
        parser = self.__class__(self.meta, parent=self)
        return parser.parse(filename, require, parser, p)


    def parse(self, filename, require=True, parser=None, p=None, debug=False):
        #print "parsing %s"%(filename)
        searchfn = filename
        if not os.path.isabs(filename):
            oepath = self.meta.get("OEPATH")
            if self.parent:
                dirname = os.path.dirname(self.parent.filename)
                oepath = "%s:%s"%(dirname, oepath)
            filename = oelite.path.which(oepath, filename)
        else:
            if not os.path.exists(filename):
                print "file not found: %s"%(filename)
                return
            oepath = None

        if not os.path.exists(filename):
            if require:
                raise oelite.parse.FileNotFound(self, searchfn, p)
            else:
                self.meta.set_input_mtime(searchfn, oepath)
                return

        self.filename = os.path.realpath(filename)

        if self.parent:
            oldfile = os.path.realpath(self.filename[-1])
            if self.filename == oldfile:
                print "don't include yourself!"
                return

        if parser is None and not filename.endswith(".oeclass"):
            self.meta.set("FILE", filename)
            self.meta.set("FILE_DIRNAME", os.path.dirname(filename))
            if filename.endswith(".oe"):
                file_split = os.path.basename(filename[:-3]).split("_")
                if len(file_split) > 3:
                    raise Exception("Invalid recipe filename: %s"%(filename))
                self.meta.set("RECIPE_NAME", file_split[0])
                self.meta.set("PN", file_split[0])
                if len(file_split) > 1:
                    self.meta.set("RECIPE_VERSION", file_split[1])
                    self.meta.set("PV", file_split[1])
                else:
                    self.meta.set("RECIPE_VERSION", "0")
                    self.meta.set("PV", "0")

        # FIXME: write lock file to safeguard against race condition
        mtime = os.path.getmtime(self.filename)
        f = open(self.filename)
        self.text = f.read()
        f.close()
        self.meta.set_input_mtime(searchfn, oepath, mtime)

        if not parser:
            parser = self
        return parser._parse(self.text, debug=debug)


    def _parse(self, s, debug=False):
        self.lexer.lineno = 0
        # To be able to properly stop parsing of Python functions at end
        # of file, we need a non-empty line
        self.yacc.parse(s + '\n#EOF', lexer=self.lexer, debug=debug)
        return self.meta


    def yacctest(self, s):
        self.meta = oelite.meta.DictMeta()
        return self._parse(s)
