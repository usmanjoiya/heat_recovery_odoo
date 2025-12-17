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

	def export_sync_invoice(self,connection, instance_id, limit):
		mapping = self.env['quickbookonline.invoice']
		exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
		to_export_ids = self.env['account.move'].search([('id','not in',exported_ids),
		('state','not in',['cancel','draft']),('move_type','=','out_invoice')],limit=limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		if not to_export_ids.ids:
			message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
		try:
			for invoice_id in to_export_ids:
				response = self.export_online_invoice(connection, invoice_id, instance_id)
				if response.get('status'):
					quickbook_id = response['quickbook_id']
					invoice_id.doc_number = response['doc_number']
					self.create_odoo_mapping('quickbookonline.invoice', invoice_id.id, quickbook_id, instance_id)
					successfull_ids.append(invoice_id.id)
				else:
					unsuccessfull_ids.append(str(invoice_id.id))
					if response['message']:
						msg += '<span>({}) {}</span><br>'.format(str(invoice_id.id), response['message'])
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		else:
			if successfull_ids:
				message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Invoice SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
			if unsuccessfull_ids:
				message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Invoices Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def get_invoice_lines_schema(self, connection, move_invoice, instance_id):
		invoiceLines = []
		discounts = move_invoice.invoice_line_ids.mapped('discount')
		ids = move_invoice.invoice_line_ids.filtered(lambda rec: rec.discount != discounts[0])
		if ids:
			return []
		for invoiceLine in move_invoice.invoice_line_ids:  
			productName = self.check_online_specific_product(connection, invoiceLine.product_id, instance_id)
			tax_code = ''
			if connection.get('quickbook_account_code'):
				# if invoiceLine.tax_ids and not invoiceLine.tax_ids[0].price_include:
				if invoiceLine.tax_ids:
					tax_code = connection['quickbook_account_code'].name
			else:
				# if invoiceLine.tax_ids and not invoiceLine.tax_ids[0].price_include:
				# 	tax_code =  connection.get('quickbook_account_tax_code').quickbook_id if connection.get('quickbook_account_tax_code') else False
				# else:
				tax_code = connection.get('quickbook_default_order_line_tax').quickbook_id if connection.get('quickbook_default_order_line_tax') else False
			# if not tax_code:
			# 	# raise UserError('Please Select Quickbook Account Tax For The Instance')
			# 	_logger.warning(f'Please Select Quickbook Account Tax For The Instance')
			schema = {
			'Description': invoiceLine.name or '',
			'DetailType': 'SalesItemLineDetail',
			'Amount':invoiceLine.quantity*invoiceLine.price_unit or 0
			}
			schema['SalesItemLineDetail'] = {
				'Qty': invoiceLine.quantity or 0,
				'UnitPrice': invoiceLine.price_unit or 0,
				'ItemRef': {'value':productName}
			}
			if tax_code:
				schema['SalesItemLineDetail']['TaxCodeRef'] = {'value':tax_code}
			else:
				_logger.warning(f'Please Select Quickbook Account Tax For The Instance')
				
			invoiceLines.append(schema)
		if invoiceLines:
			invoiceLines.append({
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
		return invoiceLines
	
	def get_export_invoice_schema(self, connection, move_invoice, instance_id):
		schema = {}
		TxnTaxCodeRef = connection.get('quickbook_account_tax_code')
		if move_invoice.partner_id and move_invoice.partner_id.parent_id:
			partner_id = move_invoice.partner_id.parent_id
		else:
			partner_id = move_invoice.partner_id
		schema = {
			'TotalAmt': move_invoice.amount_total or 0,
			'CustomerRef':{'value':self.check_online_specific_partner(connection,partner_id, instance_id)},
		}
		if move_invoice.invoice_date:
			schema['TxnDate'] =  move_invoice.invoice_date.strftime("%Y-%m-%d")
		if move_invoice.invoice_date_due:
			schema['DueDate'] = move_invoice.invoice_date_due.strftime("%Y-%m-%d")
		if move_invoice.invoice_origin:
			sale_order = self.env['sale.order'].search([('name','=',move_invoice.invoice_origin)],limit=1)
			if sale_order:
				sale_quickbook_id = self.check_online_specific_order(connection, sale_order, instance_id)
				schema.update({
					'LinkedTxn':[{
						'TxnId':sale_quickbook_id,
						'TxnType':'Estimate'
						}]})
		if TxnTaxCodeRef:
			schema['TxnTaxDetail'] ={
				'TxnTaxCodeRef':{'value':TxnTaxCodeRef.quickbook_id
				}}
		schema['DocNumber'] = str(move_invoice.name)
		if move_invoice.invoice_payment_term_id:
			SalesTermRef = self.get_sales_term_ref(move_invoice.invoice_payment_term_id, instance_id)
			if SalesTermRef:
				schema['SalesTermRef'] = {'value':SalesTermRef}
		schema['Line'] = self.get_invoice_lines_schema(connection, move_invoice, instance_id)
		schema['ApplyTaxAfterDiscount'] = True
		_logger.info("============================================schema%r",schema)
		return schema

	def export_online_invoice(self,connection,invoice_id, instance_id):
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
			url+= 'invoice?minorversion=75'
			schema = self.get_export_invoice_schema(connection, invoice_id, instance_id)
			if not schema['Line']:
				return{
					'status':False,
					'message':"Discount are not same in invoice lines"
				}
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				quickbook_id =  response.get('Invoice')['Id']
				doc_number = response['Invoice']['DocNumber']
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'quickbook_id':quickbook_id,
			'doc_number':doc_number,
			'message':message
		}
	

	def check_online_specific_invoice(self, connection, invoice_id, instance_id):
		mapping = self.env['quickbookonline.invoice']
		domain = [('instance_id','=',instance_id),
		('name','=',invoice_id.id)]
		search = mapping.search(domain,limit=1)
		quickbook_id = False
		if search:
			quickbook_id = search.quickbook_id
		else:
			response = self.export_online_invoice(connection, invoice_id, instance_id)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.invoice', invoice_id.id, quickbook_id, instance_id)
		return quickbook_id
		
