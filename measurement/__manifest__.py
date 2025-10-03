{
    'name': "Measurement Module",
    'version': '1.0',
    'summary': "Different measurement scenerio for the home for heat recovery.",
    'description': """
    This module extend different measurement scenerio
    """,
    'author': "Shaheer",
    'category': 'Sales',
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/inh_sale_order.xml',
        'views/dwelling_ventilation_views.xml',
        'views/inh_prod_temp_view.xml',
        'reports/report_heat_recovery.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'AGPL-3',
}