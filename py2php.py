#!/usr/bin/env python
from types import StringType

# Copyright 2006 James Tauber and contributors
#
# modified by Andreas Bunkahle in 2019
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Note:  AST types are documented at:
#  https://docs.python.org/2/library/compiler.html


import compiler
from compiler import ast
import os
import copy
import codecs
import locale

# this is the python function used to wrap native javascript
NATIVE_JS_FUNC_NAME = "PHP"

from pprint import pprint

def print_r(obj):
    pprint (vars(obj))

class Klass:

    klasses = {}

    def __init__(self, name):
        self.name = name
        self.klasses[name] = self
        self.functions = set()
        
    def set_base(self, base_name):
        self.base = self.klasses.get(base_name)
        
    def add_function(self, function_name):
        self.functions.add(function_name)


class TranslationError(Exception):
    def __init__(self, message, node):
        self.message = "line %s:\n%s\n%s" % (node.lineno, message, node)

    def __str__(self):
        return self.message

def strip_py(name):
    if name[2:10] == 'pyjamas.':
        return "__"+name[10:]
    if name[2:10] == 'pyjamas_':
        return "__"+name[10:]
    if name[:8] == 'pyjamas.':
        return name[8:]
    return name

class Translator:

    def __init__(self, module_name, mod, output):
        if module_name:
            self.module_prefix = ""
        else:
            self.module_prefix = ""
        self.imported_modules = set()
        self.imported_js = set()
        self.top_level_functions = set()
        self.top_level_classes = set()
        self.top_level_vars = set()
        self.imported_classes = {}
        self.method_imported_globals = set()
        self.method_self = None
        self.depth = 0
        self.eol = "\n"
        
        buf = u''
        if module_name != "eval":
            buf += "set_include_path(get_include_path() . PATH_SEPARATOR . dirname(__FILE__) . DIRECTORY_SEPARATOR . 'libpy2php');\n"
            buf += "require_once('libpy2php.php');" + self.eol
        for child in mod.node:
            if isinstance(child, ast.Function):
                self.top_level_functions.add(child.name)
            elif isinstance(child, ast.Class):
                self.top_level_classes.add(child.name)

        for child in mod.node:
            if isinstance(child, ast.Function):
                buf += self._function(child, False)
            elif isinstance(child, ast.Class):
                buf += self._class(child)
            elif isinstance(child, ast.Import):
                importName = child.names[0][0]
                if importName == '__pyjamas__': # special module to help make pyjamas modules loadable in the python interpreter
                    pass
                elif importName.endswith('.php'):
                   self.imported_js.add(importName)
                else:
                   self.imported_modules.add(strip_py(importName))
                buf += self._import(child)
            elif isinstance(child, ast.From):
                if child.modname == '__pyjamas__': # special module to help make pyjamas modules loadable in the python interpreter
                    pass
                else:
                    self.imported_modules.add(child.modname)
                    self._from(child)
            elif isinstance(child, ast.Discard):
                buf += self._discard(child, None)
            elif isinstance(child, ast.Assign):
                buf += self._assign(child, None, True)
            else:
                buf += self._stmt(child, None)
                # raise TranslationError("unsupported AST type " + child.__class__.__name__, child)
        
        print >>output, buf
        
        # Initialize all classes for this module
        #for className in self.top_level_classes:
        #    print >> self.output, "__"+strip_py(self.module_prefix)+className+"_initialize();"
    
    def _default_args_handler(self, node, current_klass):
        arg_list = []

        if len(node.defaults):
            default_pos = len(node.argnames) - len(node.defaults)
        else:
            default_pos = 99999999
        
        end = 0
        normal_args = node.argnames
        if node.varargs != None:
            end = node.varargs
            normal_args = node.argnames[:-end]

        cnt = 0
        for argname in normal_args:
            if( argname != 'self'):   # weed out those silly python 'self' args
                if type(argname) in [tuple, list]:
                    for n in argname:
                        arg_list.append( '$' + n )
                else:
                    argname = '$' + argname
                    if cnt >= default_pos:
                        default_node = node.defaults[cnt-default_pos]
                        
                        default_value = self.expr( default_node, current_klass )
                        
                        arg_list.append( argname + "=" + default_value )
                    else:
                        arg_list.append( argname  )
            cnt = cnt + 1
        
        if end > 0:
            varargs = node.argnames[-end:]
            args = []
            for arg in varargs:
                arg_list.append( "...$" + arg )

        return ",".join(arg_list)
    
    def ind(self):
        return "    " * self.depth
        
    
                
    def _kwargs_parser(self, node, function_name, arg_names, current_klass):
        buf = u''
        if len(node.defaults) or node.kwargs:
            default_pos = len(arg_names) - len(node.defaults)
            if arg_names and arg_names[0] == self.method_self:
                default_pos -= 1
            buf += self.ind() + "function " + function_name+'(', ", ".join(["__kwargs"]+arg_names), ") {" + self.eol
            self.depth += 1
            for default_node in node.defaults:
                default_value = self.expr(default_node, current_klass)
