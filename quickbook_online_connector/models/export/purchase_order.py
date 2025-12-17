# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
import json
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

class QuickBookOnlineAccount(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'

	def export_sync_purchase_order(self,connection, instance_id, limit):
		mapping = self.env['quickbookonline.purchase.order']
		exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
		to_export_ids = self.env['purchase.order'].search([('id','not in',exported_ids),
		('state','not in',['cancel']),('order_line','!=',False)],limit=limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		if not to_export_ids.ids:
			message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
		try:
			for order_id in to_export_ids:
				
				response = self.export_online_purchase_order(connection, order_id, instance_id)
				if response.get('status'):
					quickbook_id = response['quickbook_id']
					order_id.doc_number = response['doc_number']
					self.create_odoo_mapping('quickbookonline.purchase.order', order_id.id, quickbook_id, instance_id)
					successfull_ids.append(order_id.id)
				else:
					unsuccessfull_ids.append(str(order_id.id))
					if response['message']:
						msg += '<span>({}) {}</span><br>'.format(str(order_id.id), response['message'])
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		else:
			if successfull_ids:
				message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Orders SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
			if unsuccessfull_ids:
				message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Orders Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def get_lines_schema(self, connection, purchase_order, instance_id):
		orderLines = []
		for orderLine in purchase_order.order_line:       
			productName = self.check_online_specific_product(connection, orderLine.product_id, instance_id)
			tax_code = False
			if connection.get('quickbook_account_code'):
				if orderLine.taxes_id and not orderLine.taxes_id[0].price_include:
					tax_code = connection['quickbook_account_code'].name
			else:
				tax_code =  connection.get('quickbook_account_purchase_tax_code').quickbook_id if connection.get('quickbook_account_purchase_tax_code') else False
				if not tax_code:
					raise UserError('Please Select Quickbook Purchase Tax For The Instance')
			schema = {
			'Description': orderLine.name,
			'DetailType': 'ItemBasedExpenseLineDetail',
			'Amount':orderLine.price_subtotal or 0,
			}
			schema['ItemBasedExpenseLineDetail'] ={
				'Qty': orderLine.product_qty or 0,
				'UnitPrice': orderLine.price_unit or 0,
				'ItemRef': {'value':productName}
			}
			if tax_code:
				schema['ItemBasedExpenseLineDetail']['TaxCodeRef'] = {'value':tax_code}
			orderLines.append(schema)
		return orderLines
	
	def get_export_purchase_order_schema(self, connection, purchase_order, instance_id):
		schema = {}
		account = connection.get('quickbook_account_payble_account')
		if not account:
			raise UserError('Please Select Purchase Payble Account For The Instance')
		APAccountRef =self.check_online_specific_account(connection, account, instance_id)
		if APAccountRef:
			schema['APAccountRef'] = {'value':APAccountRef}
		TxnTaxCodeRef = connection.get('quickbook_account_purchase_tax_code')
		schema.update({
			'TotalAmt': purchase_order.amount_total or 0,
			'VendorRef':{'value':self.check_online_specific_vendor(connection,purchase_order.partner_id, instance_id)},
			'DocNumber': purchase_order.name,
			'GlobalTaxCalculation': 'TaxExcluded',
		})
		if TxnTaxCodeRef:
			schema['TxnTaxDetail'] ={
				'TxnTaxCodeRef':{'value':TxnTaxCodeRef.quickbook_id
				}}
		if purchase_order.date_order.date():
			schema['TxnDate'] = '-'.join([str(purchase_order.date_order.year),str(purchase_order.date_order.month),str(purchase_order.date_order.day)])
		if purchase_order.payment_term_id:
			SalesTermRef = self.get_sales_term_ref(purchase_order.payment_term_id, instance_id)
			if SalesTermRef:
				schema['SalesTermRef'] = {'value':SalesTermRef}
		schema['Line'] = self.get_lines_schema(connection, purchase_order, instance_id)
		_logger.info("=====================================schema%r",schema)
		return schema
	
	def get_online_tax_code(self, account_tax, instance_id):
		tax_env = self.env['quickbookonline.tax']
		domain = [('instance_id','=',instance_id),('name','=',account_tax.id)]
		tax_id = tax_env.search(domain,limit=1)
		if tax_id:
			return tax_id.quickbook_id
		return False
	
	def get_sales_term_ref(self, payment_term_id, instance_id):
		payment_term = self.env['quickbookonline.payment.term.map']
		domain = [('instance_id','=',instance_id),('name','=',payment_term_id.id)]
		payment_term_id = payment_term.search(domain,limit=1)
		if payment_term_id:
			return payment_term_id.quickbook_id
		return False

	def export_online_purchase_order(self,connection,order_id, instance_id):
		status = False
		url = connection.get('url')
		access_token = connection.get('access_token')
		client = self.env['call.quickbook.api']
		quickbook_id = ''
		message = 'SuccessFully Exported'
		doc_number = ''
		if url and access_token:
			headers = {
				'Content-type':'application/json',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			url+= 'purchaseorder?minorversion=75'
			schema = self.get_export_purchase_order_schema(connection, order_id, instance_id)
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				quickbook_id =  response.get('PurchaseOrder')['Id']
				doc_number = response['PurchaseOrder']['DocNumber']
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'quickbook_id':quickbook_id,
			'doc_number':doc_number,
			'message':message
		}
	

	def check_online_specific_purchase_order(self, connection, order_id, instance_id):
		mapping = self.env['quickbookonline.purchase.order']
		domain = [('instance_id','=',instance_id),
		('name','=',order_id.id)]
		search = mapping.search(domain,limit=1)
		quickbook_id = False
		if search:
			quickbook_id = search.quickbook_id
		else:
			response = self.export_online_purchase_order(connection, order_id, instance_id)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.purchase.order', order_id.id, quickbook_id, instance_id)
		return quickbook_id
		
