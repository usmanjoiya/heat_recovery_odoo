# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
_logger = logging.getLogger(__name__)

class quickbookonlineSynchronization(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'
	
	
	def import_import_purchase_order(self,connection, instance_id, limit):
		TimeModified = connection.get('importPurchaseOrderTime')
		if TimeModified:
			query = "WHERE Metadata.CreateTime>'%s' OrderBy Metadata.CreateTime"%TimeModified
		else:
			query = 'OrderBy Metadata.CreateTime'
		message,TimeModified = self.import_get_purchase_order(connection, instance_id, limit, query)
		if TimeModified:
			self.env['quickbookonline.instance'].browse(instance_id).importPurchaseOrderTime = TimeModified
		return message
	

	def import_get_purchase_order(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from purchaseorder  %s MAXRESULTS %d"%(statement,limit)
		purchase_order = self.env['purchase.order']
		mapping = self.env['quickbookonline.purchase.order']
		message = '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>'
		TimeModified = False
		client = self.env['call.quickbook.api']
		access_token = connection.get('access_token')
		try:
			headers = {
				'Content-type':'text/plain',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			response = client.get_query_object(url, query, headers,75)
			orders = response.get('PurchaseOrder',[])
			success_ids = []
			for order in orders:
				_logger.info("==============================order%r",order)
				domain = [('instance_id','=',instance_id),
				('quickbook_id','=',order['Id'])
				]
				TimeModified = order['MetaData']['CreateTime']
				search = mapping.search(domain,limit=1)
				if not search:
					vals = self.get_import_purchase_vals(order, connection, instance_id)
					odoo_id = purchase_order.create(vals)
					success_ids.append(self.create_odoo_mapping('quickbookonline.purchase.order', odoo_id.id, 
					order['Id'], instance_id,{'created_by':'import'}))
			message += '{} Purchase Orders SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message,TimeModified

	def get_import_purchase_vals(self, order, connection, instance_id):
		vals = {}
		
		partner_id = self.import_get_specific_vendor(connection, order.get('VendorRef',{}).get('value'), instance_id)
		if partner_id:
			vals = {
				'currency_id':connection.get('default_pricelist_id').currency_id.id if connection.get('default_pricelist_id') else False,
				'user_id':connection.get('default_sales_user').id
				}
			vals['partner_id'] = partner_id
			vals['doc_number'] = order['DocNumber']
			vals['order_line'] = self.get_import_purchase_lines(order, connection, instance_id)
			vals['date_planned'] = order['TxnDate']
			SalesTermRef = order.get('SalesTermRef',{}).get('value')
			if SalesTermRef:
				odoo_id = self.get_import_payment_term_id(SalesTermRef, instance_id)
				if odoo_id:
					vals['payment_term_id'] = odoo_id
		return vals
	

	def get_import_purchase_lines(self, order, connection, instance_id):
		tax_id = []
		lines = []
		TaxLines = order.get('TxnTaxDetail',{}).get('TaxLine',[])
		for TaxLine in TaxLines:
			tax = self.get_online_import_tax(TaxLine['TaxLineDetail']['TaxRateRef']['value'],instance_id)
			if tax:
				tax_id.append(tax)
		for line in order['Line']:
			if line.get('DetailType')=='ItemBasedExpenseLineDetail':
				productId = self.import_get_specific_product(connection,line['ItemBasedExpenseLineDetail']['ItemRef']['value'],instance_id)
				if productId:
					vals = {
					'name': line.get('description'),
					'product_qty': line.get('ItemBasedExpenseLineDetail',{}).get('Qty',1),
					'price_unit':line.get('ItemBasedExpenseLineDetail',{}).get('UnitPrice',1),
					'taxes_id':False,
					}
					code_ref = line.get('ItemBasedExpenseLineDetail',{}).get('TaxCodeRef',{}).get('value')
					if code_ref:
						tax_code = self.env['quickbookonline.tax.code'].search([('instance_id','=', instance_id),('quickbook_id','=',code_ref)],limit=1)
						if tax_code and tax_code.is_taxable and tax_code.tax_ids:
							vals['taxes_id'] = [(6,0,tax_code.tax_ids.ids)]
					product_id = productId
					product = self.env['product.product'].browse(product_id)
					vals.update({
						'product_id': product_id,
						'product_uom': product.uom_id.id
						})
					if not vals['name']:
						vals['name'] = product.description or ''
					lines.append((0,0,vals))
		return lines

	def import_get_specific_purchase_order(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.purchase.order']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id)]
		order = False
		find = mapping.search(domain,limit=1)
		if find:
			order = find.name
		else:
			query = "WHERE Id='%s'"%quickbook_id
			self.import_get_purchase_order(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				order = find.name
		return order
