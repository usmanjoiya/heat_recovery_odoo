{
    'name': "portal_extension",

    'summary': "Allow portal User to upload document",

    'description': """
                   Now the portal user can also upload the Document by Clicking New Button on documents page
                       """,

    'author': "MountSol",
    'website': "https://www.mountsol.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'documents'],

    # always loaded
    'data': [

    ],
    'assets': {
        'web.assets_backend': [
            'portal_extension/static/src/js/document_upload.js',
        ],
    },
}
