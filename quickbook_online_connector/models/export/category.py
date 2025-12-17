# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
import json
_logger = logging.getLogger(__name__)


class QuickBookOnlineCategory(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'

	def export_sync_category(self,connection, instance_id, limit):
		mapping = self.env['quickbookonline.category']
		exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
		to_export_ids = self.env['product.category'].search([('id','not in',exported_ids)],limit=limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		if not to_export_ids.ids:
			message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
		try:
			for category_id in to_export_ids:
				response = self.export_online_category(connection, category_id, instance_id)
				if response.get('status'):
					quickbook_id = response['quickbook_id']
					self.create_odoo_mapping('quickbookonline.category', category_id.id, quickbook_id, instance_id)
					successfull_ids.append(category_id.id)
				else:
					unsuccessfull_ids.append(str(category_id.id))
					if response['message']:
						msg += '<span>({}) {}</span><br>'.format(str(category_id.id), response['message'])
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		else:
			if successfull_ids:
				message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Categories SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
			if unsuccessfull_ids:
				message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Categories Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def export_update_category(self, connection, instance_id, limit):
		mapping = self.env['quickbookonline.category']
		to_update_ids = mapping.search([('instance_id','=',instance_id),
		('is_sync','=','yes')],limit = limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		for to_update in to_update_ids:
			category_id = to_update.name
			quickbook_id = to_update.quickbook_id
			response = self.update_online_category(connection,category_id,quickbook_id, instance_id)
			if response.get('status'):
				to_update.is_sync = 'no'
				successfull_ids.append(category_id.id)
			else:
				unsuccessfull_ids.append(str(category_id.id))
				if response['message']:
					msg += '<span>({}) {}</span><br>'.format(str(category_id.id), response['message'])
		if successfull_ids:
			message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Categories SuccessFull Updated To Quickbook.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
		if unsuccessfull_ids:
			message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Categories Updated IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def update_online_category(self,connection,category_id,quickbook_id, instance_id):
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
			get_url = url + 'item/%s/minorversion=75'%quickbook_id
			try:
				get_category_object = client.call_online_api(get_url,'GET',None, headers=headers)
			except:
				pass
			url+= 'item?minorversion=75'
			schema = {
				'SyncToken':'0',
				'domain':'QBO',
				'Name':category_id.name,
				'Type':'Category',
				'sparse':False,
				'Id':str(quickbook_id)
			}
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'message':message
		}
			
	
	def export_online_category(self,connection,category_id, instance_id):
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
			parent_id = False
			if category_id.parent_id:
				parent_id = self.check_online_specific_category(connection,category_id.parent_id, instance_id)
			schema = {
				'Type':'Category',
				'Name':category_id.name,
				'SubItem':False
			}
			if parent_id:
				schema.update({
					'SubItem':True,
					'ParentRef':{
						'name':category_id.parent_id.name,
						'value':parent_id
						}
				})
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
	

	def check_online_specific_category(self, connection, category_id, instance_id):
		mapping = self.env['quickbookonline.category']
		domain = [('instance_id','=',instance_id),
		('name','=',category_id.id)]
		search = mapping.search(domain,limit=1)
		quickbook_id = False
		if search:
			quickbook_id = search.quickbook_id
		else:
			response = self.export_online_category(connection, category_id, instance_id)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.category', category_id.id, quickbook_id, instance_id)
		return quickbook_id
		
