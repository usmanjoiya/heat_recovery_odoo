{
    'name': "Measurement Module",
    'version': '1.0',
    'summary': "Different measurement scenerio for the home for heat recovery.",
    'description': """
    This module extend different measurement scenerio
    """,
    'author': "Shaheer",
    'category': 'Sales',
    'depends': ['base','sale','mail','contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/inh_sale_order.xml',
        'views/res_state_country.xml',
        'views/res_partner.xml',
        'views/dwelling_ventilation_views.xml',
        'views/inh_prod_temp_view.xml',
        'views/inh_prod_prod_view.xml',
        'views/alrightness_pricess_views.xml',
        'views/placement_config.xml',
        'views/floor_conf_view.xml',
        'data/prod_attrs_name.xml',
        'reports/report_heat_recovery.xml',
        'reports/custom_temp_action_format.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'measurement/static/src/js/product_configurator_dialog_inherit.js',
            'measurement/static/src/js/inh_sale_prod_field.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'AGPL-3',
}