# -*- coding: utf-8 -*-
# Copyright 2024 Jupetern

{
    'name': 'Omux Column Manager',
    'category': 'Tools',
    'summary': 'Inline list editing enables you to update records quickly by changing data directly in a record\'s row on the list page. Manage the fields that are displayed as columns in the list view. The available options vary, drag and drop to reorder list items, effortlessly rearrange your list items. Make some fileds in list not sortable. Reorderable drag-and-drop, inline editing, list control, cell editing, custom list view, dynamic list view, dynamic tree view, advanced list view, ultimate list, dragging and dropping, change titles, specific column, hide column, show column, rename column, reorder column, rearrange column, manage columns, column manager, list view manager.',
    'version': '1.0.7',
    'license': 'OPL-1',
    'author': 'Sveltware Solutions',
    'website': 'https://www.linkedin.com/in/sveltware',
    'images': ['static/description/banner.png'],
    'depends': ['base', 'web'],
    'data': [
        'security/groups.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Load manager.js first (contains ColumnManager export)
            'udoo_web_list_view/static/src/mod/manager.js',
            'udoo_web_list_view/static/src/mod/manager.xml',
            'udoo_web_list_view/static/src/mod/manager.scss',
            # Then load list renderer and controller
            (
                'after',
                'web/static/src/views/list/list_renderer.xml',
                'udoo_web_list_view/static/src/list/renderer.xml',
            ),
            (
                'after',
                'web/static/src/views/list/list_controller.xml',
                'udoo_web_list_view/static/src/list/controller.xml',
            ),
            'udoo_web_list_view/static/src/list/controller.js',
            'udoo_web_list_view/static/src/list/renderer.js',
            'udoo_web_list_view/static/src/list/controller.scss',
        ],
    },
    'price':120,
    'currency': 'USD',
}
