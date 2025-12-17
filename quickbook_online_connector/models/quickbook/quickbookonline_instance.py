# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, api, fields, models
from odoo.exceptions import UserError
import logging
import requests
import base64
import json
_logger = logging.getLogger(__name__)
from urllib.parse import urlencode

limit = [("1", "1"),
    ("10", "10"),
    ("50", "50"),
    ("100", "100"),
    ("200", "200"),
    ("300", "300"),
    ("500", "500"),
    ("1000", "1000"),
    ("2000", "2000"),
		]

class QuickBookOnlineInstance(models.Model):
	_name = 'quickbookonline.instance'
	_inherit = ['mail.thread']
	_description = 'Model For QuickBook Online Odoo Connection'

	def _default_category_name(self):
		category_id = self.env['product.category'].search([], limit=1).id
		if category_id:
			return category_id
		return False
	
	def _default_warehouse_name(self):
		warehouse_id = self.env['stock.warehouse'].search([], limit=1).id
		if warehouse_id:
			return warehouse_id
		return False
	
	def _default_pricelist_name(self):
		pricelist = self.env['product.pricelist'].search([], limit=1).id
		if pricelist:
			return pricelist
		return False


	name = fields.Char(string = 'Instance Name', required = True)
	
	client_id = fields.Char(string = 'Client id',required = True, help="Paste Client ID from quickbook apps Keys & credentials section")

	client_key = fields.Char(string = 'Client key', required = True, help="Paste Client Secret from quickbook apps Keys & credentials section")

	redirect_url = fields.Char(string='Redirect Url', default=lambda self: self.sudo().get_base_url() +'/quickbook_online_connector', required = True, help='eg: https://your-odoo-url/quickbook_online_connector')

	refresh_token = fields.Char(string='Refresh Toekn')

	access_token = fields.Char(string='Access Toekn')

	realmId = fields.Char(string = 'Realm Id')
	qbo_company_name = fields.Char(string='Company Name')
	
	active = fields.Boolean(string = 'Active', 
	default = True)

	connection_status = fields.Boolean(
		string = 'Connection Status',
		default = False
		)
	
	environment = fields.Selection(
		selection = [('sandbox','SandBox'),
		('production','Production')], 
		string='Environment',
		default = 'sandbox',
		required = True
	)

	default_import_limit = [
	("10", "10"),
    ("50", "50"),
    ("100", "100"),
    ("200", "200"),
    ("300", "300"),
    ("500", "500"),
    ("1000", "1000"),
    ("all", "All")
		]

	# Default settings
	default_category_id = fields.Many2one('product.category',string = 'Default Product Category',default = lambda self: self._default_category_name())
	default_warehouse_id = fields.Many2one('stock.warehouse',string = 'Default Stock Warehouse',default = lambda self: self._default_warehouse_name())
	default_pricelist_id = fields.Many2one('product.pricelist',string = 'Default Pricelist Id',default = lambda self: self._default_pricelist_name())
	default_sales_team = fields.Many2one('crm.team', string='Default Sales Team',help="""Default Sales Team Used In Sale Order.""")
	default_sales_user = fields.Many2one('res.users',string='Default Sales User',help="""Default Sales Person Used In Sale Order.""")
	automate_confirm_sale_order = fields.Boolean('Automatic Confirm Sale Order')
	automate_confirm_purchase_order = fields.Boolean('Automatic Confirm Purchase Order')
	discount_product_id = fields.Many2one('product.product', string='Discount Product')
	company_id = fields.Many2one(related='default_warehouse_id.company_id',
		string='Company Id')
	# category_product_id = fields.Many2one('product.product', string = 'Purchase Category Product Id')

 	# New Update: improvements
	location_id = fields.Many2one(related="default_warehouse_id.lot_stock_id", string="Location ID")
	auto_sync_stock = fields.Boolean('Auto Stock Sync')
	avoid_duplicity = fields.Boolean('Avoid Duplicity')

	# Account Settings
	quickbook_income_account = fields.Many2one('account.account',string = 'Quickbook Income Account')
	quickbook_asset_account = fields.Many2one('account.account', string = 'Quickbook Asset Account')
	quickbook_expense_account = fields.Many2one('account.account', string = 'Quickbook Expense Account')
	quickbook_account_payble_account = fields.Many2one('account.account', string = 'Quickbook Purchase Account Payble')
	quickbook_account_tax = fields.Many2one('account.tax')
	quickbook_account_code = fields.Many2one('quickbookonline.tax.code',domain = [('tax_group','=',False)])
	quickbook_account_tax_code = fields.Many2one('quickbookonline.tax.code',domain = [('tax_group','=',True)])
	quickbook_account_purchase_tax_code = fields.Many2one('quickbookonline.tax.code',domain = [('tax_group','=',True)])
	quickbook_default_order_line_tax = fields.Many2one('quickbookonline.tax.code', string = "Tax On No Tax OrderLine",domain = [('tax_group','=',False)])

	apply_tax_after_discount = fields.Boolean(string='Apply Tax After Discount', default=True)
	#Time Settings
	importCategoryTime = fields.Char('Import Category Time')
	importProductTime = fields.Char('Import Product Time')
	importCustomerTime = fields.Char('Import Customer Time')
	importOrderTime = fields.Char('Import Order Time')
	importVendorTime = fields.Char('Import Vendor Time')
	importPurchaseOrderTime = fields.Char('Import Purchase Order Time')
	importInvoiceTime = fields.Char('Import Invoice Time')
	importBillTime = fields.Char('Import Bill Time')
	importPaymentTime = fields.Char('Import Payment Time')


	# Bulk Import Limit For Cron
	importCategoryLimit = fields.Selection(selection = limit, default='10')
	importOrderLimit = fields.Selection(selection = limit, default='10')
	importProductLimit = fields.Selection(selection = limit, default='10')
	importInvoiceLimit = fields.Selection(selection = limit, default='10')
	importBillLimit = fields.Selection(selection = limit, default='10')
	importCustomerLimit = fields.Selection(selection = limit, default='10')
	importPaymentLimit = fields.Selection(selection = limit, default='10')
	importVendorLimit = fields.Selection(selection = limit, default='10')
	importPurchaseOrderLimit = fields.Selection(selection = limit, default='10')

	# Quickbook Defaul Import Limit
	importTaxCodeLimit = fields.Selection(selection = default_import_limit, default="100")
	importSaleTaxLimit = fields.Selection(selection = default_import_limit, default="100")
	importPaymentTermLimit = fields.Selection(selection = default_import_limit, default="100")
	importPaymentMethodLimit = fields.Selection(selection = default_import_limit, default="100")


	# Import For Cron
	category_import_cron = fields.Boolean('Import Category')
	product_import_cron = fields.Boolean('Import Product')
	partner_import_cron = fields.Boolean('Import Partner')
	order_import_cron = fields.Boolean('Import Order')
	invoice_import_cron = fields.Boolean('Import Invoice')
	bill_import_cron = fields.Boolean('Import Bill')
	payment_import_cron = fields.Boolean('Import Payment')
	vendor_import_cron = fields.Boolean('Import Vendor')
	purchase_order_import_cron = fields.Boolean('Import Purchase Order')


	# Export For Cron
	category_export_cron = fields.Boolean('Export Category')
	product_export_cron = fields.Boolean('Export Product')
	partner_export_cron = fields.Boolean('Export Partner')
	order_export_cron = fields.Boolean('Export Order')
	invoice_export_cron = fields.Boolean('Export Invoice')
	bill_export_cron = fields.Boolean('Export Bill')
	payment_export_cron = fields.Boolean('Export Payment')
	vendor_export_cron = fields.Boolean('Export Vendor')
	purchase_order_export_cron = fields.Boolean('Export Purchase Order')

	@api.model_create_multi
	def create(self,vals_list):
		for vals in vals_list:
			if vals.get('api_url',False):
				if not vals['api_url'].endswith('/'):
					vals['api_url'] += '/'
			if not self.env.context.get('multi_instance',False) and vals.get('active',False):
				if(self.search([('active','=',True)])):
					raise UserError('Only One Active Connection Allowed')
		return super().create(vals_list)

	def write(self,vals):
		if not self.env.context.get('multi_instance',False) and vals.get('active',False):
			if(self.search([('active','=',True)])):
				raise UserError('Only One Active Connection Allowed')
		return super().write(vals)
	
	def open_cron_view(self):
		return {
            "type": "ir.actions.act_window",
            "res_model": "ir.cron",
            "domain": [('model_id', '=', self.env['ir.model'].search([('model','=','quickbookonline.synchronization')]).id)],
            "name": "QBO: Scheduled Actions",
            "context": {"create": False, 'search_default_all': 1},
            'view_mode': 'list,form',
        }
 
	def disconnect_connection(self):
		self.write({
			'connection_status': False,
		})

	def get_company_info(self, access_token, realmId):
		qbo_company_name = False
		try:
			headers = {
					'Content-type':'text/plain',
					'Accept': 'application/json',
					'Authorization':'Bearer %s'%access_token
				}
			url = 'https://sandbox-quickbooks.api.intuit.com/v3/company/%s/'%realmId if self.environment=='sandbox' else 'https://quickbooks.api.intuit.com/v3/company/%s/'%realmId
			url += f'companyinfo/{realmId}/?minorversion=75'
			response = requests.get(url, headers=headers)
			if response.ok or response.status_code in [200, 201]:
				res = response.json()
				if res.get('CompanyInfo'):
					qbo_company_name = res.get('CompanyInfo').get('CompanyName')
		except Exception as e:
			_logger.error('Error in getting company info: %r', e, exc_info=True)
		self.qbo_company_name = qbo_company_name

	def test_connection(self):
		msg_env = self.env['quickbookonline.message.wizard']
		base_url = 'https://appcenter.intuit.com/connect/oauth2'
		params = {
			'client_id':self.client_id,
			'scope':'com.intuit.quickbooks.accounting',
			'redirect_uri':self.redirect_url,
			'response_type':'code',
			'state':'123456:122222'
		}
		url = '?'.join([base_url,urlencode(params)])
		response = requests.post(url)
		if response.status_code in [200,201]:
			return {
       			'name': 'Go to Quickbook Online',
				'res_model': 'ir.actions.act_url',
				'type'     : 'ir.actions.act_url',
				'target'   : 'self',
				'url'      : response.url,
			   }
		else:
			self.connection_status = False
			message = """<p class="text-danger">Issue: Error While Getting Authorization Code(Url Not Found)</p>"""
		return msg_env.generate_message(message)
	

	def create_online_connection(self, args):
		code = args['code']
		realmId = args['realmId']
		token_url = 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
		usrPass = self.client_id + ':' +self.client_key
		auth_header = usrPass.encode('utf-8')
		Authorization = ' '.join(['Basic', base64.b64encode(auth_header).decode('utf-8')])
		headers = {
			'Content-Type': 'application/x-www-form-urlencoded',
			'Authorization' : Authorization
		}
		data = urlencode({
			'grant_type':'authorization_code',
			'code':code,
			'redirect_uri':self.redirect_url
		})
		response = requests.post(token_url,data, headers = headers)
		if response.status_code in [200,201]:
			res = response.json()
			refresh_token = res.get('refresh_token','')
			access_token = res.get('access_token','')
			vals = {
				'connection_status':True,
				'realmId':realmId,
				'refresh_token':refresh_token,
				'access_token':access_token
			}
			self.get_company_info(access_token, realmId)
			return self.write(vals)
		return False
	
	def get_tax_data(self):
		self.ensure_one()
		if not self.env['quickbookonline.tax'].search([('instance_id','=',self.id)]):
			self.get_sale_tax()
		connection = self._create_quickbook_connection(self.id)
		url = connection.get('url',False)
		self = self.with_context(instance_id= self.id)
		access_token = connection.get('access_token',False)
		message = ''
		message_wizard = self.env['quickbookonline.message.wizard']
		tax_env = self.env['quickbookonline.tax.code'].with_company(connection.get('company_id'))
		client = self.env['call.quickbook.api']
		try:
			headers = {
				'Content-type':'text/plain',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			query = 'select * From TaxCode Orderby Id MAXRESULTS 500'
			response = client.get_query_object(url, query, headers,75)
			dic = response.get('TaxCode',[])
			for i in dic:
				_logger.info("==================================i=%r",i)
				quickbook_id = i.get('Id')
				name =  i.get('Name')
				is_taxable =  i.get('Taxable')
				tax_group = i.get('TaxGroup')
				vals = {
					'quickbook_id':quickbook_id,
					'name':name,
					'is_taxable':is_taxable,
					'instance_id':self.id,
					'tax_group':tax_group
				}
				tax_rates = i.get('SalesTaxRateList',{}).get('TaxRateDetail',[])
				tax_ids = []
				tax_mapping = self.env['quickbookonline.tax']
				for tax_rate in tax_rates:
					quickbook_tax_id = tax_rate['TaxRateRef']['value']
					mapping = tax_mapping.search([('quickbook_id','=',quickbook_tax_id),
					('instance_id','=',self.id)],limit=1)
					if mapping:
						tax_ids.append(mapping.odoo_id)
				if tax_ids:
					vals['tax_ids'] = [(6,0,tax_ids)]
				tax_id = tax_env.search([('quickbook_id','=',quickbook_id),('instance_id','=',self.id)],limit=1)
				if tax_id:
					tax_id.write(vals)
				else:
					tax_env.create(vals)
			message+= '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>Message: SucessFully Imported All The Tax Codes</div>'
		except Exception as e:
			message+= '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message_wizard.generate_message(message)
	
	def get_payment_methods(self):
		self.ensure_one()
		connection = self._create_quickbook_connection(self.id)
		url = connection.get('url',False)
		self = self.with_context(instance_id= self.id)
		access_token = connection.get('access_token',False)
		message = ''
		message_wizard = self.env['quickbookonline.message.wizard']
		tax_env = self.env['quickbookonline.payment.method'].with_company(connection.get('company_id'))
		client = self.env['call.quickbook.api']
		try:
			headers = {
				'Content-type':'text/plain',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			query = 'select * From PaymentMethod Orderby Id MAXRESULTS 500'
			response = client.get_query_object(url, query, headers,75)
			dic = response.get('PaymentMethod',[])
			for i in dic:
				quickbook_id = i.get('Id')
				name =  i.get('Name')
				payment_type =  i.get('Type')
				vals = {
					'quickbook_id':quickbook_id,
					'name':name,
					'payment_type':payment_type,
					'instance_id':self.id
				}
				tax_id = tax_env.search([('quickbook_id','=',quickbook_id),('instance_id','=',self.id)],limit=1)
				if tax_id:
					tax_id.write(vals)
				else:
					tax_env.create(vals)
			message+= '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>Message: SucessFully Imported All The Payment Methods</div>'
		except Exception as e:
			message+= '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message_wizard.generate_message(message)
	

	def get_payment_terms(self):
		self.ensure_one()
		connection = self._create_quickbook_connection(self.id)
		url = connection.get('url',False)
		self = self.with_context(instance_id= self.id)
		access_token = connection.get('access_token',False)
		message = ''
		message_wizard = self.env['quickbookonline.message.wizard']
		tax_env = self.env['quickbookonline.payment.term'].with_company(connection.get('company_id'))
		client = self.env['call.quickbook.api']
		try:
			headers = {
				'Content-type':'text/plain',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			query = 'select * From Term Orderby Id MAXRESULTS 500'
			response = client.get_query_object(url, query, headers, 75)
			dic = response.get('Term',[])
			for i in dic:
				quickbook_id = i.get('Id')
				name =  i.get('Name')
				vals = {
					'quickbook_id':quickbook_id,
					'name':name,
					'instance_id':self.id
				}
				tax_id = tax_env.search([('quickbook_id','=',quickbook_id),('instance_id','=',self.id)],limit=1)
				if tax_id:
					tax_id.write(vals)
				else:
					tax_env.create(vals)
			message+= '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>Message: SucessFully Imported All The Payment Terms</div>'
		except Exception as e:
			message+= '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message_wizard.generate_message(message)

	def get_sale_tax(self):
		self.ensure_one()
		connection = self._create_quickbook_connection(self.id)
		url = connection.get('url',False)
		self = self.with_context(instance_id= self.id)
		access_token = connection.get('access_token',False)
		message = ''
		message_wizard = self.env['quickbookonline.message.wizard']
		tax_env = self.env['quickbookonline.tax']
		client = self.env['call.quickbook.api']
		account_tax = self.env['account.tax'].with_company(connection.get('company_id'))
		try:
			headers = {
				'Content-type':'text/plain',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			query = 'select * From TaxRate Orderby Id MAXRESULTS 500'
			response = client.get_query_object(url, query, headers,75)
			dic = response.get('TaxRate',[])
			for i in dic:
				quickbook_id = i.get('Id')
				name =  i.get('Name')
				rate = i.get('RateValue')
				_logger.info("++++++++++Logger for Sales Taxes+++++++++++:%r",rate)
				if rate:
					vals = {
							'name':name,
							'type_tax_use':'sale',
							'amount':float(rate),
						}
					tax_id = account_tax.search([('name','=',name)],limit=1)
					if tax_id:
						tax_id.write(vals)
					else:
						tax_id = account_tax.create(vals)
					if tax_id:
						if not tax_env.search([('quickbook_id','=',quickbook_id),('instance_id','=',self.id)]):
							tax_env.create({
								'quickbook_id':quickbook_id,
								'name':tax_id.id,
								'odoo_id':tax_id.id,
								'instance_id':self.id,
								'created_by':'import'
							})
			message+= '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>Message: SucessFully Imported All The Sales Taxes</div>'
		except Exception as e:
			message+= '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message_wizard.generate_message(message)

	def _create_quickbook_connection(self, instance_id, refresh_token=False):
		instance = self.browse(instance_id)
		client_id = instance.client_id
		client_key = instance.client_key
		access_token = instance.access_token
		realmId = instance.realmId
		apply_tax_after_discount = instance.apply_tax_after_discount
		#Default Configuration To Create Records In Odoo
		default_category_id = instance.default_category_id
		default_warehouse_id = instance.default_warehouse_id
		company_id = instance.company_id
		default_pricelist_id = instance.default_pricelist_id
		default_sales_team = instance.default_sales_team
		default_sales_user = instance.default_sales_user
		automate_confirm_sale_order = instance.automate_confirm_sale_order
		automate_confirm_purchase_order = instance.automate_confirm_purchase_order

		# Account in get connection info
		quickbook_income_account = instance.quickbook_income_account
		quickbook_asset_account = instance.quickbook_asset_account
		quickbook_expense_account = instance.quickbook_expense_account
		quickbook_account_tax = instance.quickbook_account_tax
		quickbook_account_code = instance.quickbook_account_code
		quickbook_account_tax_code = instance.quickbook_account_tax_code
		quickbook_account_purchase_tax_code = instance.quickbook_account_purchase_tax_code
		quickbook_account_payble_account = instance.quickbook_account_payble_account
		quickbook_default_order_line_tax = instance.quickbook_default_order_line_tax

		#Time Info
		importCategoryTime = instance.importCategoryTime
		importProductTime = instance.importProductTime
		importCustomerTime = instance.importCustomerTime
		importOrderTime = instance.importOrderTime
		importPurchaseOrderTime = instance.importPurchaseOrderTime
		importVendorTime = instance.importVendorTime
		importInvoiceTime = instance.importInvoiceTime
		importBillTime = instance.importBillTime
		importPaymentTime = instance.importPaymentTime
		avoid_duplicity = instance.avoid_duplicity
		if refresh_token:
			url = 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
			usrPass = client_id + ':' + client_key
			auth_header = usrPass.encode('utf-8')
			Authorization = ' '.join(['Basic', base64.b64encode(auth_header).decode('utf-8')])
			headers = {
				'Content-Type': 'application/x-www-form-urlencoded',
				'Authorization' : Authorization,
				'Accept': 'application/json'
			}
			data = urlencode({
			'grant_type':'refresh_token',
			'refresh_token':instance.refresh_token
			})
			response = requests.post(url,data, headers = headers)
			if response.status_code in [200,201]:
				res = response.json()
				refresh_token = res.get('refresh_token','')
				access_token = res.get('access_token','')
				vals = {
					'refresh_token':refresh_token,
					'access_token':access_token
				}
				instance.write(vals)
				self.env.cr.commit()
		return{
			'url': 'https://sandbox-quickbooks.api.intuit.com/v3/company/%s/'%realmId if instance.environment=='sandbox' else 'https://quickbooks.api.intuit.com/v3/company/%s/'%realmId,
			'access_token':access_token,
			'default_category_id':default_category_id,
			'default_warehouse_id':default_warehouse_id,
			'company_id':company_id,
			'default_pricelist_id':default_pricelist_id,
			'default_sales_team':default_sales_team,
			'default_sales_user':default_sales_user,
			'automate_confirm_sale_order':automate_confirm_sale_order,
			'automate_confirm_purchase_order':automate_confirm_purchase_order,
			'quickbook_income_account' :quickbook_income_account,
			'quickbook_asset_account' :quickbook_asset_account,
			'quickbook_expense_account' :quickbook_expense_account,
			'quickbook_account_tax' :quickbook_account_tax,
			'quickbook_account_code' :quickbook_account_code,
			'quickbook_account_tax_code':quickbook_account_tax_code,
			'quickbook_account_purchase_tax_code':quickbook_account_purchase_tax_code,
			'quickbook_account_payble_account':quickbook_account_payble_account,
			'quickbook_default_order_line_tax':quickbook_default_order_line_tax,
			'importCategoryTime' : importCategoryTime,
			'importProductTime' : importProductTime,
			'importCustomerTime' : importCustomerTime,
			'importOrderTime' : importOrderTime,
			'importPurchaseOrderTime':importPurchaseOrderTime,
			'importVendorTime':importVendorTime,
			'importInvoiceTime':importInvoiceTime,
			'importBillTime':importBillTime,
			'importPaymentTime':importPaymentTime,
			'apply_tax_after_discount':apply_tax_after_discount,
			'avoid_duplicity': avoid_duplicity,
			}

	@api.model
	def get_quantity(self, obj_pro):
		quantity = 0.0
		ctx = self.env.context.copy() or {}
		if 'location' not in ctx:
			ctx.update({
				'location': self.location_id.id
			})
		product = obj_pro.with_context(ctx)
		quantity = product.qty_available
		quantity = quantity.split('.')[0] if type(quantity) == str else quantity.as_integer_ratio()[0] if type(quantity) == float else quantity
		return quantity
 
	def sync_realtime_quantity(self, instance_id, mapping_id, quantity):
		try:
			count = 0
			all_fields = instance_id.read()[0]
			headers = {
				'Content-type':'application/json',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%all_fields.get('access_token')
			}	
			url = 'https://sandbox-quickbooks.api.intuit.com/v3/company/%s/'%all_fields.get('realmId') if all_fields.get('environment')=='sandbox' else 'https://quickbooks.api.intuit.com/v3/company/%s/'%all_fields.get('realmId')
			get_url = url + 'item/%s?minorversion=75'%mapping_id.quickbook_id
			url += 'item?minorversion=75'
			get_response = requests.request('GET', get_url, data=None, headers=headers)
			if not get_response.ok:
				if get_response.status_code == 401:
					count +=1
					if count < 2: # Call again
						connection = self._create_quickbook_connection(all_fields.get('id'), refresh_token=all_fields.get('refresh_token'))
						return self.sync_realtime_quantity(instance_id, mapping_id, quantity)
				_logger.error('Something went wrong in updating the product stock %r', get_response.json())
				return False
			item = get_response.json().get('Item')
			if item.get('Type') == "Inventory":
				item.update({'TrackQtyOnHand':True, 'QtyOnHand': quantity})
				response = requests.request('POST', url, data=json.dumps(item), headers=headers)
				if not response.ok:
					_logger.info('Error in real time stock sync: {}'.format(response.text))
			else:
				_logger.info("Can not track quantity for this product")
		except Exception as e:
			_logger.error('Error in real time stock sync: %r', e)
			return False
