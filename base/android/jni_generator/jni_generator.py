#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Extracts native methods from a Java file and generates the JNI bindings.
If you change this, please run and update the tests."""

import collections
import optparse
import os
import re
import string
from string import Template
import subprocess
import sys
import textwrap


UNKNOWN_JAVA_TYPE_PREFIX = 'UNKNOWN_JAVA_TYPE: '


class ParseError(Exception):
  """Exception thrown when we can't parse the input file."""

  def __init__(self, description, *context_lines):
    Exception.__init__(self)
    self.description = description
    self.context_lines = context_lines

  def __str__(self):
    context = '\n'.join(self.context_lines)
    return '***\nERROR: %s\n\n%s\n***' % (self.description, context)


class Param(object):
  """Describes a param for a method, either java or native."""

  def __init__(self, **kwargs):
    self.datatype = kwargs['datatype']
    self.name = kwargs['name']
    self.cpp_class_name = kwargs.get('cpp_class_name', None)


class NativeMethod(object):
  """Describes a C/C++ method that is called by Java code"""

  def __init__(self, **kwargs):
    self.static = kwargs['static']
    self.java_class_name = kwargs['java_class_name']
    self.return_type = kwargs['return_type']
    self.name = kwargs['name']
    self.params = kwargs['params']
    if self.params:
      assert type(self.params) is list
      assert type(self.params[0]) is Param
    if (self.params and
        self.params[0].datatype == 'int' and
        self.params[0].name.startswith('native')):
      self.type = 'method'
      if self.params[0].cpp_class_name:
        self.p0_type = self.params[0].cpp_class_name
      else:
        self.p0_type = self.params[0].name[len('native'):]
    elif self.static:
      self.type = 'function'
    else:
      self.type = 'function'
    self.method_id_var_name = kwargs.get('method_id_var_name', None)


class CalledByNative(object):
  """Describes a java method exported to c/c++"""

  def __init__(self, **kwargs):
    self.system_class = kwargs['system_class']
    self.unchecked = kwargs['unchecked']
    self.static = kwargs['static']
    self.java_class_name = kwargs['java_class_name']
    self.return_type = kwargs['return_type']
    self.env_call = kwargs['env_call']
    self.name = kwargs['name']
    self.params = kwargs['params']
    self.method_id_var_name = kwargs.get('method_id_var_name', None)


def JavaDataTypeToC(java_type):
  """Returns a C datatype for the given java type."""
  java_pod_type_map = {
      'int': 'jint',
      'byte': 'jbyte',
      'boolean': 'jboolean',
      'long': 'jlong',
      'double': 'jdouble',
      'float': 'jfloat',
  }
  java_type_map = {
      'void': 'void',
      'String': 'jstring',
  }
  if java_type in java_pod_type_map:
    return java_pod_type_map[java_type]
  elif java_type in java_type_map:
    return java_type_map[java_type]
  elif java_type.endswith('[]'):
    if java_type[:-2] in java_pod_type_map:
      return java_pod_type_map[java_type[:-2]] + 'Array'
    return 'jobjectArray'
  else:
    return 'jobject'