#                if isinstance(default_node, ast.Const):
#                    default_value = self._const(default_node)
#                elif isinstance(default_node, ast.Name):
#                    default_value = self._name(default_node)
#                elif isinstance(default_node, ast.UnarySub):
#                    default_value = self._unarysub(default_node, current_klass)
#                else:
#                    raise TranslationError("unsupported type (in _method)", default_node)
                
                default_name = arg_names[default_pos]
                buf += self.ind() + "if (typeof %s == 'undefined')"%(default_name) + self.eol
                self.depth += 1
                buf += self.ind() + "%s=__kwargs.%s;"% (default_name, default_name) + self.eol
                self.depth -= 1 
                default_pos += 1
            
            #self._default_args_handler(node, arg_names, current_klass)
            if node.kwargs: arg_names += ["pyjslib_Dict(__kwargs)"]
            buf += self.ind() + "var __r = "+"".join(["[", ", ".join(arg_names), "]"])+";" + self.eol
            buf += self.ind() + "return __r;" + self.eol
            self.depth -= 1
            buf += self.ind() + "};" + self.eol
        return buf
        
    def _function(self, node, local=False, static=False):
        function_name = ''
        buf = u''
        if local: function_name = node.name
        else: function_name = strip_py(self.module_prefix) + node.name
            
        argnames = []
        for argname in node.argnames:
            if( argname != 'self'):   # weed out those silly python 'self' args
                if type(argname) in [tuple, list]:
                    for n in argname:
                        argnames.append( "$" + n )
                else:
                    argnames.append( "$" + argname )
        
        arg_names = list(argnames)
        normal_arg_names = list(arg_names)
        if node.kwargs: kwargname = normal_arg_names.pop()
        if node.varargs: varargname = normal_arg_names.pop()        
        
        declared_arg_names = list(normal_arg_names)
        if node.kwargs: declared_arg_names.append(kwargname)

        buf += self._doc(node.doc)
        
        #function_args = "(" + ", ".join(declared_arg_names) + ")"
        ordered_args = self._default_args_handler(node, None)
        function_args = "(" + ordered_args + ")"
        static_buf = ""
        if static:
            static_buf = "static "
        buf += self.ind() + "%sfunction %s%s {" % (static_buf, function_name, function_args) + self.eol
            
        self.depth += 1
        
        for child in node.code:
            buf += self._stmt(child, None)

        self.depth -= 1
        buf += self.ind() + "}" + self.eol
        return buf
    
    
    def _doc(self, node):
        buf = u''
        if node != None and len(node):
            lines = node.strip().split("\n")
            buf += self.ind() + "/**" + self.eol
            for line in lines:
                line = line.lstrip()
                if( line.startswith( '* ' ) ):
                    line = line[2:]
                buf += self.ind() + " * " + line + self.eol
            buf += self.ind() + " */" + self.eol
        return buf
        
    
    def _return(self, node, current_klass):
        buf = u''
        expr = self.expr(node.value, current_klass)
        if expr != "null":
            buf += self.ind() + "return " + expr + ";" + self.eol
        else:
            buf += self.ind() + "return;" + self.eol
        return buf


    def _break(self, node, current_klass):
        return self.ind() + "break;" + self.eol


    def _continue(self, node, current_klass):
        return self.ind() + "continue;" + self.eol

    def _customcallargs(self, args, position_map, current_klass):
        
        cnt = 0
        newargs = []
        for a in args:
            if cnt < len(position_map):
                phptype = position_map[cnt]
                arg = self._arg_as_phptype(a, phptype)
            else:
                arg = self.expr(a, current_klass)
            if arg != None:
                newargs.append(arg)
            cnt = cnt + 1
        return newargs


    def _callfunc(self, v, current_klass):
        #print "_callfunc: " + str(v)
        is_append = False
        is_user_func = False
        is_constructor = False
        call_args = []
        omit_call_args = False
        omit_call_parens = False
        
        python_builtins = ['abs', 'divmod', 'input', 'open', 'staticmethod', 'all', 'enumerate', 'int', 'ord', 'str', 'any', 'eval', 'isinstance', 'pow', 'sum', 'basestring', 'execfile', 'issubclass', 'print', 'super', 'bin', 'file', 'iter', 'property', 'tuple', 'bool', 'filter', 'len', 'range', 'type', 'bytearray', 'float', 'list', 'raw_input', 'unichr', 'callable', 'format', 'locals', 'reduce', 'unicode', 'chr', 'frozenset', 'long', 'reload', 'vars', 'classmethod', 'getattr', 'map', 'repr', 'xrange', 'cmp', 'globals', 'max', 'reversed', 'zip', 'compile', 'hasattr', 'memoryview', 'round', '__import__', 'complex', 'hash', 'min', 'set', 'delattr', 'help', 'next', 'setattr', 'dict', 'hex', 'object', 'slice', 'dir', 'id', 'oct', 'sorted']
        # print_r(v)
        if isinstance(v.node, ast.Name):
            if v.node.name in self.top_level_functions:
                call_name = v.node.name
            elif v.node.name in self.top_level_classes:
                call_name = "new " + v.node.name
            elif self.imported_classes.has_key(v.node.name):
                # BUG: imported_classes may contain imported function names
                # also.  But python AST doesn't seem to provide any way to
                # distinguish between a class and a function when importing
                # or when calling.  :-(
                call_name = "new " + v.node.name
            elif v.node.name == "super":
                call_name = "parent"
                omit_call_args = True
                omit_call_parens = True
            elif v.node.name == "callable":
                call_name = "is_function"
            elif v.node.name == "dict":
                call_name = "pyjslib_dict"
            elif v.node.name == "map":
                call_name = "pyjslib_map"
                call_args = self._customcallargs(v.args, ['callable'], current_klass)
            elif v.node.name == "zip":
                call_name = "pyjslib_zip"
            elif v.node.name == "dir":
                call_name = "pyjslib_dir"
            elif v.node.name == "getattr":
                call_name = "pyjslib_getattr"
            elif v.node.name == "hasattr":
                call_name = "method_exists"
            elif v.node.name == "int":
                call_name = "pyjslib_int"
            elif v.node.name == "str":
                call_name = "pyjslib_str"
            elif v.node.name == "range":
                call_name = "pyjslib_range"
            elif v.node.name == "len":
                call_name = "count"
            elif v.node.name == "sum":
                call_name = "pyjslib_sum"
            elif v.node.name == "min":
                call_name = "pyjslib_min"
            elif v.node.name == "max":
                call_name = "pyjslib_max"
            elif v.node.name == "list":
                call_name = "pyjslib_list"
            elif v.node.name == "hash":
                call_name = "pyjslib_hash"
            elif v.node.name == "repr":
                call_name = "pyjslib_repr"
            elif v.node.name == "isinstance":
                call_name = "isinstance"
            elif v.node.name == "open":
                call_name = "pyjslib_open"
            elif v.node.name == "globals":
                call_name = "pyjslib_globals"
            elif v.node.name == "filter":
                call_args = self._customcallargs(v.args, ['callable'], current_klass)
                call_name = "pyjslib_filter"
            elif v.node.name in python_builtins:
                call_name = v.node.name
            else:
                # none of the above, so it must be a variable, right?
                call_name = "$" + v.node.name
            #print "call_name: " + call_name
            
        elif isinstance(v.node, ast.Getattr):
            attr_name = v.node.attrname
            if isinstance(v.node.expr, ast.Name):
                call_name = self._name2(v.node.expr, current_klass, attr_name, True)
                call_args = []
            elif isinstance(v.node.expr, ast.Getattr):
                call_name = self._getattr2(v.node.expr, current_klass, attr_name)
                call_args = []
            elif isinstance(v.node.expr, ast.CallFunc):
                method = v.node.attrname
                if method == "__init__":
                    method = "__construct"
                call_name = self._callfunc(v.node.expr, current_klass) + "->" + method
                call_args = []
            elif isinstance(v.node.expr, ast.Subscript):
                call_name = self._subscript(v.node.expr, current_klass) + "->" + v.node.attrname
                call_args = []
            elif isinstance(v.node.expr, ast.Const):
                call_name = self.expr(v.node.expr, current_klass) + "->" + v.node.attrname
                call_args = []
            else:
                call_name = self.expr(v.node.expr, current_klass) + "->" + v.node.attrname
                #raise TranslationError("unsupported type (in _callfunc)", v.node.expr)
            if call_name.endswith( "->append"):
                call_name = call_name.replace( "->append", "")
                is_append = True
            if call_name.endswith( "__construct"):
                is_constructor = True

        elif isinstance(v.node, ast.Subscript):
            call_name = self._subscript(v.node, current_klass)
            call_args = []

        elif isinstance(v.node, ast.CallFunc):
            call_name = self._callfunc(v.node, current_klass)
            call_args = []

        # apparently this will "compile" in python but generate runtime error
        # TypeError: 'tuple' object is not callable
        elif isinstance(v.node, ast.Tuple):
            return self._tuple( v.node, current_klass )

        elif isinstance(v.node, ast.Lambda):
            call_name = self._lambda(v.node, current_klass)
            call_args = []
            is_user_func = True

        else:
            # python allows some weird stuff as function calls.
            # examples I've seen in the wild:
            #     and/or,  multiplication, tuples, etc.
            call_name = "(" + self.expr(v.node, current_klass) + ")"

        # else:
        #    raise TranslationError("unsupported type (in _callfunc)", v.node)
         
        call_name = strip_py(call_name)

        kwargs = []
        
        if len(call_args) == 0 and omit_call_args == False:
            cnt = 0
            for ch4 in v.args:
                if isinstance(ch4, ast.Keyword):
                    kwarg = '"' + ch4.name + '"' + " => " + self.expr(ch4.expr, current_klass)
                    kwargs.append(kwarg)
                else:
                    arg = self.expr(ch4, current_klass)
                    if arg == "$this" and is_constructor and cnt == 0:
                        continue
                    #print "ARG: " + arg + ', ' + str(ch4)
                    #no_dollar = [ast.Class, ast.Const]
                    if isinstance(ch4, ast.Name):
                        arg = arg
                    if( arg != None):
                        call_args.append(arg)
                cnt = cnt + 1

        if v.star_args != None:
            arg = "..." + self.expr(v.star_args, current_klass)
            call_args.append( arg )
            
        if v.dstar_args != None:
            dstar_arg = self.expr(v.dstar_args, current_klass)
            if v.star_args:
                cargs = self.expr(v.star_args, current_klass)
            else:
                cargs = "[" + ",".join( call_args ) + "]"
            try: call_this, method_name = call_name.rsplit("->", 1)
            except ValueError:
                # Must be a function call ...
                return ("py2php_kwargs_function_call('"+call_name+"', "
                                  + cargs + ", " + dstar_arg
                                  + ")" )
            else:
                if call_this == 'parent':
                    return ("py2php_kwargs_method_call($this, 'parent', '"+method_name+"', "
                                      + cargs + ", " + dstar_arg
                                      + ")")
                    
                if not call_this[0] == '$':
                    call_this = "'" + call_this + "'"
                return ("py2php_kwargs_method_call("+call_this+", null, '"+method_name+"', "
                                  + cargs + ", " + dstar_arg
                                  + ")")
            

        if is_user_func:
            return "call_user_func(" + call_name + ", " + ", ".join(call_args) + ")"
            
        elif kwargs:
            cargs = "[" + ",".join( call_args ) + "]"
            kargs = "[" + ",".join( kwargs ) + "]"
            try: call_this, method_name = call_name.rsplit("->", 1)
            except ValueError:
                # Must be a function call ...
                return ("py2php_kwargs_function_call('"+call_name+"', "
                                  + cargs + ", " + kargs + ")" )
            else:
                if not call_this[0] == '$':
                    call_this = "'" + call_this + "'"
                return ("py2php_kwargs_method_call("+call_this+", null, '"+method_name+"', "
                                  + cargs + ", " + kargs + ")" )
        else:
            if is_append:
                return call_name + "[] = " + ", ".join(call_args)
            elif not omit_call_parens:
                return call_name + "(" + ", ".join(call_args) + ")"
            else:
                return call_name
    
    def _print(self, node, current_klass, nl = False):
        buf = u''
        call_args = []
        for ch4 in node.nodes:
            arg = self.expr(ch4, current_klass)
            call_args.append(arg)
            
        func = "pyjslib_print"
        if nl:
            func = "pyjslib_printnl"
        
        if len(call_args) == 1:
            buf += self.ind() + func + "(" + ''.join(call_args) + ");" + self.eol
        else:
            buf += self.ind() + func + "([" + ', '.join(call_args) + "], true);" + self.eol
        return buf
        

    def _getattr(self, v, as_callable=False):
        attr_name = v.attrname
        if isinstance(v.expr, ast.Name):
            obj = self._name(v.expr, return_none_for_module=True)
            if obj == None and v.expr.name in self.imported_modules:
                if as_callable:
                    return "['" + v.expr.name + "', '" + attr_name + "']"
                else:
                    return v.expr.name+'::'+ attr_name
            scope = "->"
            if v.expr.name in self.top_level_classes or v.expr.name in self.imported_classes:
                scope = "::"
                attr_name = "$" + attr_name
            if as_callable:
                if obj[0] != '$':
                    obj = "'" + obj + "'"
                return "[" + obj + ", '" + v.attrname + "']"
            else:
                return obj + scope + attr_name
        elif isinstance(v.expr, ast.Getattr):
            return self._getattr(v.expr) + "->" + attr_name
        elif isinstance(v.expr, ast.Subscript):
            return self._subscript(v.expr, attr_name ) + "->" + attr_name
        elif isinstance(v.expr, ast.CallFunc):
            return self._callfunc(v.expr, attr_name )
        else:
            return self.expr(v.expr, None) + "::" + attr_name
            # raise TranslationError("unsupported type (in _getattr)", v.expr)
    
    def _arg_as_phptype(self, node, phptype):
        if phptype == "string":
            return "'" + node.name + "'"
        elif phptype == "callable":
            if isinstance( node, ast.Name):
                return "'" + node.name + "'"
            elif isinstance( node, ast.Getattr):
                return self._getattr( node, True )
            elif isinstance( node, ast.Lambda):
                return self._lambda( node, None )
        elif phptype == "variable":
            return "$" + node.name
        elif phptype == "literal":
            return node.name
        else:
            raise TranslationError("unsupported phptype (in _name_as_phptype)", node)
    
    
    def _name(self, v, return_none_for_module=False):
        if v.name == "True":
            return "true"
        elif v.name == "False":
            return "false"
        elif v.name == "None":
            return "null"
        elif v.name == self.method_self:
            return "$this"
        elif v.name in self.method_imported_globals:
            return "$" + self._self(v.name)
        elif self.imported_classes.has_key(v.name):
            return self._self(v.name)
        elif v.name in self.top_level_classes:
            return self._self(v.name)
        elif v.name in self.imported_modules and return_none_for_module:
            return None
        else:
            return "$" + self._self(v.name)


    def _name2(self, v, current_klass, attr_name, is_call=False):
        obj = v.name
        
        dollar = "$"
        if is_call:
            dollar = ""
        
        if attr_name == "__init__":
            attr_name = "__construct"

        if obj in self.method_imported_globals:
            call_name = self._name(v) + "->" + attr_name
        elif self.imported_classes.has_key(obj):
            #attr_str = ""
            #if attr_name != "__init__":
            call_name = obj + "::" + dollar + attr_name
        elif obj in self.imported_modules:
            # PHP has no concept of modules.
            # This could be using PHP namespaces, in PHP6.
            # For now we just pretend the module is a class.  Often it should be anyway.
            call_name = obj + "::" + dollar + attr_name
        elif obj[0] == obj[0].upper():
            call_name = obj + "::" + dollar + attr_name
        else:
            call_name = self._name(v) + "->" + attr_name

        return call_name


    def _getattr2(self, v, current_klass, attr_name):
        if isinstance(v.expr, ast.Getattr):
            call_name = self._getattr2(v.expr, current_klass, v.attrname + "->" + attr_name)
        elif isinstance(v.expr, ast.Name) and v.expr.name in self.imported_modules:
            call_name = v.expr.name + "::" + v.attrname + "::" + attr_name
        elif isinstance(v.expr, ast.Name) and v.expr.name + "." + v.attrname in self.imported_modules:
            call_name = self._import_name(v.expr.name + "." + v.attrname) + "::" + attr_name
        else:
            obj = self.expr(v.expr, current_klass)
            call_name = obj + "->" + v.attrname + "->" + attr_name
            
        return call_name
    
    
    def _class(self, node):
        """
        Handle a class definition.
        
        In order to translate python semantics reasonably well, the following
        structure is used:
        
        A special object is created for the class, which inherits attributes
        from the superclass, or Object if there's no superclass.  This is the
        class object; the object which you refer to when specifying the
        class by name.  Static, class, and unbound methods are copied
        from the superclass object.
        
        A special constructor function is created with the same name as the
        class, which is used to create instances of that class.
        
        A javascript class (e.g. a function with a prototype attribute) is
        created which is the javascript class of created instances, and
        which inherits attributes from the class object. Bound methods are 
        copied from the superclass into this class rather than inherited,
        because the class object contains unbound, class, and static methods
        that we don't necessarily want to inherit.
        
        The type of a method can now be determined by inspecting its
        static_method, unbound_method, class_method, or instance_method
        attribute; only one of these should be true.
        
        Much of this work is done in pyjs_extend, is pyjslib.py
        """
        buf = u''
        class_name = strip_py(self.module_prefix) + node.name
        current_klass = Klass(class_name)
        
        init_method = None
        for child in node.code:
            if isinstance(child, ast.Function):
                current_klass.add_function(child.name)
                if child.name == "__init__":
                    child.name = "__construct"
                    init_method = child

        bases = []
        base_class = None
        
        for base in node.bases:
            if isinstance(base, ast.Name):
                basename = base.name
                if basename == 'object':
                    basename = 'stdClass'
                bases.append(basename)
            elif isinstance(base, ast.Getattr):
                bases.append( base.attrname )
            elif isinstance(base, ast.CallFunc):
                buf += self.ind() + self.eol
                buf += self.ind() + "/* py2php : Monkey Patching is not supported in PHP" + self.eol
                buf += self.ind() + " * " + self.eol
                buf += self.ind() + self._callfunc(base, None) + self.eol
                buf += self.ind() + " */" + self.eol + self.eol
            else:
                raise TranslationError("unsupported type (in _class)", base)

        if len(bases) == 1:
            base_class = bases[0]
            current_klass.set_base(base_class)
        
        buf += self._doc( node.doc )
        
        line = self.ind() + "class " + class_name
        if base_class != None:
            line += " extends " + base_class
        line += " {" + self.eol

        buf += line
        self.depth += 1
        
        if len(bases) > 1:
            buf += self.ind() + "/* py2php : PHP does not support multiple inheritance." + self.eol
            buf += self.ind() + " * Consider defining the referenced classes as traits instead." + self.eol
            buf += self.ind() + " * See: http://php.net/manual/en/language.oop5.traits.php" + self.eol
            buf += self.ind() + " */" + self.eol
            buf += self.ind() + "use " + ", ".join(bases) + " {" + self.eol
            buf += self.ind() + "}" + self.eol
        

        for child in node.code:
            if isinstance(child, ast.Pass):
                pass
            elif isinstance(child, ast.Function):
                buf += self._method(child, current_klass, class_name)
            elif isinstance(child, ast.Assign):
                buf += self.classattr(child, current_klass)
            elif isinstance(child, ast.Discard) and isinstance(child.expr, ast.Const):
                # Probably a docstring, turf it
                lines = str(child.expr.value).strip().split("\n")
                for line in lines:
                    buf += self.ind() + "// " + line.lstrip() + self.eol
            elif isinstance(child, ast.Discard):
                buf += self.ind() + self.expr( child.expr, current_klass ) + self.eol;
            elif isinstance(child, ast.Class):
                buf += self._class(child)
            else:
                # python allows arbitrary statements inside class.  weird!
                buf += self.eol
                buf += "/* py2php : python allows arbitrary statements inside class" + self.eol
                buf += " *          but PHP (sensibly) does not." + self.eol
                buf += " *          commenting out this code block." + self.eol
                buf += self._stmt(child, current_klass)
                buf += " */" + self.eol + self.eol
                # raise TranslationError("unsupported type (in _class)", child)
        self.depth -= 1
        buf += self.ind() + "}" + self.eol
        return buf
        

    def _assert(self, node, current_klass):
        buf = self.ind() + 'assert('
        buf += self.expr( node.test, current_klass )
        if node.fail:
            buf += ", " + self.expr( node.fail, current_klass )
        buf += ");" + self.eol
        
        return buf

    def _exec(self, node, current_klass):
        output = StringIO.StringIO()

        if isinstance(node.expr, ast.Name):
            buf = self.ind() + "eval(" + self.expr(node.expr, current_klass) + ");" + self.eol
        elif isinstance(node.expr, ast.Const):
            try:
                code_in = node.expr.value
                mod = compiler.parse(code_in)
                t = Translator("eval", mod, output)
                code_out = output.getvalue()
                buf = self.ind() + "eval("
                if code_out.find("'") == -1:
                    buf += "'" + code_out.strip() + "'"
                else:
                    buf += " <<< 'PY2PHP_EVAL_END'\n" + code_out.strip() + "\nPY2PHP_EVAL_END\n"
                buf += ");" + self.eol
            except:
                buf = self.ind() + "/* py2php : got exception when trying to translate this code" + self.eol
                buf = self.ind() + " *          using original input string" + self.eol
                buf = self.ind() + " */" + self.eol
                if code_in.find("'") == -1:
                    buf += "'" + code_in.strip() + "'"
                else:
                    buf += " <<< 'PY2PHP_EVAL_END'\n" + code_in.strip() + "\nPY2PHP_EVAL_END\n"
                buf += ");" + self.eol
        else:
            buf = self.ind() + "eval(" + self.expr( node.expr, current_klass ) + ");" + self.eol
            
        return buf
    
    def classattr(self, node, current_klass):
        return self._assign(node, current_klass, True)
    
        
    def _method(self, node, current_klass, class_name):
        # reset global var scope
        self.method_imported_globals = set()
        buf = u''
        
        arg_names = list(node.argnames)
        
        classmethod = False
        staticmethod = False
        if node.decorators:
            for d in node.decorators:
                if hasattr( d, 'name'):
                    if d.name == "classmethod":
                        classmethod = True
                    elif d.name == "staticmethod":
                        staticmethod = True

        buf += self._function(node, True, staticmethod)
        return buf
       
        if staticmethod:
            staticfunc = ast.Function([], class_name+"_"+node.name, node.argnames, node.defaults, node.flags, node.doc, node.code, node.lineno)
            self._function(staticfunc, True)
            return
        else: 
            if len(arg_names) == 0:
                raise TranslationError("methods must take an argument 'self' (in _method)", node)
            self.method_self = arg_names[0]
            
            #if not classmethod and arg_names[0] != "self":
            #    raise TranslationError("first arg not 'self' (in _method)", node)

        normal_arg_names = arg_names[1:]
        for arg in normal_arg_names:
            arg = "$" + arg
            
        if node.kwargs: kwargname = normal_arg_names.pop()
        if node.varargs: varargname = normal_arg_names.pop()        
        declared_arg_names = list(normal_arg_names)
        if node.kwargs: declared_arg_names.append(kwargname)
        
        function_args = "(" + ", ".join(declared_arg_names) + ")"
    
        if classmethod:
            fexpr = "__" + class_name + ".prototype.__class__." + node.name
        else:
            fexpr = "__" + class_name + ".prototype." + node.name
        buf += self.ind() + "function "+ node.name +  function_args + "{" + self.eol
        self.depth += 1

        # default arguments
        self._default_args_handler(node, normal_arg_names, current_klass)
        
        for child in node.code:
            self._stmt(child, current_klass)

        self.depth -= 1
        buf += self.ind() + "};" + self.eol
            
        self._kwargs_parser(node, fexpr, normal_arg_names, current_klass)
        
        if classmethod:
            # Have to create a version on the instances which automatically passes the
            # class as "self"
            altexpr = "__" + class_name + ".prototype." + node.name
            buf += self.ind() + "function "+node.name + "() {" + self.eol
            self.depth += 1
            buf += self.ind() + "return " + fexpr + ".apply(this.__class__, arguments);" + self.eol
            self.depth -= 1
            buf += self.ind() + "};" + self.eol
            buf += self.ind() + fexpr+".class_method = true;" + self.eol
            buf += self.ind() + altexpr+".instance_method = true;" + self.eol
        else:
            # For instance methods, we need an unbound version in the class object
            altexpr = "__" + class_name + ".prototype.__class__." + node.name
            buf += self.ind() + altexpr + " = function() {" + self.eol
            self.depth += 1
            buf += self.ind() + "return " + fexpr + ".call.apply("+fexpr+", arguments);" + self.eol
            self.depth -= 1
            buf += self.ind() + "};" + self.eol
            buf += self.ind() + altexpr+".unbound_method = true;" + self.eol
            buf += self.ind() + fexpr+".instance_method = true;" + self.eol
            
        if node.kwargs or len(node.defaults):
            buf += self.ind() + altexpr + ".parse_kwargs = " + fexpr + ".parse_kwargs;" + self.eol
        
        self.method_self = None
        self.method_imported_globals = set()
        return buf

    def _stmt(self, node, current_klass):
        buf = u''
        if isinstance(node, ast.Stmt):
            for n in node.nodes:
                buf += self._stmt(n, current_klass)
        elif isinstance(node, ast.Assert):
            buf += self._assert(node, current_klass)
        elif isinstance(node, ast.Return):
            buf += self._return(node, current_klass)
        elif isinstance(node, ast.Break):
            buf += self._break(node, current_klass)
        elif isinstance(node, ast.Continue):
            buf += self._continue(node, current_klass)
        elif isinstance(node, ast.Assign):
            buf += self._assign(node, current_klass)
        elif isinstance(node, ast.AugAssign):
            buf += self._augassign(node, current_klass)
        elif isinstance(node, ast.Discard):
            buf += self._discard(node, current_klass)
        elif isinstance(node, ast.If):
            buf += self._if(node, current_klass)
        elif isinstance(node, ast.For):
            buf += self._for(node, current_klass)
        elif isinstance(node, ast.While):
            buf += self._while(node, current_klass)
        elif isinstance(node, ast.Subscript):
            buf += self._subscript_stmt(node, current_klass)
        elif isinstance(node, ast.Global):
            buf += self._global(node, current_klass)
        elif isinstance(node, ast.Pass):
            buf += ''
        elif isinstance(node, ast.Function):
            buf += self._function(node, True)
        elif isinstance(node, ast.Exec):
            buf += self._exec(node, True)
        elif isinstance(node, ast.Printnl):
            buf += self._print(node, current_klass, nl=True)
        elif isinstance(node, ast.Print):
            buf += self._print(node, current_klass, nl=False)
        elif isinstance(node, ast.TryFinally):
            buf += self._tryfinally(node, current_klass)
        elif isinstance(node, ast.TryExcept):
            buf += self._tryexcept(node, current_klass)            
        elif isinstance(node, ast.Raise):
            buf += self._raise(node, current_klass)
        elif isinstance(node, ast.Getattr):
            buf += self._getattr(node)
        elif isinstance(node, ast.Import):
            buf += self._import(node)
        elif isinstance(node, ast.With):
            buf += self._with(node, current_klass)
        elif isinstance(node, ast.From):
            buf += self._from(node)
            
        else:
            buf += self.ind() + self.expr( node, current_klass) + ";" + self.eol
        return buf
        
    
    def _raise(self, node, current_klass):
        name = ''
        if isinstance(node.expr1, ast.Name):
            name = node.expr1.name
        elif node.expr1 == None:
            name = "Exception('py2php: python code would raise pre-existing exception here.')"
        else:
            name = self.expr( node.expr1, current_klass )
        return self.ind() + "throw new " + name + ";" + self.eol

    def _tryexcept(self, node, current_klass):
        buf = self.ind() + 'try {' + self.eol
        self.depth += 1
        buf += self._stmt( node.body, current_klass )
        self.depth -= 1
        buf += self.ind() + "}" + self.eol
        
        for e in node.handlers:
            buf += self.ind() + "catch("
            if hasattr(e[0], 'name') and e[0].name:
                buf += e[0].name
            else:
                buf += 'Exception'
            buf += " $e) {" + self.eol
            self.depth += 1
            buf += self.ind() + self._stmt(e[2], current_klass)
            self.depth -= 1
            buf += self.ind() + "}" + self.eol
            
        if node.else_:
            buf += "//" + self.ind() + "py2php: else block not supported in PHP." + self.eol
            buf += "//" + self.ind() + "else {" + self.eol
            self.depth += 1
            buf += "//" + self._stmt( node.else_, current_klass )
            self.depth -= 1
            buf += "//" + self.ind() + "}" + self.eol
            
        return buf
        

    def _tryfinally(self, node, current_klass):
        
        buf = u''
        if( isinstance( node.body, ast.TryExcept ) ):
            buf += self._tryexcept( node.body, current_klass )
        elif( isinstance( node.body, ast.Stmt ) ):
            buf += self.ind() + "try {" + self.eol
            self.depth += 1
            buf += self._stmt( node.body, current_klass )
            self.depth -= 1
            buf += self.ind() + "}" + self.eol
        else:
            raise TranslationError("unexpected type (in _tryfinally)", node.body)
        
        buf += self.ind() + "finally {" + self.eol
        self.depth += 1
        buf += self._stmt( node.final, current_klass )
        self.depth -= 1
        buf += self.ind() + "}" + self.eol
        return buf
    
    def _augassign(self, node, current_klass):
        v = node.node
        if isinstance(v, ast.Getattr):
            lhs = self._getattr(v)
        else:
            lhs = self.expr(node.node, current_klass)
        #op = '.='
        #if isinstance(node.expr, ast.Name):
        #    op = node.op
        op = node.op
        if self.use_dot( node.expr ):
            op = ".="
        rhs = self.expr(node.expr, current_klass)
        return self.ind() + lhs + " " + op + " " + rhs + ";" + self.eol

    
    def _assign(self, node, current_klass, top_level = False):
        buf = u''
        if len(node.nodes) != 1:
            tempvar = '__temp'+str(node.lineno)
            tnode = ast.Assign([ast.AssName(tempvar, "OP_ASSIGN", node.lineno)], node.expr, node.lineno)
            buf += self._assign(tnode, current_klass, top_level)
            for v in node.nodes:
               tnode2 = ast.Assign([v], ast.Name(tempvar, node.lineno), node.lineno)
               buf += self._assign(tnode2, current_klass, top_level)
            return buf

        v = node.nodes[0]
        if isinstance(v, ast.AssAttr):
            attr_name = v.attrname
            if isinstance(v.expr, ast.Name):
                obj = v.expr.name
                lhs = self.ind() + self._name(v.expr) + "->" + attr_name
                #print "LHS: " + lhs

            elif isinstance(v.expr, ast.Getattr):
                lhs = self.ind() + self._getattr(v)
            elif isinstance(v.expr, ast.Subscript):
                lhs = self.ind() + self._subscript(v.expr, current_klass) + "->" + attr_name
            elif isinstance(v.expr, ast.CallFunc):
                lhs = self.ind() + self._callfunc(v.expr, current_klass)
            else:
                raise TranslationError("unsupported type (in _assign)", v.expr)
            if v.flags == "OP_ASSIGN":
                op = "="
            else:
                raise TranslationError("unsupported flag (in _assign)", v)

        elif isinstance(v, ast.AssTuple):
            lhs = self.ind() + self._asstuple(v, current_klass)
            op = "="

        elif isinstance(v, ast.AssList):
            lhs = self.ind() + self._asslist(v, current_klass)
            op = "="
    
        elif isinstance(v, ast.AssName):
            if top_level:
                if current_klass:
                    lhs = self.ind() + "public $" + v.name
                else:
                    self.top_level_vars.add(v.name)
                    lhs = self.ind() + self._name(v)
            else:
                if v.name in self.method_imported_globals:
                    lhs = self.ind() + self._name(v)
                else:
                    lhs = self.ind() + self._name(v)
            if v.flags == "OP_ASSIGN":
                op = "="
            else:
                raise TranslationError("unsupported flag (in _assign)", v)
        elif isinstance(v, ast.Subscript):
            if v.flags == "OP_ASSIGN":
                obj = self.expr(v.expr, current_klass)
                idx = self.expr(v.subs[0], current_klass)
                value = self.expr(node.expr, current_klass)
                if len(v.subs) == 1:
                    buf += self.ind() +  obj + "[" + idx + "] = " + value + ";" + self.eol
                else:
                    buf += self.ind() +  obj + "[/* py2php : PHP does not support non-scalar array keys */] = " + value + ";" + self.eol
                return buf
            else:
                raise TranslationError("unsupported flag (in _assign)", v)
        elif isinstance(v, ast.Slice):
            expr = self.expr(v.expr, current_klass)
            lower = "0" if v.lower == None else self.expr(v.lower, current_klass)
            upper = "count(" + expr + ")" if v.upper == None else self.expr(v.upper, current_klass)
            upper = upper if lower == "0" else upper + "-" + lower
            rhs = self.expr(node.expr, current_klass)
            buf = self.ind() + "array_splice(" + expr + ", " + lower + ", " + upper + ", " + rhs + ");" + self.eol
            return buf
        else:
            raise TranslationError("unsupported type (in _assign)", v)
    

        rhs = self.expr(node.expr, current_klass)
        buf += lhs + " " + op + " " + rhs + ";" + self.eol
        return buf
    
    def _self(self, str):
        if str == 'self':
            return 'this'
        return str
    
    def _discard(self, node, current_klass):
        buf = u''
        if isinstance(node.expr, ast.CallFunc):
            if isinstance(node.expr.node, ast.Name) and node.expr.node.name == NATIVE_JS_FUNC_NAME:
                if len(node.expr.args) != 1:
                    raise TranslationError("native php function %s must have one arg" % NATIVE_JS_FUNC_NAME, node.expr)
                if not isinstance(node.expr.args[0], ast.Const):
                    raise TranslationError("native php function %s must have constant arg" % NATIVE_JS_FUNC_NAME, node.expr)
                buf += self.ind() + node.expr.args[0].value + self.eol
            else:
                expr = self._callfunc(node.expr, current_klass)
                buf += self.ind() + expr + ";" + self.eol
        elif isinstance(node.expr, ast.Const):
            if node.expr.value is not None: # Empty statements generate ignore None
                buf += self.ind() + self._const(node.expr, discard=True) + self.eol
        elif isinstance(node.expr, ast.Yield):
            buf += self._yield( node.expr, current_klass )
        elif isinstance(node.expr, ast.Name) and node.expr.name == 'XXX':
            buf += self.ind() + "// XXX" + self.eol
        else:
            buf += self.ind() + self.expr(node.expr, current_klass) + ";" + self.eol
            # raise TranslationError("unsupported type (in _discard)", node.expr)
        return buf
    
    def _if(self, node, current_klass):
        buf = u''
        for i in range(len(node.tests)):
            test, consequence = node.tests[i]
            if i == 0:
                keyword = "if"
            else:
                keyword = "else if"

            buf += self._if_test(keyword, test, consequence, current_klass)
            
        if node.else_:
            keyword = "else"
            test = None
            consequence = node.else_

            buf += self._if_test(keyword, test, consequence, current_klass)
        return buf            
        
    def _if_test(self, keyword, test, consequence, current_klass):
        buf = u''
    
        if test:
            expr = self.expr(test, current_klass)
    
            buf += self.ind() + keyword + " (" + expr + ") {" + self.eol
        else:
            buf += self.ind() + keyword + " {" + self.eol
        self.depth += 1

        if isinstance(consequence, ast.Stmt):
            for child in consequence.nodes:
                buf += self._stmt(child, current_klass)
        else:
            raise TranslationError("unsupported type (in _if_test)", consequence)

        self.depth -= 1
        buf += self.ind() + "}" + self.eol
        return buf

    def _ifexp(self, node, current_klass):
        buf = self.expr( node.test, current_klass ) + " ? "
        buf += self.expr( node.then, current_klass ) + " : "
        buf += self.expr( node.else_, current_klass )
        return buf

    def _yield( self, node, current_klass):
        buf = self.ind() + "yield(" + self.expr(node.value, current_klass) + ");" + self.eol
        return buf
    
    def _import_name(self, python_name):
        return python_name.replace('.', '_')

    def _import( self, node):
        importName = self._import_name(node.names[0][0])
        return self.ind() + "require_once( '" + importName + ".php');" + self.eol

    def _from(self, node):
        buf = u''
        for name in node.names:
            if node.modname == 'pyjamas':
                self.imported_modules.add(name[0])
            elif node.modname[:8] == 'pyjamas.':
                buf += "require_once( '" + node.modname[8:] + ".php');" 
                self.imported_classes[name[0]] = node.modname[8:]
            else:
                buf += "require_once( '" + node.modname + ".php');" 
                self.imported_classes[name[0]] = node.modname
        return buf


    def _compare(self, node, current_klass):
        lhs = self.expr(node.expr, current_klass)
        buf = "(" + lhs
        
        rhs_last = None
        
        for nodeop in node.ops:
            op = nodeop[0]
            rhs_node = nodeop[1]
            rhs = self.expr(rhs_node, current_klass)

            if op == "in":
                return "in_array(" + lhs + ", " + rhs + ")"
            elif op == "not in":
                return "!in_array(" + lhs + ", " + rhs + ")"
            elif op == "is":
                op = "=="
            elif op == "is not":
                op = "!="
                
            if rhs_last != None:
                buf += " && (" + rhs_last
            buf += " " + op + " " + rhs + ")"
            rhs_last = rhs

        return buf


    def _not(self, node, current_klass):
        expr = self.expr(node.expr, current_klass)

        return "!(" + expr + ")"

    def _or(self, node, current_klass):
        expr = " || ".join([self.expr(child, current_klass) for child in node.nodes])
        return expr

    def _and(self, node, current_klass):
        expr = " && ".join([self.expr(child, current_klass) for child in node.nodes])
        return expr

    def _for(self, node, current_klass):
        assign_name = ""
        assign_tuple = ""
        buf = u''
        dollar = "$"

        list_expr = self.expr(node.list, current_klass)

        # python calls iteritems() (2.x) or iter() (3.x)
        # for iteration over dictionaries, but php doesn't need that.
        is_dict = False
        bogus = ['->iteritems()', '->iter()', '->items()']
        for needle in bogus:
            if list_expr.endswith(needle):
                is_dict = True
                list_expr = list_expr.replace(needle, "")

        # based on Bob Ippolito's Iteration in Javascript code
        if isinstance(node.assign, ast.AssName):
            assign_name = node.assign.name
        elif isinstance(node.assign, ast.AssTuple):
            if is_dict:
                assign_name = self._asstuple_foreachdict(node.assign, current_klass)
            else:
                assign_name = self._asstuple(node.assign, current_klass)
            dollar = ''
        else:
            raise TranslationError("unsupported type (in _for)", node.assign)
        
        lhs = "var " + assign_name
        iterator_name = "__" + assign_name
        
        buf += self.ind() + "foreach( pyjslib_list(%(list_expr)s) as %(dollar)s%(assign_name)s ) {\n" % locals()
        self.depth += 1
        for node in node.body.nodes:
            buf += self._stmt(node, current_klass)
        self.depth -= 1
        buf += self.ind() + "}" + self.eol
        return buf


    def _while(self, node, current_klass):
        buf = u''
        test = self.expr(node.test, current_klass)
        buf += self.ind() + "while (" + test + ") {" + self.eol
        self.depth += 1
        if isinstance(node.body, ast.Stmt):
            for child in node.body.nodes:
                buf += self._stmt(child, current_klass)
        else:
            raise TranslationError("unsupported type (in _while)", node.body)
        self.depth -= 1
        buf += self.ind() + "}" + self.eol
        return buf


    def _const(self, node, discard=False):
        if isinstance(node.value, int):
            return unicode(node.value)
        elif isinstance(node.value, float):
            return unicode(node.value)
        elif isinstance(node.value, str):
