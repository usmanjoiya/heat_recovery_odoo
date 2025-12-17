# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
_logger = logging.getLogger(__name__)

product_type = {
	'Service':'service',
	'NonInventory':'consu',
	'Inventory':'consu'
}

class quickbookonlineSynchronization(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'
	
	
	def import_import_product(self,connection, instance_id, limit):
		TimeModified = connection.get('importProductTime')
		if TimeModified:
			query = "WHERE Metadata.LastUpdatedTime>='%s' OrderBy Metadata.LastUpdatedTime"%TimeModified
		else:
			query = 'OrderBy Metadata.LastUpdatedTime'
		message,TimeModified = self.import_get_product(connection, instance_id, limit, query)
		if TimeModified:
			self.env['quickbookonline.instance'].browse(instance_id).importProductTime = TimeModified
		return message
	

	def import_get_product(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from Item  %s MAXRESULTS %d"%(statement,limit)
		product_product = self.env['product.product']
		mapping = self.env['quickbookonline.product']
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
			products = response.get('Item',[])
			success_ids = []
			for product in products:
				if product['Type'] in product_type:
					vals = self.get_import_product_vals(product, connection, instance_id)
					domain = [('instance_id','=',instance_id),
					('quickbook_id','=',product['Id'])
					]
					TimeModified = product['MetaData']['LastUpdatedTime']
					search = mapping.search(domain,limit=1)
					if search:
						search.name.write(vals)
					else:
						vals['is_storable'] = False
						if product['Type'] == 'Inventory':
							vals['type'] = product_type[product['Type']]
							vals['is_storable'] = True
						else:
							vals['type'] = product_type[product['Type']]
						vals['invoice_policy'] = 'order'
						vals['purchase_method'] = 'purchase'
						# Avoid Duplicity:
						exists_odoo = False
						if connection.get('avoid_duplicity'):
							exists_odoo = self.match_odoo_product(vals.get('default_code'))
						if exists_odoo:
							odoo_id = exists_odoo
						else:
							odoo_id = product_product.create(vals)
						if vals['type']=='consu' and vals.get('is_storable'):
							qty = product.get('QtyOnHand',0)
							if qty:
								self.create_product_quantity(odoo_id.id,float(qty), connection.get('default_warehouse_id'))
						success_ids.append(self.create_odoo_mapping('quickbookonline.product', odoo_id.id, product['Id'], instance_id,{'created_by':'import'}))
			message += '{} Products SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message,TimeModified


	def create_product_quantity(self, product_id,quantity, warehouse_id):
		""" Changes the Product Quantity by making a Physical Inventory.
		@param self: The object pointer.
		@param product_id: product_id
		@param quantity: quantity of the product
		@param warehouse: warehouse to store quantity
		@return: True
		"""
		ctx = dict(self.env.context or {})
		ctx.update({'restrict_stock_sync': True})
		location_objs = warehouse_id if warehouse_id else self.env['stock.warehouse'].search([], limit=1)
		if location_objs:
			ctx['inventory_mode'] = True
			ctx['inventory_report_mode'] = True
			quant = self.env['stock.quant'].with_context(ctx).create({
						'product_id': product_id,
						'location_id': location_objs.lot_stock_id.id,
						'inventory_quantity': int(quantity),
			})
			quant.action_apply_inventory()
			return True
		return False   	

	def get_import_product_vals(self, product, connection, instance_id):
		vals = {}
		ParentRef = product.get('ParentRef',False)
		if ParentRef:
			odoo_id = self.import_get_specific_cateory(connection,ParentRef['value'],instance_id)
			if odoo_id:
				vals['categ_id'] = odoo_id
			else:
				vals['categ_id'] = connection.get('default_category_id').id
		else:
			vals['categ_id'] = connection.get('default_category_id').id
		vals['name'] = product.get('Name')
		vals['standard_price'] = product.get('PurchaseCost')
		vals['description'] = product.get('Description','')
		vals['default_code'] = product.get('Sku','')
		vals['list_price'] = product.get('UnitPrice',0.0)
		vals['description_purchase'] = product.get('PurchaseDesc','')
		if not product.get('Taxable'):
			vals['taxes_id'] = False
		return vals

	def import_get_specific_product(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.product']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id)]
		product = False
		find = mapping.search(domain,limit=1)
		if find:
			product = find.odoo_id
		else:
			query = "WHERE Id='%s'"%quickbook_id
			self.import_get_product(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				product = find.odoo_id
		return product
