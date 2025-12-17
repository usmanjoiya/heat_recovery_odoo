# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
{
	'name':'Quickbooks Online Connector',
	'version': '1.0.0',
	'author': 'Webkul Software Pvt. Ltd.',
	"license":  "Other proprietary",
	'summary': 'To Export All The Data Like Products, Customers, Orders, Purchase Order etc from Odoo to quickbooks online and Vice Versa quickbook bridge odoo quickbook connector quickbook odoo connector odoo quickbook online quickbooks bridge odoo quickbook connector quickbooks odoo connector odoo quickbooks online quick book connector quickbook accounting',
	'description': """ 
    Quickbooks Online Connector
	----------------------------
    To Export All The Data Like Products, Customers, Orders, Purchase Order etc from Odoo to quickbooks online and Vice Versa',
    
    For any doubt or query email us at support@webkul.com or raise a Ticket on http://webkul.com/ticket/
	""",
	'website': 'https://store.webkul.com/odoo-quickbooks-online-connector.html',
	'live_test_url':'https://odoodemo.webkul.com/demo_feedback?module=quickbook_online_connector',
	'images': [],
	'depends': ['sale_stock', 'purchase'],
	'category': 'Accounting',
	'sequence': 1,
	'data': [
		'data/cron.xml',
		'data/account_sequence.xml',
        'security/quickbookonline_security.xml',
        'security/ir.model.access.csv',
        'views/mapping/quickbookonline_partner.xml',
        'views/mapping/quickbookonline_account.xml',
		'views/mapping/quickbookonline_category.xml',
		'views/mapping/quickbookonline_tax.xml',
		'views/mapping/quickbookonline_product.xml',
		'views/mapping/quickbookonline_payment_term_map.xml',
		'views/mapping/quickbookonline_payment_method_map.xml',
        'views/mapping/quickbookonline_order.xml',
        'views/mapping/quickbookonline_invoice.xml',
        'views/mapping/quickbookonline_payment.xml',
		'views/mapping/quickbookonline_purchase_order.xml',
        'views/quickbook/quickbookonline_instance.xml',
        'views/mapping/quickbookonline_bill.xml',
		'views/core/order.xml',
		'views/core/purchase_order.xml',
		'views/core/invoice.xml',
		'views/manual_export/manual_export.xml',
		'views/quickbook/quickbookonline_dashboard.xml',
		'views/quickbook/quickbookonline_synchronization.xml',
        'views/quickbook/quickbookonline_tax_code.xml',
        'views/quickbook/quickbookonline_payment_term.xml',
        'views/quickbook/quickbookonline_payment_method.xml',
        'views/quickbook/quickbookonline_menus.xml',
		'wizard/quickbookonline_message_wizard.xml',
		'wizard/quickbookonline_bulk_synchronization.xml',
		'wizard/quickbookonline_manual_synchronization.xml',
		],

	'assets': {
        'web.assets_backend': [
			'/quickbook_online_connector/static/src/scss/quickbook_kanban.scss',
			'/quickbook_online_connector/static/src/scss/quickbook_dashboard.scss',
			'/quickbook_online_connector/static/src/js/quickbook_dashboard.js',
   			'/quickbook_online_connector/static/src/xml/quickbookonline_dashboard.xml'
        ],
        'web.assets_qweb': [
			'/quickbook_online_connector/static/src/xml/quickbookonline_dashboard.xml'
        ],
    },
	"images":  ['static/description/banner.png'],
	'installable': True,
	'application': True,
	'auto_install': False,
	"price":169,
  	"currency":"USD",
	'pre_init_hook': 'pre_init_check',
}
