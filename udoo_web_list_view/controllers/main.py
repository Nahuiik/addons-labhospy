# -*- coding: utf-8 -*-
# Copyright 2024 Jupetern

import json # Ensure json is imported
from lxml import etree

from odoo import http, _
from odoo.http import request


import logging
_logger = logging.getLogger(__name__)

class WebStudioController(http.Controller):
    @http.route('/udoo/restore_default_list_view', type='http', auth='user', csrf=False)
    def restore_default_list_view(self, **kwargs):
        # Manual JSON handling for robustness
        try:
            data = request.get_json_data()
        except ValueError:
            data = kwargs # Fallback to form data
            
        view_id = data.get('view_id')
        if view_id:
            view = request.env['ir.ui.view'].browse(int(view_id))
            self._set_mod_view(view, '')
        return request.make_json_response(True)

    @http.route('/udoo/edit_list_view', type='http', auth='user', csrf=False)
    def edit_list_view(self, **kwargs):
        # Manual JSON handling
        try:
            data = request.get_json_data()
        except ValueError:
            data = kwargs

        view_id = data.get('view_id')
        operations = data.get('operations')
        
        # Ensure operations is a dict (parse if string)
        if isinstance(operations, str):
            try:
                operations = json.loads(operations)
            except json.JSONDecodeError:
                operations = {}
        elif not operations:
            operations = {}

        if view_id:
            result = self._edit_list_view_logic(int(view_id), operations)
            return request.make_json_response(result or True)
        return request.make_json_response(False)
    
    def _edit_list_view_logic(self, view_id, operations=None):
        _logger.info("UDOO EDIT: View %s, Operations: %s", view_id, json.dumps(operations))
        def _remp_node(node):
            parent = node.getparent()
            parent.remove(node)
            # Use list(node) instead of getchildren() for Odoo 19 compatibility
            if not list(parent):
                parent.getparent().remove(parent)

        view = request.env['ir.ui.view'].browse(view_id)
        studio_view = self._get_mod_view(view) or self._create_mod_view(view, '<data/>')

        parser = etree.XMLParser(remove_blank_text=True)
        arch = etree.fromstring(studio_view.arch_db, parser=parser)

        EXP_EXPR = "//field[@name='%s' and not(@position)]"
        MOV_EXPR = "//field[@name='%s' and @position='move']"
        for field, data in sorted(operations.items(), key=lambda item: item[1]['order']):
            attrib_params = data.get('attrs') or {}
            ATT_EXPR = f"//xpath[@expr=\"//field[@name='{field}']\" and @position='attributes']"

            attribs = {}
            rem_attribs = {}
            for attr in attrib_params:
                tribs = attrib_params[attr]
                if tribs:
                    attribs[attr] = tribs
                elif attr == 'string':
                    rem_attribs[attr] = True
                elif attr == 'optional':
                    if not arch.xpath(EXP_EXPR % field):
                        rem_attribs[attr] = True
                    else:
                        attribs[attr] = ''  # unset optional

            if group_ids := data.get('group_ids'):
                ir_model_data = request.env['ir.model.data']
                group_xmlid = ir_model_data.search(
                    [('model', '=', 'res.groups'), ('res_id', 'in', group_ids)]
                )
                attribs['groups'] = ','.join(group_xmlid.mapped('complete_name'))

            xml_node = etree.Element('field', attribs)

            if prev_node := data.get('prev_node'):
                exist_moves = arch.xpath(MOV_EXPR % field)
                if exist_moves:
                    for node in exist_moves:
                        _remp_node(node)

                if isinstance(prev_node, dict) and 'id' in prev_node:
                    prev_node = prev_node['id']
                    xml_node = etree.Element('field', {'name': field, 'position': 'move'})
                else:
                    attribs = False  # Block attribute process

                exist_prevs = arch.xpath(EXP_EXPR % prev_node)
                if exist_prevs:
                    if exist_movs := arch.xpath(MOV_EXPR % prev_node):
                        exist_prevs = exist_movs
                    for node in exist_prevs:
                        parent = node.getparent()
                        parent.insert(parent.index(node) + 1, xml_node)
                        break
                else:
                    xpath_node = etree.SubElement(
                        arch,
                        'xpath',
                        {
                            'expr': f"//field[@name='{prev_node}']",
                            'position': 'after',
                        },
                    )
                    xpath_node.insert(0, xml_node)
            elif next_node := data.get('next_node'):
                exist_moves = arch.xpath(MOV_EXPR % field)
                if exist_moves:
                    for node in exist_moves:
                        _remp_node(node)

                if isinstance(next_node, dict) and 'id' in next_node:
                    next_node = next_node['id']
                    xml_node = etree.Element('field', {'name': field, 'position': 'move'})
                else:
                    attribs = False  # Block attribute process

                exist_nexts = arch.xpath(EXP_EXPR % next_node)
                if exist_nexts:
                    if exist_movs := arch.xpath(MOV_EXPR % next_node):
                        exist_nexts = exist_movs
                    for node in exist_nexts:
                        parent = node.getparent()
                        parent.insert(parent.index(node), xml_node)
                        break
                else:
                    xpath_node = etree.SubElement(
                        arch,
                        'xpath',
                        {
                            'expr': f"//field[@name='{next_node}']",
                            'position': 'before',
                        },
                    )
                    xpath_node.insert(0, xml_node)
            elif data.get('replace'):
                attribs = False  # Block attribute process

                exist_moves = arch.xpath(MOV_EXPR % field)
                if exist_moves:
                    for node in exist_moves:
                        _remp_node(node)

                exist_prevs = arch.xpath(EXP_EXPR % field)
                if exist_prevs:
                    for node in exist_prevs:
                        _remp_node(node)
                        break
                else:
                    etree.SubElement(
                        arch,
                        'xpath',
                        {
                            'expr': f"//field[@name='{field}']",
                            'position': 'replace',
                        },
                    )
                exist_att_xpaths = arch.xpath(ATT_EXPR)
                for node in exist_att_xpaths:
                    _remp_node(node)

            if attribs:
                xpath_node = None
                if exist_fields := arch.xpath(EXP_EXPR % field):
                    exist_field = exist_fields[0]
                    for attr in attribs:
                        if attr == 'name':
                            continue
                        exist_field.set(attr, attribs[attr])

                elif exist_att_xpaths := arch.xpath(ATT_EXPR):
                    xpath_node = exist_att_xpaths[0]
                else:
                    xpath_node = etree.SubElement(
                        arch,
                        'xpath',
                        {
                            'expr': f"//field[@name='{field}']",
                            'position': 'attributes',
                        },
                    )

                if xpath_node is not None:
                    for attr in attribs:
                        if attr == 'name':
                            continue
                        if exist_attrs := xpath_node.xpath(f"attribute[@name='{attr}']"):
                            exist_attrs[0].text = attribs[attr]
                        else:
                            xml_node = etree.Element('attribute', {'name': attr})
                            xml_node.text = attribs[attr]
                            xpath_node.insert(0, xml_node)

            for attr in rem_attribs:
                if exist_attrs := arch.xpath(f"//attribute[@name='{attr}']"):
                    for node in exist_attrs:
                        _remp_node(node)
                        break

        new_arch = etree.tostring(arch, encoding='unicode', pretty_print=True)
        _logger.info("UDOO EDIT: New Arch: %s", new_arch)
        self._set_mod_view(view, new_arch)

    def _generate_mod_name(self, view):
        return 'Udoo: %s customization' % (view.name)

    def _get_mod_view(self, view):
        domain = [('inherit_id', '=', view.id), ('name', '=', self._generate_mod_name(view))]
        return view.search(domain, order='priority desc, name desc, id desc', limit=1)

    def _set_mod_view(self, view, arch):
        mod_view = self._get_mod_view(view)
        if mod_view and len(arch):
            mod_view.arch_db = arch
        elif mod_view:
            mod_view.unlink()
        elif len(arch):
            self._create_mod_view(view, arch)

    def _create_mod_view(self, view, arch):
        # To ensure our customization is applied last, we need to adjust the view priorities.
        # In Udoo, users interact with the final view after all inheritance layers are applied.
        # Therefore, any changes they make affect this final result. To reflect their changes correctly,
        # our customization must be the last one executed.
        priority = max(view.inherit_children_ids.mapped('priority'), default=0) * 9
        default_prio = view._fields['priority'].default(view)
        if priority <= default_prio:
            priority = 98
        return request.env['ir.ui.view'].create(
            {
                'type': view.type,
                'model': view.model,
                'inherit_id': view.id,
                'mode': 'extension',
                'priority': priority,
                'arch': arch,
                'name': self._generate_mod_name(view),
            }
        )
