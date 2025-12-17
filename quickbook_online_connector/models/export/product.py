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
from .partner import remove_validation
_logger = logging.getLogger(__name__)

product_type = {
	'service':'Service',
	'consu':'NonInventory',
}

class QuickBookOnlineAccount(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'

	def export_sync_product(self,connection, instance_id, limit):
		mapping = self.env['quickbookonline.product']
		exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
		to_export_ids = self.env['product.product'].search([('id','not in',exported_ids),
		('type','not in',[False])],limit=limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		if not to_export_ids.ids:
			message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
		try:
			for product_id in to_export_ids:
				if product_id.type:
					vals = {
						'name' : self.remove_validation(product_id.name),
					}
					product_id.write(vals)
					response = self.export_online_product(connection, product_id, instance_id)
					if response.get('status'):
						quickbook_id = response['quickbook_id']
						self.create_odoo_mapping('quickbookonline.product', product_id.id, quickbook_id, instance_id)
						successfull_ids.append(product_id.id)
					else:
						unsuccessfull_ids.append(str(product_id.id))
						if response['message']:
							msg += '<span>({}) {}</span><br>'.format(str(product_id.id), response['message'])
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		else:
			if successfull_ids:
				message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Products SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
			if unsuccessfull_ids:
				message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Products Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def export_update_product(self, connection, instance_id, limit):
		mapping = self.env['quickbookonline.product']
		to_update_ids = mapping.search([('instance_id','=',instance_id),
		('is_sync','=','yes')],limit = limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		try:
			for to_update in to_update_ids:
				product_id = to_update.name
				quickbook_id = to_update.quickbook_id
				response = self.update_online_product(connection,product_id,quickbook_id, instance_id)
				if response.get('status'):
					to_update.is_sync = 'no'
					successfull_ids.append(product_id.id)
				else:
					unsuccessfull_ids.append(str(product_id.id))
					if response['message']:
						msg += '<span>({}) {}</span><br>'.format(str(product_id.id), response['message'])
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		else:
			if successfull_ids:
				message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Products SuccessFull Updated To Quickbook.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
			if unsuccessfull_ids:
				message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Products Updated IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def update_online_product(self,connection,product_id,quickbook_id, instance_id):
		status = False
		url = connection.get('url')
		access_token = connection.get('access_token')
		client = self.env['call.quickbook.api']
		message = 'SuccessFully Updated'
		if url and access_token:
			headers = {
				'Content-type':'application/json',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			get_url = url + 'item/%s?minorversion=75'%quickbook_id
			url+= 'item?minorversion=75'
			try:
				get_product_schema =  client.call_online_api(get_url,'GET',None, headers = headers)
			except:
				pass
			schema = self.get_default_product_schema(connection,product_id, instance_id)
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'message':message
		}
	
	def get_default_product_schema(self, connection, product_id, instance_id):
		schema = {
				'Type':'Inventory' if product_id.is_storable else product_type[product_id.type],
				'Name': remove_validation(product_id.display_name),
				'UnitPrice': product_id.lst_price or 0.0,
				'PurchaseCost': product_id.standard_price or 0.0,
				'Active':True,
				'Description': remove_validation(product_id.description or '',3999),
				'PurchaseDesc': remove_validation(product_id.description_purchase or '',3999),
				'Sku': product_id.default_code or '', 
			}
		ParentRef = self.check_online_specific_category(connection,product_id.categ_id, instance_id)
		if ParentRef:
			schema['SubItem'] = True
			schema['ParentRef'] = {'value':ParentRef}
		if product_id.type in ('consu','service'):
			account = connection.get('quickbook_income_account')
			if not account:
				raise UserError("Please Set Income Account For The Instance")
			IncomeAccountRef =self.check_online_specific_account(connection, account, instance_id)
			if IncomeAccountRef:
				schema['IncomeAccountRef'] = {'value':IncomeAccountRef}
		if schema['Type'] =='Inventory':
			if not connection.get('quickbook_asset_account'):
				raise UserError("Please Set Asset Account For The Instance")
			AssetAccountRef = self.check_online_specific_account(connection,connection.get('quickbook_asset_account'), instance_id)
			if AssetAccountRef:
				schema['AssetAccountRef'] ={'value':AssetAccountRef}
			schema['InvStartDate'] = product_id.create_date.strftime("%Y-%m-%d")
			schema['QtyOnHand'] = int(product_id.qty_available) or 0
			schema['TrackQtyOnHand'] = True
		if not connection.get('quickbook_expense_account'):
			raise UserError("Please Set Expense Account For The Instance")
		ExpenseAccountRef = self.check_online_specific_account(connection,connection.get('quickbook_expense_account'), instance_id)
		if ExpenseAccountRef:
			schema['ExpenseAccountRef'] = {'value':ExpenseAccountRef}
		_logger.info("==============================================schema%r",schema)
		return schema


	def export_online_product(self,connection,product_id, instance_id):
		status = False
		url = connection.get('url')
		access_token = connection.get('access_token')
		client = self.env['call.quickbook.api']
		quickbook_id = ''
		message = 'SuccessFully Exported'
		if url and access_token:
			headers = {
				'Content-type':'application/json',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			url+= 'item?minorversion=75'
			schema = self.get_default_product_schema(connection, product_id, instance_id)
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				quickbook_id =  response.get('Item')['Id']
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'quickbook_id':quickbook_id,
			'message':message
		}
	

	def check_online_specific_product(self, connection, product_id, instance_id):
		mapping = self.env['quickbookonline.product']
		domain = [('instance_id','=',instance_id),
		('name','=',product_id.id)]
		search = mapping.search(domain,limit=1)
		quickbook_id = False
		if search:
			quickbook_id = search.quickbook_id
		else:
			response = self.export_online_product(connection, product_id, instance_id)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.product', product_id.id, quickbook_id, instance_id)
		return quickbook_id
		

	def remove_validation(self,name, lenght = False):
		bad_chars = [';', ':', '!', "*", "$", "'"]
		for char in bad_chars:
			name.replace(char,'')
		if lenght:
			if len(name)>lenght:
				name = ''.join(name[0:lenght-1])
		return name.strip()