def JavaParamToJni(param):
  """Converts a java param into a JNI signature type."""
  pod_param_map = {
      'int': 'I',
      'boolean': 'Z',
      'long': 'J',
      'double': 'D',
      'float': 'F',
      'byte': 'B',
      'void': 'V',
  }
  object_param_list = [
      'Ljava/lang/String',
      'Ljava/lang/Boolean',
      'Ljava/lang/Integer',
      'Ljava/lang/Long',
      'Ljava/lang/Object',
      'Ljava/util/List',
      'Ljava/util/ArrayList',
      'Ljava/util/HashMap',
      'Landroid/graphics/Bitmap',
      'Landroid/content/Context',
      'Landroid/graphics/Canvas',
      'Landroid/view/Surface',
      'Landroid/view/KeyEvent',
      'Landroid/graphics/Rect',
      'Landroid/graphics/RectF',
      'Landroid/view/View',
      'Landroid/graphics/Matrix',
      'Landroid/graphics/Point',
      'Ljava/nio/ByteBuffer',
      'Ljava/io/InputStream',
      'Ljava/util/Vector',
  ]
  app_param_list = [
      'Lorg/chromium/chromeview/ChromeView',
      'Lcom/android/chrome/Tab',
      'Lorg/chromium/chromeview/TouchPoint',
      'Landroid/graphics/SurfaceTexture',
      'Lorg/chromium/chromeview/ChromeViewClient',
      'Lcom/android/chrome/JSModalDialog',
      'Lcom/android/chrome/infobar/InfoBarContainer$NativeInfoBar',
      'Lcom/android/chrome/OmniboxSuggestion',
      ('Lcom/android/chrome/preferences/ChromeNativePreferences$'
       'PasswordListObserver'),
      'Lorg/chromium/chromeview/SandboxedProcessArgs',
      'Lorg/chromium/chromeview/SandboxedProcessConnection',
      'Lorg/chromium/chromeview/SandboxedProcessService',
      'Lcom/android/chrome/ChromeBrowserProvider$BookmarkNode',
      'Lcom/android/chrome/database/SQLiteCursor',
      ('Lorg/chromium/chromeview/ChromeView$'
       'FindResultReceivedListener$FindNotificationDetails'),
      'Lorg/chromium/chromeview/ChromeView$ChromeViewContextMenuInfo',
      'Lorg/chromium/chromeview/AutofillData',
      'Lorg/chromium/chromeview/JavaInputStream',
      'Lorg/chromium/chromeview/ChromeVideoView',
      'Lorg/chromium/chromeview/ChromeHttpAuthHandler',
      'Lorg/chromium/base/SystemMessageHandler',
      'Lorg/chromium/chromeview/SelectFileDialog',
      'Lorg/chromium/chromeview/SurfaceTextureListener',
      'Lorg/chromium/chromeview/DeviceOrientation',
      'Lorg/chromium/chromeview/MediaPlayerListener',
      'Lorg/chromium/chromeview/DeviceInfo',
      'Lorg/chromium/chromeview/LocationProvider',
      'Lcom/android/chrome/PageInfoViewer',
  ]
  if param == 'byte[][]':
    return '[[B'
  prefix = ''
  # Array?
  if param[-2:] == '[]':
    prefix = '['
    param = param[:-2]
  # Generic?
  if '<' in param:
    param = param[:param.index('<')]
  if param in pod_param_map:
    return prefix + pod_param_map[param]
  for qualified_name in object_param_list + app_param_list:
    if (qualified_name.endswith('/' + param) or
        qualified_name.endswith('$' + param.replace('.', '$'))):
      return prefix + qualified_name + ';'
  else:
    return UNKNOWN_JAVA_TYPE_PREFIX + prefix + param + ';'


def JniSignature(params, returns, wrap):
  """Returns the JNI signature for the given datatypes."""
  items = ['(']
  items += [JavaParamToJni(param.datatype) for param in params]
  items += [')']
  items += [JavaParamToJni(returns)]
  if wrap:
    return '\n' + '\n'.join(['"' + item + '"' for item in items])
  else:
    return '"' + ''.join(items) + '"'


def ParseParams(params):
  """Parses the params into a list of Param objects."""
  if not params:
    return []
  ret = []
  re_comment = re.compile(r'.*?\/\* (.*) \*\/')
  for p in [p.strip() for p in params.split(',')]:
    items = p.split(' ')
    if 'final' in items:
      items.remove('final')
    comment = re.match(re_comment, p)
    param = Param(
        datatype=items[0],
        name=(items[1] if len(items) > 1 else 'p%s' % len(ret)),
        cpp_class_name=comment.group(1) if comment else None
    )
    ret += [param]
  return ret


def GetUnknownDatatypes(items):
  """Returns a list containing the unknown datatypes."""
  unknown_types = {}
  for item in items:
    all_datatypes = ([JavaParamToJni(param.datatype)
                      for param in item.params] +
                     [JavaParamToJni(item.return_type)])
    for d in all_datatypes:
      if d.startswith(UNKNOWN_JAVA_TYPE_PREFIX):
        unknown_types[d] = (unknown_types.get(d, []) +
                            [item.name or 'Unable to parse'])
  return unknown_types


def ExtractFullyQualifiedJavaClassName(java_file_name, contents):
  re_package = re.compile('.*?package (.*?);')
  matches = re.findall(re_package, contents)
  if not matches:
    raise SyntaxError('Unable to find "package" line in %s' % java_file_name)
  return (matches[0].replace('.', '/') + '/' +
          os.path.splitext(os.path.basename(java_file_name))[0])