#            return "\"" + node.value.encode('string_escape') + "\""
            try:
                val = node.value.decode("unicode-escape", 'backslashreplace')
            except:
                val = '?'
            
            buf = val.replace( "'", "\\'" )
            buf = buf.replace( "\r", "\\r" )
            if discard:
                return "/*" + buf + "*/"
            else:
                return "'" + buf + "'"
        elif node.value is None:
            return "null"
        else:
            return unicode(node.value)
            raise TranslationError("unsupported type (in _const)", node)

    def _unarysub(self, node, current_klass):
        return "-" + self.expr(node.expr, current_klass)

    def _unaryadd(self, node, current_klass):
        return "+" + self.expr(node.expr, current_klass)

    def _add(self, node, current_klass):
        op = " + "
        paren_left = "("
        paren_right = ")"
        if self.use_dot(node.left) or self.use_dot(node.right):
            op = " . "
            paren_left = ""
            paren_right = ""
        return paren_left + self.expr(node.left, current_klass) + op + self.expr(node.right, current_klass) + paren_right
        
    def use_dot(self, node):
        if isinstance(node, ast.Const):
            if isinstance(node.value, str):
                return True
            
        # return True if variable name contains 'str'
        elif isinstance(node, ast.Name):
            if( node.name.lower().find('str') != -1 or node.name.lower().find('buf') != -1 ):
                return True
            
        elif isinstance( node, ast.Add):
            if self.use_dot(node.left) or self.use_dot(node.right):
                return True
        return False

    def _sub(self, node, current_klass):
        return "(" + self.expr(node.left, current_klass) + " - " + self.expr(node.right, current_klass) + ")"

    def _div(self, node, current_klass):
        return "(" + self.expr(node.left, current_klass) + " / " + self.expr(node.right, current_klass) + ")"

    def _floordiv(self, node, current_klass):
        return "floor(" + self.expr(node.left, current_klass) + " / " + self.expr(node.right, current_klass) + ")"

    def _mul(self, node, current_klass):
        return "(" + self.expr(node.left, current_klass) + " * " + self.expr(node.right, current_klass) + ")"

    def _mod(self, node, current_klass):
        if isinstance(node.left, ast.Const) and isinstance(node.left.value, StringType):
            self.imported_js.add("sprintf.js") # Include the sprintf functionality if it is used
            if isinstance(node.right, ast.Tuple):
                return "sprintf("+self.expr(node.left, current_klass) + ", " + self._tuple(node.right, current_klass, brackets=False)+")"
            else:
                return "sprintf("+self.expr(node.left, current_klass) + ", " + self.expr(node.right, current_klass)+")"
        return "(" + self.expr(node.left, current_klass) + " % " + self.expr(node.right, current_klass) + ")"

    def _invert(self, node, current_klass):
        return "~" + self.expr(node.expr, current_klass)

    def _bitand(self, node, current_klass):
        return " & ".join([self.expr(child, current_klass) for child in node.nodes])

    def _bitor(self, node, current_klass):
        return " | ".join([self.expr(child, current_klass) for child in node.nodes])

    def _bitxor(self, node, current_klass):
        return " ^ ".join([self.expr(child, current_klass) for child in node.nodes])

    def _power(self, node, current_klass):
        return "pow(" + self.expr(node.left, current_klass) + ", " + self.expr(node.right, current_klass) + ")"

    def _leftshift(self, node, current_klass):
        return self.expr(node.left, current_klass) + " << " + self.expr(node.right, current_klass)

    def _rightshift(self, node, current_klass):
        return self.expr(node.left, current_klass) + " >> " + self.expr(node.right, current_klass)

    def _subscript(self, node, current_klass):
        if node.flags in ["OP_APPLY", "OP_ASSIGN"]:
            if len(node.subs) == 1:
                if isinstance(node.subs[0], ast.Sliceobj):
                    return "pyjslib_array_slice(" + self.expr(node.expr, current_klass) + ", " + self.expr(node.subs[0], current_klass) + ")" 
                else:
                    return self.expr(node.expr, current_klass) + "[" + self.expr(node.subs[0], current_klass) + "]"
            else:
                return self.expr(node.expr, current_klass) + "[/* py2php : PHP does not support non-scalar array keys */]"
                # raise TranslationError("must have one sub (in _subscript)", node)
        elif node.flags == "OP_DELETE":
            # assumption: OP_DELETE always implies a statement.
            return self._subscript_stmt( node, current_klass )
        else:
            raise TranslationError("unsupported flag (in _subscript)", node)

    def _subscript_stmt(self, node, current_klass):
        buf = u''
        if node.flags == "OP_DELETE":
            buf += self.ind() + "unset(" + self.expr(node.expr, current_klass) + "[" + self.expr(node.subs[0], current_klass) + "]);" + self.eol
        else:
            raise TranslationError("unsupported flag (in _subscript)", node)
        return buf

    def _list(self, node, current_klass):
        inners = []
        for x in node.nodes:
            buf = self.expr(x, current_klass)
            if buf.startswith( ' ('):
                print "PAREN: " + str(x)
                print "BUF: " + buf
            inners.append( buf )
        inner = ", ".join(inners)
            
        return "[" + inner + "]"

    def _dict(self, node, current_klass):
        items = []
        for x in node.items:
            key = self.expr(x[0], current_klass)
            value = self.expr(x[1], current_klass)
            items.append(key + " => " + value)
        return "[" + ", ".join(items) + "]"

    def _asstuple_foreachdict(self, node, current_klass):
        return " => ".join([self.expr(x, current_klass) for x in node.nodes])
    
    def _asstuple(self, node, current_klass):
        return "list(" + ", ".join([self.expr(x, current_klass) for x in node.nodes]) + ")"

    def _asslist(self, node, current_klass):
        return "list(" + ", ".join([self.expr(x, current_klass) for x in node.nodes]) + ")"
    
    def _assname( self, node, current_klass):
        buf = u''
        var = "$" + node.name
        if node.flags == 'OP_DELETE':
            buf = "unset(" + var + ")"
        else:
            buf = var
        return buf
            

    def _assattr( self, node, current_klass):
        return self.expr(node.expr, current_klass) + "->" + node.attrname

    def _tuple(self, node, current_klass, brackets=True):
        if brackets:
            return u"[" + u", ".join([self.expr(x, current_klass) for x in node.nodes]) + u"]"
        else:
            return u", ".join([self.expr(x, current_klass) for x in node.nodes])

    def _slice(self, node, current_klass):
        if node.flags in ["OP_APPLY", "OP_DELETE"]:
            lower = "null"
            upper = "null"
            upper_apply = "null"
            if node.lower != None:
                lower = self.expr(node.lower, current_klass)
            if node.upper != None:
                upper = upper_apply = self.expr(node.upper, current_klass)
                if  node.lower != None:
                     upper_apply = upper + " - " + lower
                     
            expr_apply = self.expr(node.expr, current_klass) + ", " + lower + ", " + upper_apply
            expr_del = self.expr(node.expr, current_klass) + ", " + lower + ", " + upper
                     
            if node.flags == "OP_APPLY":
                return  "array_slice(" + expr_apply + ")"
            elif node.flags == "OP_DELETE":
                return  "pyjslib_del_slice(" + expr_del + ")"
        else:
            raise TranslationError("unsupported flag (in _slice)", node)

    def _sliceobj(self, node, current_klass):
        step = ast.Const(1)
        start = node.nodes[0]
        stop = node.nodes[1]
        if len(node.nodes) > 2:
            step = node.nodes[2]
        
        lower = self.expr(start, current_klass)
        upper = self.expr(stop, current_klass)
        step = self.expr(step, current_klass)
                
        return u'' + lower + ", " + upper + ", " + step
        
    def _lambda(self, node, current_klass):
        buf = u''
            
        argnames = []
        for argname in node.argnames:
            if isinstance(argname, tuple):
                for a in argname:
                    argnames.append( "$" + a )
            else:
                argnames.append( "$" + argname )
        
        arg_names = list(argnames)
        normal_arg_names = list(arg_names)
        if node.kwargs: kwargname = normal_arg_names.pop()
        if node.varargs: varargname = normal_arg_names.pop()        
        
        declared_arg_names = list(normal_arg_names)
        if node.kwargs: declared_arg_names.append(kwargname)

        function_args = "(" + self._default_args_handler(node, None) + ")"
        buf += "function %s {" % (function_args) 

        buf += "return " + self.expr(node.code, None) + ";}"
        return buf

    def _global(self, node, current_klass):
        buf = self.ind() + 'global '
        names = []
        for name in node.names:
            self.method_imported_globals.add(name)
            names.append( "$" + name )
        buf += ", ".join( names ) + ";" + self.eol
            
        return buf

    def _backquote(self, node, current_klass):
        return "pyjslib_repr(" + self.expr(node.expr, current_klass) + ")"

    def _genexpr(self, node, current_klass):
        buf = "pyjslib_genexpr( function($__vars) { extract($__vars); "
        buf += self._genexprcode(node.code, current_klass)
        buf = buf + "}, get_defined_vars() )"
        return buf
    
    def _genexprcode(self, node, current_klass):
        buf = ""
        buf += self._genexprfor(node.quals[0], node.expr, node.quals, current_klass)
        return buf
    
    def _genexprfor(self, node, expr, quals, current_klass):
        assign_name = ""
        buf = u''
        dollar = '$'

        # based on Bob Ippolito's Iteration in Javascript code
        if isinstance(node.assign, ast.AssName):
            assign_name = node.assign.name
        elif isinstance(node.assign, ast.AssTuple):
            assign_name = self._asstuple(node.assign, current_klass)
            dollar = ''
        else:
            raise TranslationError("unsupported type (in _genexprfor)", node.assign)

        list_expr = self.expr(node.iter, current_klass)
                
        quals.pop(0)
        buf += "foreach( pyjslib_list(%(list_expr)s) as %(dollar)s%(assign_name)s ) {" % locals()
        for if_cond in node.ifs:
            buf += self._genexprif(if_cond, current_klass)
            buf += " "
            
        if(len(quals)):
            buf += self._genexprfor(quals[0], expr, quals, current_klass)
        else:
            buf += "yield " + self.expr(expr, current_klass) + ";"
            
        buf +=  "}"
        return buf

    def _genexprif(self, node, current_klass):
        return "if(" + self.expr(node.test, current_klass) + ")"
        
    def _listcomp(self, node, current_klass):
        buf = "pyjslib_listcomp( function($__vars) { extract($__vars); "
        buf += self._listcompfor(node.quals[0], node.expr, node.quals, current_klass)
        buf = buf + "}, get_defined_vars() )"
        return buf

    def _listcompfor(self, node, expr, quals, current_klass):
        assign_name = ""
        buf = u''
        dollar = '$'

        # based on Bob Ippolito's Iteration in Javascript code
        if isinstance(node.assign, ast.AssName):
            assign_name = node.assign.name
        elif isinstance(node.assign, ast.AssTuple):
            assign_name = self._asstuple(node.assign, current_klass)
            dollar = ''
        else:
            raise TranslationError("unsupported type (in _listcompfor)", node.assign)

        list_expr = self.expr(node.list, current_klass)
        
        quals.pop(0)
        buf += "foreach( pyjslib_list(%(list_expr)s) as %(dollar)s%(assign_name)s ) {" % locals()
        for if_cond in node.ifs:
            buf += self._listcompif(if_cond, current_klass)
            buf += " "
            
        if(len(quals)):
            buf += self._listcompfor(quals[0], expr, quals, current_klass)
        else:
            buf += "yield " + self.expr(expr, current_klass) + ";"
            
        buf +=  "}"
        return buf

    def _listcompif(self, node, current_klass):
        return "if(" + self.expr(node.test, current_klass) + ")"

    def _with(self, node, current_klass):
        buf = '// py2php.fixme "with" unsupported.' + self.eol
        return buf


    def expr(self, node, current_klass):
        #print "NODER: " + str(node)
        if isinstance(node, ast.Const):
            return self._const(node)
        # @@@ not sure if the parentheses should be here or in individual operator functions - JKT
        elif isinstance(node, ast.Mul):
            return self._mul(node, current_klass)
        elif isinstance(node, ast.Add):
            return self._add(node, current_klass)
        elif isinstance(node, ast.Sub):
            return self._sub(node, current_klass)
        elif isinstance(node, ast.Div):
            return self._div(node, current_klass)
        elif isinstance(node, ast.FloorDiv):
            return self._div(node, current_klass)        
        elif isinstance(node, ast.Mod):
            return self._mod(node, current_klass)
        elif isinstance(node, ast.UnarySub):
            return self._unarysub(node, current_klass)
        elif isinstance(node, ast.UnaryAdd):
            return self._unaryadd(node, current_klass)
        elif isinstance(node, ast.Not):
            return self._not(node, current_klass)
        elif isinstance(node, ast.Or):
            return self._or(node, current_klass)
        elif isinstance(node, ast.And):
            return self._and(node, current_klass)
        elif isinstance(node, ast.Invert):
            return self._invert(node, current_klass)
        elif isinstance(node, ast.Bitand):
            return self._bitand(node, current_klass)
        elif isinstance(node, ast.Bitor):
            return self._bitor(node, current_klass)
        elif isinstance(node, ast.Bitxor):
            return self._bitxor(node, current_klass)
        elif isinstance(node, ast.Power):
            return self._power(node, current_klass)                
        elif isinstance(node, ast.LeftShift):
            return self._leftshift(node, current_klass)
        elif isinstance(node, ast.RightShift):
            return self._rightshift(node, current_klass)                
        elif isinstance(node, ast.Compare):
            return self._compare(node, current_klass)
        elif isinstance(node, ast.CallFunc):
            return self._callfunc(node, current_klass)
        elif isinstance(node, ast.Name):
            return self._name(node)
        elif isinstance(node, ast.Subscript):
            return self._subscript(node, current_klass)
        elif isinstance(node, ast.Getattr):
            return self._getattr(node)
        elif isinstance(node, ast.List):
            return self._list(node, current_klass)
        elif isinstance(node, ast.Dict):
            return self._dict(node, current_klass)
        elif isinstance(node, ast.Tuple):
            return self._tuple(node, current_klass)
        elif isinstance(node, ast.AssName):
            return self._assname(node, current_klass)        
        elif isinstance(node, ast.AssAttr):
            return self._assattr(node, current_klass)        
        elif isinstance(node, ast.Slice):
            return self._slice(node, current_klass)
        elif isinstance(node, ast.Sliceobj):
            return self._sliceobj(node, current_klass)
        elif isinstance(node, ast.Lambda):
            return self._lambda(node, current_klass)        
        elif isinstance(node, ast.IfExp):
            return self._ifexp(node, current_klass)        
        elif isinstance(node, ast.ListComp):
            return self._listcomp(node, current_klass)
        elif isinstance(node, ast.GenExpr):
            return self._genexpr(node, current_klass)        
        elif isinstance(node, ast.ListCompFor):
            return self._listcompfor(node, current_klass)        
        elif isinstance(node, ast.ListCompIf):
            return self._listcompif(node, current_klass)        
        elif isinstance(node, ast.AssTuple):
            return self._asstuple(node, current_klass)
        elif isinstance(node, ast.Class):
            return self._class(node)
        elif isinstance(node, ast.Backquote):
            return self._backquote(node, current_klass)
        elif isinstance(node, ast.Yield):
            return self._yield(node, current_klass)
        
        else:
            raise TranslationError("unsupported type (in expr)", node)



