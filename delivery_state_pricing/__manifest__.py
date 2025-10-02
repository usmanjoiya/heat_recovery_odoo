{
    'name': "Delivery State Pricing",
    'version': '1.0',
    'summary': "Adds state-based pricing rules to delivery methods.",
    'description': """
        This module extends the delivery price rule to allow for
        pricing based on the destination state.
    """,
    'author': "Shaheer",
    'category': 'Sales/Delivery',
    'depends': ['delivery', 'sale_management'],
    'data': [
        'views/delivery_price_rule_views.xml',
        'views/choose_delivery_carrier.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'AGPL-3',
}