def ExtractNatives(contents):
  """Returns a list of dict containing information about a native method."""
  contents = contents.replace('\n', '')
  natives = []
  re_native = re.compile(r'(@NativeCall(\(\"(.*?)\"\)))?\s*'
                         '(\w+\s\w+|\w+|\s+)\s*?native (\S*?) (\w+?)\((.*?)\);')
  matches = re.findall(re_native, contents)
  for match in matches:
    native = NativeMethod(
        static='static' in match[3],
        java_class_name=match[2],
        return_type=match[4],
        name=match[5].replace('native', ''),
        params=ParseParams(match[6]))
    natives += [native]
  return natives


def GetEnvCallForReturnType(return_type):
  """Maps the types availabe via env->Call__Method."""
  env_call_map = {'boolean': ('Boolean', ''),
                  'byte': ('Byte', ''),
                  'char': ('Char', ''),
                  'short': ('Short', ''),
                  'int': ('Int', ''),
                  'long': ('Long', ''),
                  'float': ('Float', ''),
                  'void': ('Void', ''),
                  'double': ('Double', ''),
                  'String': ('Object', 'jstring'),
                  'Object': ('Object', ''),
                 }
  return env_call_map.get(return_type, ('Object', ''))


def GetMangledMethodName(name, jni_signature):
  """Returns a mangled method name for a (name, jni_signature) pair.

     The returned name can be used as a C identifier and will be unique for all
     valid overloads of the same method.

  Args:
     name: string.
     jni_signature: string.

  Returns:
      A mangled name.
  """
  sig_translation = string.maketrans('[()/;$', 'apq_xs')
  mangled_name = name + '_' + string.translate(jni_signature, sig_translation,
                                               '"')
  assert re.match(r'[0-9a-zA-Z_]+', mangled_name)
  return mangled_name


def MangleCalledByNatives(called_by_natives):
  """Mangles all the overloads from the call_by_natives list."""
  method_counts = collections.defaultdict(
      lambda: collections.defaultdict(lambda: 0))
  for called_by_native in called_by_natives:
    java_class_name = called_by_native.java_class_name
    name = called_by_native.name
    method_counts[java_class_name][name] += 1
  for called_by_native in called_by_natives:
    java_class_name = called_by_native.java_class_name
    method_name = called_by_native.name
    method_id_var_name = method_name
    if method_counts[java_class_name][method_name] > 1:
      jni_signature = JniSignature(called_by_native.params,
                                   called_by_native.return_type,
                                   False)
      method_id_var_name = GetMangledMethodName(method_name, jni_signature)
    called_by_native.method_id_var_name = method_id_var_name
  return called_by_natives


# Regex to match the JNI return types that should be included in a
# ScopedJavaLocalRef.
RE_SCOPED_JNI_RETURN_TYPES = re.compile('jobject|jclass|jstring|.*Array')

# Regex to match a string like "@CalledByNative public void foo(int bar)".
RE_CALLED_BY_NATIVE = re.compile(
    '@CalledByNative(?P<Unchecked>(Unchecked)*?)(?:\("(?P<annotation>.*)"\))?'
    '\s+(?P<prefix>[\w ]*?)'
    '\s*(?P<return_type>\w+)'
    '\s+(?P<name>\w+)'
    '\s*\((?P<params>[^\)]*)\)')


def ExtractCalledByNatives(contents):
  """Parses all methods annotated with @CalledByNative.

  Args:
    contents: the contents of the java file.

  Returns:
    A list of dict with information about the annotated methods.
    TODO(bulach): return a CalledByNative object.

  Raises:
    ParseError: if unable to parse.
  """
  called_by_natives = []
  for match in re.finditer(RE_CALLED_BY_NATIVE, contents):
    called_by_natives += [CalledByNative(
        system_class=False,
        unchecked='Unchecked' in match.group('Unchecked'),
        static='static' in match.group('prefix'),
        java_class_name=match.group('annotation') or '',
        return_type=match.group('return_type'),
        env_call=GetEnvCallForReturnType(match.group('return_type')),
        name=match.group('name'),
        params=ParseParams(match.group('params')))]
  # Check for any @CalledByNative occurrences that weren't matched.
  unmatched_lines = re.sub(RE_CALLED_BY_NATIVE, '', contents).split('\n')
  for line1, line2 in zip(unmatched_lines, unmatched_lines[1:]):
    if '@CalledByNative' in line1:
      raise ParseError('could not parse @CalledByNative method signature',
                       line1, line2)
  return MangleCalledByNatives(called_by_natives)


