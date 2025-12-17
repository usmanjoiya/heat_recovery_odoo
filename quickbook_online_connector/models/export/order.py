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

	def export_sync_order(self,connection, instance_id, limit):
		mapping = self.env['quickbookonline.order']
		exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
		to_export_ids = self.env['sale.order'].search([('id','not in',exported_ids),
		('state','not in',['cancel']),('order_line','!=',False)],limit=limit)
		successfull_ids, unsuccessfull_ids = [],[]
		apply_tax = False
		msg = ''
		message = ''
		if not to_export_ids.ids:
			message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
		try:
			for order_id in to_export_ids:
				response = self.export_online_order(connection, order_id, instance_id)
				if response.get('status'):
					quickbook_id = response['quickbook_id']
					order_id.doc_number = response['doc_number']
					self.create_odoo_mapping('quickbookonline.order', order_id.id, quickbook_id, instance_id)
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
	
	def get_sale_lines_schema(self, connection, sale_order, instance_id):
		orderLines = []
		discounts = sale_order.order_line.mapped('discount')
		ids = sale_order.order_line.filtered(lambda rec: rec.discount != discounts[0])
		if ids:
			return []
		for orderLine in sale_order.order_line:       
			if orderLine.product_id:
				productName = self.check_online_specific_product(connection, orderLine.product_id, instance_id)
				tax_code = ''
				if connection.get('quickbook_account_code'):
					if orderLine.tax_ids and not orderLine.tax_ids[0].price_include:
						tax_code = connection['quickbook_account_code'].name
				
				else:
					if orderLine.tax_ids and not orderLine.tax_ids[0].price_include:
						tax_code =  connection.get('quickbook_account_tax_code').quickbook_id if connection.get('quickbook_account_tax_code') else False
					else:
						tax_code = connection.get('quickbook_default_order_line_tax').quickbook_id if connection.get('quickbook_default_order_line_tax') else False
					if not tax_code:
						_logger.warning('Please Select Quickbook Account Tax Code For The Instance')
				schema = {
				'Description': orderLine.name,
				'DetailType': 'SalesItemLineDetail',
				'Amount':orderLine.product_uom_qty * orderLine.price_unit or 0
				}
				schema['SalesItemLineDetail'] = {
					'Qty': orderLine.product_uom_qty or 0,
					'UnitPrice': orderLine.price_unit or 0,
					'ItemRef': {'value':productName}
				}
				if tax_code:
					schema['SalesItemLineDetail']['TaxCodeRef'] = {'value':tax_code}
				orderLines.append(schema)
		if orderLines:
			orderLines.append({
				'DetailType': 'DiscountLineDetail',
				'DiscountLineDetail': {
					'PercentBased': True,
					'DiscountPercent': discounts[0],
					'DiscountAccountRef': {
						'value': '86',
						'name': 'Discounts given'
					}
				}
			})		
		return orderLines
	
	def get_export_order_schema(self, connection, sale_order, instance_id):
		schema = {}
		TxnTaxCodeRef = connection.get('quickbook_account_tax_code')
		schema = {
			'TotalAmt': sale_order.amount_total or 0,
			'CustomerRef':{'value':self.check_online_specific_partner(connection,sale_order.partner_id, instance_id)},
		}
		if TxnTaxCodeRef:
			schema['TxnTaxDetail'] ={
				'TxnTaxCodeRef':{'value':TxnTaxCodeRef.quickbook_id
				}}
		schema['DocNumber'] = str(sale_order.name)
		if sale_order.payment_term_id:
			SalesTermRef = self.get_sales_term_ref(sale_order.payment_term_id, instance_id)
			if SalesTermRef:
				schema['SalesTermRef'] = {'value':SalesTermRef}
		schema['Line'] = self.get_sale_lines_schema(connection, sale_order, instance_id)
		schema['ApplyTaxAfterDiscount'] = True
		_logger.info("==============================================schema%r",schema)
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

	def export_online_order(self,connection,order_id, instance_id):
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
			url+= 'estimate?minorversion=75'
			schema = self.get_export_order_schema(connection, order_id, instance_id)
			if not schema['Line']:
				return {
				'status':False,
				'message':"Discount are not same in orderLine"
			}
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				quickbook_id =  response.get('Estimate')['Id']
				doc_number = response['Estimate']['DocNumber']
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'quickbook_id':quickbook_id,
			'doc_number':doc_number,
			'message':message
		}
	

	def check_online_specific_order(self, connection, order_id, instance_id):
		mapping = self.env['quickbookonline.order']
		domain = [('instance_id','=',instance_id),
		('name','=',order_id.id)]
		search = mapping.search(domain,limit=1)
		quickbook_id = False
		if search:
			quickbook_id = search.quickbook_id
		else:
			response = self.export_online_order(connection, order_id, instance_id)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.order', order_id.id, quickbook_id, instance_id)
		return quickbook_id
		