import StringIO

def translate(file_name, module_name):
    output = StringIO.StringIO()
    mod = compiler.parseFile(file_name)
    t = Translator(module_name, mod, output)
    return output.getvalue()

class PlatformParser:
    def __init__(self, platform_dir = ""):
        self.platform_dir = platform_dir
        self.parse_cache = {}
        self.platform = ""

    def setPlatform(self, platform):
        self.platform = platform
        
    def parseModule(self, module_name, file_name):
        if self.parse_cache.has_key(file_name):
            mod = self.parse_cache[file_name]
        else:
            print "Importing " + module_name
            mod = compiler.parseFile(file_name)
            self.parse_cache[file_name] = mod
        
        platform_file_name = self.generatePlatformFilename(file_name)
        if self.platform and os.path.isfile(platform_file_name):
            mod = copy.deepcopy(mod)
            mod_override = compiler.parseFile(platform_file_name)
            self.merge(mod, mod_override)

        return mod
        
    def generatePlatformFilename(self, file_name):
        (module_name, extension) = os.path.splitext(os.path.basename(file_name))
        platform_file_name = module_name + self.platform + extension
        
        return os.path.join(os.path.dirname(file_name), self.platform_dir, platform_file_name)

    def merge(self, tree1, tree2):
        for child in tree2.node:
            if isinstance(child, ast.Function):
                self.replaceFunction(tree1, child.name, child)
            elif isinstance(child, ast.Class):
                self.replaceClassMethods(tree1, child.name, child)

        return tree1
            
    def replaceFunction(self, tree, function_name, function_node):
        # find function to replace
        for child in tree.node:
            if isinstance(child, ast.Function) and child.name == function_name:
                self.copyFunction(child, function_node)
                return
        raise TranslationError("function not found: " + function_name, function_node)

    def replaceClassMethods(self, tree, class_name, class_node):
        # find class to replace
        old_class_node = None
        for child in tree.node:
            if isinstance(child, ast.Class) and child.name == class_name:
                old_class_node = child
                break
        
        if not old_class_node:
            raise TranslationError("class not found: " + class_name, class_node)
        
        # replace methods
        for function_node in class_node.code:
            if isinstance(function_node, ast.Function):
                found = False
                for child in old_class_node.code:
                    if isinstance(child, ast.Function) and child.name == function_node.name:
                        found = True
                        self.copyFunction(child, function_node)
                        break

                if not found:
                    raise TranslationError("class method not found: " + class_name + "::" + function_node.name, function_node)

    def copyFunction(self, target, source):
        target.code = source.code
        target.argnames = source.argnames
        target.defaults = source.defaults
        target.doc = source.doc # @@@ not sure we need to do this any more


