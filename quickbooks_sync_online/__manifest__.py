# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    'name': 'Odoo QuickBooks Online Connector PRO',
    'summary': '''Seamlessly integrate your Odoo ERP with QuickBooks Online (QBO) for efficient financial management.
Synchronize invoices, bills, payments, customers, vendors, and products between the two systems.
Automate data transfer to eliminate manual entry and reduce errors.

This connector maps taxes, accounts, payment terms, and departments between Odoo and QBO.
Export invoices and bills from Odoo to QBO. Import and export customer/vendor payments, partners, and products.
You can also send payment links directly from Odoo to your customers.

Choose between manual and automatic synchronization to fit your business needs.

Keywords: QuickBooks Online, QuickBooks Odoo Connector, QuickBooks Integration, Odoo QuickBooks Connector,
Sync QuickBooks with Odoo, QuickBooks Online Integration, QuickBooks Invoice Export, QuickBooks Payment Import,
QuickBooks Payment Export, QuickBooks Partner Sync, QuickBooks Customer Sync, QuickBooks Product Sync,
Intuit Odoo Connector, Connect QuickBooks to Odoo, Automatic QuickBooks Sync, Manual QuickBooks Sync,
QuickBooks Online Payment Links''',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'support': 'support@ventor.tech',
    'license': 'OPL-1',
    'live_test_url': 'https://ventor.tech/contact-us/',
    'price': 299.00,
    'currency': 'EUR',
    'depends': [
        'sale_management',
        'sale_purchase',
        'account',
        'stock_dropshipping',
        'queue_job',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        # Wizard views
        'wizard/qbo_help_wizard_views.xml',
        # Mapping views
        'views/mapping/qbo_map_mixin_views.xml',
        'views/mapping/qbo_map_account_move_views.xml',
        'views/mapping/qbo_map_partner_views.xml',
        'views/mapping/qbo_map_product_views.xml',
        'views/mapping/qbo_map_account_views.xml',
        'views/mapping/qbo_map_tax_views.xml',
        'views/mapping/qbo_map_taxcode_views.xml',
        'views/mapping/qbo_map_term_views.xml',
        'views/mapping/qbo_map_payment_method_views.xml',
        'views/mapping/qbo_map_payment_views.xml',
        'views/mapping/qbo_map_sale_order_views.xml',
        'views/mapping/qbo_map_department_views.xml',
        # Standard views
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/product_views.xml',
        'views/product_category_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/sale_order_views.xml',
        'views/stock_warehouse_views.xml',
        'views/queue_job_views.xml',
        'views/ir_menu.xml',
        # Data
        'data/ir_cron_data.xml',
        'data/res_company_data.xml',
        'data/mail_template_data.xml',
        # 'data/queue_job_data.xml',
    ],
    'external_dependencies': {
        'python': [
            'quickbooks',
            'pycountry',
        ],
    },
    'images': [
        "static/description/images/banner.gif",
    ],
    "cloc_exclude": [
        "**/*",
    ],
    'installable': True,
    'application': True,
}
