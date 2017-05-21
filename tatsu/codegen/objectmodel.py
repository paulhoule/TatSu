# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from datetime import datetime
from collections import namedtuple as NT  # noqa: N812

from tatsu.util import (
    compress_seq,
    indent,
    re,
    safe_name,
)
from tatsu.objectmodel import Node
from tatsu.objectmodel import BASE_CLASS_TOKEN
from tatsu.exceptions import CodegenError
from tatsu.rendering import Renderer
from tatsu.codegen.cgbase import ModelRenderer, CodeGenerator


NODE_NAME_PATTERN = '(?!\d)\w+(' + BASE_CLASS_TOKEN + '(?!\d)\w+)*'


_TypeSpec = NT('TypeSpec', ['class_name', 'base'])


def codegen(model):
    return ObjectModelCodeGenerator().render(model)


def _get_node_class_name(rule):
    if not rule.params:
        return None

    typespec = rule.params[0]
    if not re.match(NODE_NAME_PATTERN, typespec):
        return None
    if not typespec[0].isupper():
        return None
    return typespec


def _typespec(rule, default_base=True):
    if not _get_node_class_name(rule):
        return _TypeSpec(None, None)

    spec = rule.params[0].split(BASE_CLASS_TOKEN)
    class_name = safe_name(spec[0])
    base = None
    bases = spec[1:]
    if bases:
        base = safe_name(bases[0])
    elif default_base:
        base = 'ModelBase'
    return _TypeSpec(class_name, base)


class BaseClassRenderer(Renderer):
    def __init__(self, class_name):
        self.class_name = class_name

    template = '''
        class {class_name}(ModelBase):
            pass
        '''


class ObjectModelCodeGenerator(CodeGenerator):
    def _find_renderer_class(self, item):
        if not isinstance(item, Node):
            return None

        name = item.__class__.__name__
        renderer = globals().get(name, None)
        if not renderer or not issubclass(renderer, ModelRenderer):
            raise CodegenError('Renderer for %s not found' % name)
        return renderer


class Rule(ModelRenderer):
    def render_fields(self, fields):
        defs = [safe_name(d) for d, l in compress_seq(self.defines())]
        defs = list(sorted(set(defs)))

        kwargs = '\n'.join('%s = None' % d for d in defs)
        if kwargs:
            kwargs = indent(kwargs)
        else:
            kwargs = indent('pass')

        spec = _typespec(self.node)

        fields.update(
            class_name=spec.class_name,
            base=spec.base,
            kwargs=kwargs,
        )

    template = '''
        class {class_name}({base}):
        {kwargs}
        '''


class Grammar(ModelRenderer):
    def render_fields(self, fields):
        node_class_names = set()

        bases = []
        model_rules = []
        for rule in self.node.rules:
            spec = _typespec(rule, False)
            if not spec.class_name:
                continue
            if spec.class_name not in node_class_names:
                model_rules.append(rule)
            if spec.base and spec.base not in node_class_names:
                bases.append(spec.base)
            node_class_names.add(spec.class_name)
            node_class_names.add(spec.base)

        base_class_declarations = [
            BaseClassRenderer(base).render()
            for base in bases
        ]

        model_class_declarations = [
            self.get_renderer(rule).render()
            for rule in model_rules
        ]

        base_class_declarations = '\n\n\n'.join(base_class_declarations)
        if base_class_declarations:
            base_class_declarations += '\n\n'
        model_class_declarations = '\n\n\n'.join(model_class_declarations)

        version = datetime.now().strftime('%Y.%m.%d.%H')

        fields.update(
            base_class_declarations=base_class_declarations,
            model_class_declarations=model_class_declarations,
            version=version,
        )

    template = '''\
                #!/usr/bin/env python
                # -*- coding: utf-8 -*-

                # CAVEAT UTILITOR
                #
                # This file was automatically generated by TatSu.
                #
                #    https://pypi.python.org/pypi/tatsu/
                #
                # Any changes you make to it will be overwritten the next time
                # the file is generated.

                from __future__ import print_function, division, absolute_import, unicode_literals

                from tatsu.objectmodel import Node
                from tatsu.semantics import ModelBuilderSemantics


                class {name}ModelBuilderSemantics(ModelBuilderSemantics):
                    def __init__(self):
                        types = [
                            t for t in globals().values()
                            if type(t) is type and issubclass(t, ModelBase)
                        ]
                        super({name}ModelBuilderSemantics, self).__init__(types=types)


                class ModelBase(Node):
                    pass


                {base_class_declarations}{model_class_declarations}
                '''