class AppTranslator:

    def __init__(self, library_dirs=["../library"], parser=None):
        self.extension = ".py"

        self.library_modules = []
        self.library_dirs = library_dirs
        
        if not parser:
            self.parser = PlatformParser()
        else:
            self.parser = parser

    def findFile(self, file_name):
        if os.path.isfile(file_name):
            return file_name

        if file_name[:8] == 'pyjamas.': # strip off library name
            if file_name != "pyjamas.py":
                file_name = file_name[8:]
        for library_dir in self.library_dirs:
            full_file_name = os.path.join(os.path.dirname(__file__), library_dir, file_name)
            if os.path.isfile(full_file_name):
                return full_file_name
        
        raise Exception("file not found: " + file_name)
    
    def translate(self, module_name, is_app=True):

        if module_name not in self.library_modules:
            self.library_modules.append(module_name)
        
        file_name = self.findFile(module_name + self.extension)
        
        if is_app:
            module_name_translated = ""
        else:
            module_name_translated = module_name
        
        output = cStringIO.StringIO()
        
        mod = self.parser.parseModule(module_name, file_name)
        t = Translator(module_name_translated, mod, output)
        module_str = output.getvalue()
        
        imported_modules_str = ''
        for module in t.imported_modules:
            if module not in self.library_modules:
                imported_modules_str += self.translate(module, False)
        for js in t.imported_js:
           path = self.findFile(js)
           if os.path.isfile(path):
              print 'Including', js
              imported_modules_str += '\n//\n// BEGIN '+js+'\n//\n'
              imported_modules_str += file(path).read()
              imported_modules_str += '\n//\n// END '+js+'\n//\n'
           else:
              print >>sys.stderr, 'Warning: Unable to find imported javascript:', js

        if module_name == 'pyjamas':
            return imported_modules_str 
        return imported_modules_str + module_str

    def translateLibraries(self, library_modules=[]):
        self.library_modules = library_modules

        imported_modules_str = ""
        for library in self.library_modules:
            imported_modules_str += self.translate(library, False)
        
        return imported_modules_str


