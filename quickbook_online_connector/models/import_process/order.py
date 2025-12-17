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
	
	
	def import_import_order(self,connection, instance_id, limit):
		TimeModified = connection.get('importOrderTime')
		if TimeModified:
			query = "WHERE Metadata.CreateTime>'%s' OrderBy Metadata.CreateTime"%TimeModified
		else:
			query = 'OrderBy Metadata.CreateTime'
		message,TimeModified = self.import_get_order(connection, instance_id, limit, query)
		if TimeModified:
			self.env['quickbookonline.instance'].browse(instance_id).importOrderTime = TimeModified
		return message
	

	def import_get_order(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from Estimate  %s MAXRESULTS %d"%(statement,limit)
		_logger.info("============================================query%r",query)
		order_order = self.env['sale.order']
		mapping = self.env['quickbookonline.order']
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
			orders = response.get('Estimate',[])
			success_ids = []
			for order in orders:
				domain = [('instance_id','=',instance_id),
				('quickbook_id','=',order['Id'])
				]
				TimeModified = order['MetaData']['CreateTime']
				search = mapping.search(domain,limit=1)
				if not search:
					vals = self.get_import_order_vals(order, connection, instance_id)
					odoo_id = order_order.create(vals)
					success_ids.append(self.create_odoo_mapping('quickbookonline.order', odoo_id.id, 
					order['Id'], instance_id,{'created_by':'import'}))
			message += '{} Orders SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message,TimeModified

	def get_import_order_vals(self, order, connection, instance_id):
		vals = {}
		vals = {'warehouse_id': connection.get('default_warehouse_id').id,
				'pricelist_id':connection.get('default_pricelist_id').id,
				'team_id': connection.get('default_sales_team').id,
				'user_id':connection.get('default_sales_user').id
		}
		vals['partner_id'] = self.import_get_specific_customer(connection, order.get('CustomerRef',{}).get('value'), instance_id)
		vals['doc_number'] = order['DocNumber']
		vals['order_line'] = self.get_import_order_lines(order, connection, instance_id)
		SalesTermRef = order.get('SalesTermRef',{}).get('value')
		if SalesTermRef:
			odoo_id = self.get_import_payment_term_id(SalesTermRef, instance_id)
			if odoo_id:
				vals['payment_term_id'] = odoo_id
		return vals
	

	def get_import_payment_term_id(self, quickbook_id, instance_id):
		payment_term = self.env['quickbookonline.payment.term.map']
		domain = [('instance_id','=',instance_id),('quickbook_id','=',quickbook_id)]
		payment_term_id = payment_term.search(domain,limit=1)
		if payment_term_id:
			return payment_term_id.odoo_id
		return False

	def get_import_order_lines(self, order, connection, instance_id):
		tax_id = []
		lines = []
		if connection.get('apply_tax_after_discount') != order.get('ApplyTaxAfterDiscount'):
			_logger.error("ApplyTaxAfterDiscount is not Match at the QuickBook End")
		TaxLines = order.get('TxnTaxDetail',{}).get('TaxLine',[])
		for TaxLine in TaxLines:
			tax = self.get_online_import_tax(TaxLine['TaxLineDetail']['TaxRateRef']['value'],instance_id)
			if tax:
				tax_id.append(tax)
		discount = False
		discountLineDetail = order['Line'][-1]
		if discountLineDetail.get('DetailType') == 'DiscountLineDetail':
			if connection.get('apply_tax_after_discount') and discountLineDetail.get('DiscountLineDetail',{}).get('PercentBased'):
				discount = discountLineDetail.get('DiscountLineDetail',{}).get('DiscountPercent',0.0)
		for line in order['Line']:
			if line.get('DetailType')=='SalesItemLineDetail':
				vals = {
				'name': line.get('description'),
				'product_uom_qty': line.get('SalesItemLineDetail',{}).get('Qty',1),
				'price_unit':line.get('SalesItemLineDetail',{}).get('UnitPrice',1),
				}
				code_ref = line.get('SalesItemLineDetail',{}).get('TaxCodeRef',{}).get('value')
				# NON: Tax is not applied to this line
				if not code_ref == "NON" and tax_id:
					vals['tax_id'] = [(6,0,tax_id)]
				if connection.get('apply_tax_after_discount') and discount:
						vals['discount'] = discount
				product_id = self.import_get_specific_product(connection,line['SalesItemLineDetail']['ItemRef']['value'],instance_id)
				if product_id:
					product = self.env['product.product'].browse(product_id)
					vals.update({
						'product_id': product_id,
						'product_uom_id': product.uom_id.id
						})
					if not vals['name']:
						vals['name'] = product.description or ''
					lines.append((0,0,vals))
			elif line.get('DetailType')=='DiscountLineDetail':
				if discount:
					continue
				else:
					vals = self.get_discount_product(instance_id)
					if line.get('Amount'):
						vals.update({
							'name':line.get('DiscountLineDetail',{}).get('name') or 'Discount Applied On Estimate',
							'price_unit': -float(line.get('Amount')),
							'product_uom_qty':1,
						})
						if tax_id and order.get('ApplyTaxAfterDiscount'):
							vals['tax_id'] = [(6, 0, tax_id)]
						lines.append((0,0,vals))
		return lines

	def get_discount_product(self, instance_id):
		instance = self.env['quickbookonline.instance'].browse(instance_id)
		vals = {}
		if instance.discount_product_id:
			odoo_id = instance.discount_product_id
		else:
			odoo_id = self.env['product.product'].create({
					'sale_ok' : False,
					'name' : 'Discount',
					'type' : 'service',
					'list_price' : 0.0,
					'description': 'Service Type product used by Quickbook Online for Discount Purposes'
				})
			instance.discount_product_id = odoo_id.id
		vals.update({
			'product_id': odoo_id.id,
			'product_uom_id': odoo_id.uom_id.id
		})
		return vals
			
			
	
	def get_online_import_tax(self, quickbook_id, instance_id):
		tax_env = self.env['quickbookonline.tax']
		domain = [('instance_id','=',instance_id),('quickbook_id','=',quickbook_id)]
		tax_id = tax_env.search(domain,limit=1)
		if tax_id:
			return tax_id.odoo_id
		return []

	def import_get_specific_order(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.order']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id)]
		order = False
		find = mapping.search(domain,limit=1)
		if find:
			order = find.name
		else:
			query = "WHERE Id='%s'"%quickbook_id
			self.import_get_order(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				order = find.name
		return order