class JNIFromJavaP(object):
  """Uses 'javap' to parse a .class file and generate the JNI header file."""

  def __init__(self, contents, namespace):
    self.contents = contents
    self.namespace = namespace
    self.fully_qualified_class = re.match('.*?class (.*?) ',
                                          contents[1]).group(1)
    self.fully_qualified_class = self.fully_qualified_class.replace('.', '/')
    self.java_class_name = self.fully_qualified_class.split('/')[-1]
    if not self.namespace:
      self.namespace = 'JNI_' + self.java_class_name
    re_method = re.compile('(.*?)(\w+?) (\w+?)\((.*?)\)')
    self.called_by_natives = []
    for method in contents[2:]:
      match = re.match(re_method, method)
      if not match:
        continue
      self.called_by_natives += [CalledByNative(
          system_class=True,
          unchecked=False,
          static='static' in match.group(1),
          java_class_name='',
          return_type=match.group(2),
          name=match.group(3),
          params=ParseParams(match.group(4)),
          env_call=GetEnvCallForReturnType(match.group(2)))]
    self.called_by_natives = MangleCalledByNatives(self.called_by_natives)
    self.inl_header_file_generator = InlHeaderFileGenerator(
        self.namespace, self.fully_qualified_class, [], self.called_by_natives)

  def GetContent(self):
    return self.inl_header_file_generator.GetContent()

  @staticmethod
  def CreateFromClass(class_file, namespace):
    class_name = os.path.splitext(os.path.basename(class_file))[0]
    p = subprocess.Popen(args=['javap', class_name],
                         cwd=os.path.dirname(class_file),
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    stdout, _ = p.communicate()
    jni_from_javap = JNIFromJavaP(stdout.split('\n'), namespace)
    return jni_from_javap


class JNIFromJavaSource(object):
  """Uses the given java source file to generate the JNI header file."""

  def __init__(self, contents, fully_qualified_class):
    contents = self._RemoveComments(contents)
    natives = ExtractNatives(contents)
    called_by_natives = ExtractCalledByNatives(contents)
    inl_header_file_generator = InlHeaderFileGenerator(
        '', fully_qualified_class, natives, called_by_natives)
    self.content = inl_header_file_generator.GetContent()

  def _RemoveComments(self, contents):
    ret = []
    for c in [c.strip() for c in contents.split('\n')]:
      if not c.startswith('//'):
        ret += [c]
    return '\n'.join(ret)

  def GetContent(self):
    return self.content

  @staticmethod
  def CreateFromFile(java_file_name):
    contents = file(java_file_name).read()
    fully_qualified_class = ExtractFullyQualifiedJavaClassName(java_file_name,
                                                               contents)
    return JNIFromJavaSource(contents, fully_qualified_class)


class InlHeaderFileGenerator(object):
  """Generates an inline header file for JNI integration."""

  def __init__(self, namespace, fully_qualified_class, natives,
               called_by_natives):
    self.namespace = namespace
    self.fully_qualified_class = fully_qualified_class
    self.class_name = self.fully_qualified_class.split('/')[-1]
    self.natives = natives
    self.called_by_natives = called_by_natives
    self.header_guard = fully_qualified_class.replace('/', '_') + '_JNI'
    unknown_datatypes = GetUnknownDatatypes(self.natives +
                                            self.called_by_natives)
    if unknown_datatypes:
      msg = ('There are a few unknown datatypes in %s' %
             self.fully_qualified_class)
      msg += '\nPlease, edit %s' % sys.argv[0]
      msg += '\nand add the java type to JavaParamToJni()\n'
      for unknown_datatype in unknown_datatypes:
        msg += '\n%s in methods:\n' % unknown_datatype
        msg += '\n '.join(unknown_datatypes[unknown_datatype])
      raise SyntaxError(msg)

  def GetContent(self):
    """Returns the content of the JNI binding file."""
    template = Template("""\
// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


// This file is autogenerated by
//     ${SCRIPT_NAME}
// For
//     ${FULLY_QUALIFIED_CLASS}

#ifndef ${HEADER_GUARD}
#define ${HEADER_GUARD}

#include <jni.h>

#include "base/android/jni_android.h"
#include "base/android/scoped_java_ref.h"
#include "base/basictypes.h"
#include "base/logging.h"

using base::android::ScopedJavaLocalRef;

// Step 1: forward declarations.
namespace {
$CLASS_PATH_DEFINITIONS
}  // namespace
$FORWARD_DECLARATIONS

// Step 2: method stubs.
$METHOD_STUBS

// Step 3: GetMethodIDs and RegisterNatives.
$OPEN_NAMESPACE

static void GetMethodIDsImpl(JNIEnv* env) {
$GET_METHOD_IDS_IMPL
}

static bool RegisterNativesImpl(JNIEnv* env) {
  ${NAMESPACE}GetMethodIDsImpl(env);
$REGISTER_NATIVES_IMPL
  return true;
}
$CLOSE_NAMESPACE
#endif  // ${HEADER_GUARD}
""")
    script_components = os.path.abspath(sys.argv[0]).split(os.path.sep)
    base_index = script_components.index('base')
    script_name = os.sep.join(script_components[base_index:])
    values = {
        'SCRIPT_NAME': script_name,
        'FULLY_QUALIFIED_CLASS': self.fully_qualified_class,
        'CLASS_PATH_DEFINITIONS': self.GetClassPathDefinitionsString(),
        'FORWARD_DECLARATIONS': self.GetForwardDeclarationsString(),
        'METHOD_STUBS': self.GetMethodStubsString(),
        'OPEN_NAMESPACE': self.GetOpenNamespaceString(),
        'NAMESPACE': self.GetNamespaceString(),
        'GET_METHOD_IDS_IMPL': self.GetMethodIDsImplString(),
        'REGISTER_NATIVES_IMPL': self.GetRegisterNativesImplString(),
        'CLOSE_NAMESPACE': self.GetCloseNamespaceString(),
        'HEADER_GUARD': self.header_guard,
    }
    return WrapOutput(template.substitute(values))

  def GetClassPathDefinitionsString(self):
    ret = []
    ret += [self.GetClassPathDefinitions()]
    return '\n'.join(ret)

  def GetForwardDeclarationsString(self):
    ret = []
    for native in self.natives:
      if native.type != 'method':
        ret += [self.GetForwardDeclaration(native)]
    return '\n'.join(ret)

  def GetMethodStubsString(self):
    ret = []
    for native in self.natives:
      if native.type == 'method':
        ret += [self.GetNativeMethodStub(native)]
    for called_by_native in self.called_by_natives:
      ret += [self.GetCalledByNativeMethodStub(called_by_native)]
    return '\n'.join(ret)

  def GetKMethodsString(self, clazz):
    ret = []
    for native in self.natives:
      if (native.java_class_name == clazz or
          (not native.java_class_name and clazz == self.class_name)):
        ret += [self.GetKMethodArrayEntry(native)]
    return '\n'.join(ret)

  def GetMethodIDsImplString(self):
    ret = []
    ret += [self.GetFindClasses()]
    for called_by_native in self.called_by_natives:
      ret += [self.GetMethodIDImpl(called_by_native)]
    return '\n'.join(ret)

  def GetRegisterNativesImplString(self):
    """Returns the implementation for RegisterNatives."""
    template = Template("""\
  static const JNINativeMethod kMethods${JAVA_CLASS}[] = {
${KMETHODS}
  };
  const int kMethods${JAVA_CLASS}Size = arraysize(kMethods${JAVA_CLASS});

  if (env->RegisterNatives(g_${JAVA_CLASS}_clazz,
                           kMethods${JAVA_CLASS},
                           kMethods${JAVA_CLASS}Size) < 0) {
    LOG(ERROR) << "RegisterNatives failed in " << __FILE__;
    return false;
  }
""")
    ret = []
    all_classes = self.GetUniqueClasses(self.natives)
    all_classes[self.class_name] = self.fully_qualified_class
    for clazz in all_classes:
      kmethods = self.GetKMethodsString(clazz)
      if kmethods:
        values = {'JAVA_CLASS': clazz,
                  'KMETHODS': kmethods}
        ret += [template.substitute(values)]
    if not ret: return ''
    return '\n' + '\n'.join(ret)

  def GetOpenNamespaceString(self):
    if self.namespace:
      return 'namespace %s {' % self.namespace
    return ''

  def GetNamespaceString(self):
    if self.namespace:
      return '%s::' % self.namespace
    return ''

  def GetCloseNamespaceString(self):
    if self.namespace:
      return '}  // namespace %s\n' % self.namespace
    return ''

  def GetJNIFirstParam(self, native):
    ret = []
    if native.type == 'method':
      ret = ['jobject obj']
    elif native.type == 'function':
      if native.static:
        ret = ['jclass clazz']
      else:
        ret = ['jobject obj']
    return ret

  def GetParamsInDeclaration(self, native):
    """Returns the params for the stub declaration.

    Args:
      native: the native dictionary describing the method.

    Returns:
      A string containing the params.
    """
    return ',\n    '.join(self.GetJNIFirstParam(native) +
                          [JavaDataTypeToC(param.datatype) + ' ' +
                           param.name
                           for param in native.params])

  def GetCalledByNativeParamsInDeclaration(self, called_by_native):
    return ',\n    '.join([JavaDataTypeToC(param.datatype) + ' ' +
                           param.name
                           for param in called_by_native.params])

  def GetForwardDeclaration(self, native):
    template = Template("""
static ${RETURN} ${NAME}(JNIEnv* env, ${PARAMS});
""")
    values = {'RETURN': JavaDataTypeToC(native.return_type),
              'NAME': native.name,
              'PARAMS': self.GetParamsInDeclaration(native)}
    return template.substitute(values)

  def GetNativeMethodStub(self, native):
    """Returns stubs for native methods."""
    template = Template("""\
static ${RETURN} ${NAME}(JNIEnv* env, ${PARAMS_IN_DECLARATION}) {
  DCHECK(${PARAM0_NAME}) << "${NAME}";
  ${P0_TYPE}* native = reinterpret_cast<${P0_TYPE}*>(${PARAM0_NAME});
  return native->${NAME}(env, obj${PARAMS_IN_CALL})${POST_CALL};
}
""")
    params_for_call = ', '.join(p.name for p in native.params[1:])
    if params_for_call:
      params_for_call = ', ' + params_for_call

    return_type = JavaDataTypeToC(native.return_type)
    if re.match(RE_SCOPED_JNI_RETURN_TYPES, return_type):
      scoped_return_type = 'ScopedJavaLocalRef<' + return_type + '>'
      post_call = '.Release()'
    else:
      scoped_return_type = return_type
      post_call = ''
    values = {
        'RETURN': return_type,
        'SCOPED_RETURN': scoped_return_type,
        'NAME': native.name,
        'PARAMS_IN_DECLARATION': self.GetParamsInDeclaration(native),
        'PARAM0_NAME': native.params[0].name,
        'P0_TYPE': native.p0_type,
        'PARAMS_IN_CALL': params_for_call,
        'POST_CALL': post_call
    }
    return template.substitute(values)

  def GetCalledByNativeMethodStub(self, called_by_native):
    """Returns a string."""
    function_signature_template = Template("""\
static ${RETURN_TYPE} Java_${JAVA_CLASS}_${METHOD}(\
JNIEnv* env${FIRST_PARAM_IN_DECLARATION}${PARAMS_IN_DECLARATION})""")
    function_header_template = Template("""\
${FUNCTION_SIGNATURE} {""")
    function_header_with_unused_template = Template("""\
${FUNCTION_SIGNATURE} __attribute__ ((unused));
${FUNCTION_SIGNATURE} {""")
    template = Template("""
static jmethodID g_${JAVA_CLASS}_${METHOD_ID_VAR_NAME} = 0;
${FUNCTION_HEADER}
  /* Must call RegisterNativesImpl()  */
  DCHECK(g_${JAVA_CLASS}_clazz);
  DCHECK(g_${JAVA_CLASS}_${METHOD_ID_VAR_NAME});
  ${RETURN_DECLARATION}
  ${PRE_CALL}env->Call${STATIC}${ENV_CALL}Method(${FIRST_PARAM_IN_CALL},
      g_${JAVA_CLASS}_${METHOD_ID_VAR_NAME}${PARAMS_IN_CALL})${POST_CALL};
  ${CHECK_EXCEPTION}
  ${RETURN_CLAUSE}
}""")
    if called_by_native.static:
      first_param_in_declaration = ''
      first_param_in_call = ('g_%s_clazz' %
                             (called_by_native.java_class_name or
                              self.class_name))
    else:
      first_param_in_declaration = ', jobject obj'
      first_param_in_call = 'obj'
    params_in_declaration = self.GetCalledByNativeParamsInDeclaration(
        called_by_native)
    if params_in_declaration:
      params_in_declaration = ', ' + params_in_declaration
    params_for_call = ', '.join(param.name
                                for param in called_by_native.params)
    if params_for_call:
      params_for_call = ', ' + params_for_call
    pre_call = ''
    post_call = ''
    if called_by_native.env_call[1]:
      pre_call = 'static_cast<%s>(' % called_by_native.env_call[1]
      post_call = ')'
    check_exception = ''
    if not called_by_native.unchecked:
      check_exception = 'base::android::CheckException(env);'
    return_type = JavaDataTypeToC(called_by_native.return_type)
    return_declaration = ''
    return_clause = ''
    if return_type != 'void':
      pre_call = '  ' + pre_call
      return_declaration = return_type + ' ret ='
      if re.match(RE_SCOPED_JNI_RETURN_TYPES, return_type):
        return_type = 'ScopedJavaLocalRef<' + return_type + '>'
        return_clause = 'return ' + return_type + '(env, ret);'
      else:
        return_clause = 'return ret;'
    values = {
        'JAVA_CLASS': called_by_native.java_class_name or self.class_name,
        'METHOD': called_by_native.name,
        'RETURN_TYPE': return_type,
        'RETURN_DECLARATION': return_declaration,
        'RETURN_CLAUSE': return_clause,
        'FIRST_PARAM_IN_DECLARATION': first_param_in_declaration,
        'PARAMS_IN_DECLARATION': params_in_declaration,
        'STATIC': 'Static' if called_by_native.static else '',
        'PRE_CALL': pre_call,
        'POST_CALL': post_call,
        'ENV_CALL': called_by_native.env_call[0],
        'FIRST_PARAM_IN_CALL': first_param_in_call,
        'PARAMS_IN_CALL': params_for_call,
        'METHOD_ID_VAR_NAME': called_by_native.method_id_var_name,
        'CHECK_EXCEPTION': check_exception,
    }
    values['FUNCTION_SIGNATURE'] = (
        function_signature_template.substitute(values))
    if called_by_native.system_class:
      values['FUNCTION_HEADER'] = (
          function_header_with_unused_template.substitute(values))
    else:
      values['FUNCTION_HEADER'] = function_header_template.substitute(values)
    return template.substitute(values)

  def GetKMethodArrayEntry(self, native):
    template = Template("""\
    { "native${NAME}", ${JNI_SIGNATURE}, reinterpret_cast<void*>(${NAME}) },""")
    values = {'NAME': native.name,
              'JNI_SIGNATURE': JniSignature(native.params, native.return_type,
                                            True)}
    return template.substitute(values)

  def GetUniqueClasses(self, origin):
    ret = {self.class_name: self.fully_qualified_class}
    for entry in origin:
      class_name = self.class_name
      jni_class_path = self.fully_qualified_class
      if entry.java_class_name:
        class_name = entry.java_class_name
        jni_class_path = self.fully_qualified_class + '$' + class_name
      ret[class_name] = jni_class_path
    return ret

  def GetClassPathDefinitions(self):
    """Returns the ClassPath constants."""
    ret = []
    template = Template("""\
const char k${JAVA_CLASS}ClassPath[] = "${JNI_CLASS_PATH}";""")
    native_classes = self.GetUniqueClasses(self.natives)
    called_by_native_classes = self.GetUniqueClasses(self.called_by_natives)
    all_classes = native_classes
    all_classes.update(called_by_native_classes)
    for clazz in all_classes:
      values = {
          'JAVA_CLASS': clazz,
          'JNI_CLASS_PATH': all_classes[clazz],
      }
      ret += [template.substitute(values)]
    ret += ''
    for clazz in called_by_native_classes:
      template = Template("""\
// Leaking this jclass as we cannot use LazyInstance from some threads.
jclass g_${JAVA_CLASS}_clazz = NULL;""")
      values = {
          'JAVA_CLASS': clazz,
      }
      ret += [template.substitute(values)]
    return '\n'.join(ret)

  def GetFindClasses(self):
    """Returns the imlementation of FindClass for all known classes."""
    template = Template("""\
  g_${JAVA_CLASS}_clazz = reinterpret_cast<jclass>(env->NewGlobalRef(
      base::android::GetUnscopedClass(env, k${JAVA_CLASS}ClassPath)));""")
    ret = []
    for clazz in self.GetUniqueClasses(self.called_by_natives):
      values = {'JAVA_CLASS': clazz}
      ret += [template.substitute(values)]
    return '\n'.join(ret)

  def GetMethodIDImpl(self, called_by_native):
    """Returns the implementation of GetMethodID."""
    template = Template("""\
  g_${JAVA_CLASS}_${METHOD_ID_VAR_NAME} =
      base::android::Get${STATIC}MethodID(
          env, g_${JAVA_CLASS}_clazz,
          "${NAME}",
          ${JNI_SIGNATURE});
""")
    values = {
        'JAVA_CLASS': called_by_native.java_class_name or self.class_name,
        'NAME': called_by_native.name,
        'METHOD_ID_VAR_NAME': called_by_native.method_id_var_name,
        'STATIC': 'Static' if called_by_native.static else '',
        'JNI_SIGNATURE': JniSignature(called_by_native.params,
                                      called_by_native.return_type,
                                      True)
    }
    return template.substitute(values)


def WrapOutput(output):
  ret = []
  for line in output.splitlines():
    if len(line) < 80:
      ret.append(line.rstrip())
    else:
      first_line_indent = ' ' * (len(line) - len(line.lstrip()))
      subsequent_indent =  first_line_indent + ' ' * 4
      if line.startswith('//'):
        subsequent_indent = '//' + subsequent_indent
      wrapper = textwrap.TextWrapper(width=80,
                                     subsequent_indent=subsequent_indent,
                                     break_long_words=False)
      ret += [wrapped.rstrip() for wrapped in wrapper.wrap(line)]
  ret += ['']
  return '\n'.join(ret)


def GenerateJNIHeaders(input_files, output_files, use_javap, namespace):
  for i in xrange(len(input_files)):
    try:
      if use_javap:
        jni_from_javap = JNIFromJavaP.CreateFromClass(input_files[i], namespace)
        output = jni_from_javap.GetContent()
      else:
        jni_from_java_source = JNIFromJavaSource.CreateFromFile(input_files[i])
        output = jni_from_java_source.GetContent()
    except ParseError, e:
      print e
      sys.exit(1)
    if output_files:
      header_name = output_files[i]
      if not os.path.exists(os.path.dirname(os.path.abspath(header_name))):
        os.makedirs(os.path.dirname(os.path.abspath(header_name)))
      if (not os.path.exists(header_name) or
          file(header_name).read() != output):
        print 'Generating ', header_name
        output_file = file(header_name, 'w')
        output_file.write(output)
        output_file.close()
    else:
      print output


def CheckFilenames(input_files, output_files):
  """Make sure the input and output have consistent names."""
  if len(input_files) != len(output_files):
    sys.exit('Input files length %d must match output length %d' %
             (len(input_files), len(output_files)))
  for i in xrange(len(input_files)):
    input_prefix = os.path.splitext(os.path.basename(input_files[i]))[0]
    output_prefix = os.path.splitext(os.path.basename(output_files[i]))[0]
    if input_prefix.lower() + 'jni' != output_prefix.replace('_', '').lower():
      sys.exit('\n'.join([
          '*** Error ***',
          'Input and output files have inconsistent names:',
          '\t' + os.path.basename(input_files[i]),
          '\t' + os.path.basename(output_files[i]),
          '',
          'Input "FooBar.java" must be converted to output "foo_bar_jni.h"',
          '',
      ]))


def main(argv):
  usage = """usage: %prog [OPTION] file1[ file2...] [output1[ output2...]]
This script will parse the given java source code extracting the native
declarations and print the header file to stdout (or a file).
See SampleForTests.java for more details.
  """
  option_parser = optparse.OptionParser(usage=usage)
  option_parser.add_option('-o', dest='output_files',
                           action='store_true',
                           default=False,
                           help='Saves the output to file(s) (the first half of'
                           ' args specify the java input files, the second'
                           ' half specify the header output files.')
  option_parser.add_option('-p', dest='javap_class',
                           action='store_true',
                           default=False,
                           help='Uses javap to extract the methods from a'
                           ' pre-compiled class. Input files should point'
                           ' to pre-compiled Java .class files.')
  option_parser.add_option('-n', dest='namespace',
                           help='Uses as a namespace in the generated header,'
                           ' instead of the javap class name.')
  options, args = option_parser.parse_args(argv)
  input_files = args[1:]
  output_files = []
  if options.output_files:
    output_files = input_files[len(input_files) / 2:]
    input_files = input_files[:len(input_files) / 2]
  CheckFilenames(input_files, output_files)
  GenerateJNIHeaders(input_files, output_files, options.javap_class,
                     options.namespace)


if __name__ == '__main__':
  sys.exit(main(sys.argv))