if __name__ == "__main__":
    import sys
    file_name = sys.argv[1]
    output_filename = os.path.splitext(os.path.basename(file_name))[0] + ".php"
    if len(sys.argv) > 2:
        module_name = sys.argv[2]
    else:
        module_name = None

    math_expression_php = ["acosh", "acos", "asinh", "asin", "atan2", "atanh", "atan", "ceil", "cosh", "cos", "deg2rad", "expm1", "exp", "M_E", "floor", "fmod", "hypot", "is_infinite", "is_nan", "log10", "log1p", "log", "modf", "M_PI", "pow", "rad2deg", "sinh", "sin", "sqrt", "tanh", "tan"]
    math_expressions_py = ['acosh', 'acos', 'asinh', 'asin', 'atan2', 'atanh', 'atan', 'ceil', 'cosh', 'cos', 'radians', 'expm1', 'exp', 'e',   'floor', 'fmod', 'hypot', 'isinf',       'isnan',  'log10', 'log1p', 'log', 'modf', 'pi',   'pow', 'degrees', 'sinh', 'sin', 'sqrt', 'tanh', 'tan']

    # retrieve and keep the comments in the python file:
    pythonfile = open(file_name, "rb")
    lines = pythonfile.readlines()
    pythonfile.close()
    coding = ""
    codetag = "# -*- coding:"
    lc = len(codetag)
    math_included = False
    for line in lines:
        if line.startswith(codetag):
            end = line[lc:].find("-*-")
            coding = line[lc:lc+end].strip(" ").lstrip(" ")
            print "coding of the file:", coding
        if "import math" in line:
            math_included = True
    if coding == "":
        coding = "utf-8"
    new_lines = []
    for line in lines:
        if line.lstrip(" \t").startswith("#"):
            tag = line.find("#")
            line = line[:tag] + '"""' + line.strip()[tag+1:] + '"""\n'
        new_lines.append(line.decode(coding))
    pythonfile = open("tmp.py", "wb")
    for line in new_lines:
        pythonfile.write(line.encode(coding))
    pythonfile.close()
    # necessary for print unicode to non utf-8 output, eg redirect to file.
    # python 2.x is crazy.
    # see: https://wiki.python.org/moin/PrintFails
    sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout);
    
    translated_code = "<?php " + translate("tmp.py", module_name),
    # print translated_code, type(translated_code)
    tagname = "math::"
    save_file = open(output_filename, "wb")
    for line in translated_code[0].split("\n"):
        if math_included:
            found = True
            while tagname in line and found:
                tag = line.find(tagname)
                line_rest = line[tag+len(tagname):]
                found = False
                for i, exp in enumerate(math_expressions_py):
                    if line_rest.startswith(exp):
                        line = line[:tag] + math_expression_php[i] + line_rest[len(exp):] 
                        found = True
                        break
            if "require_once( 'math.php');" in line:
                line = """function modf($zahl) {
    return [$zahl-pyjslib_int($zahl), pyjslib_int($zahl)];
} """
        save_file.write(line.encode(coding)+"\n")
    save_file.close()
    print "File written to:", output_filename
