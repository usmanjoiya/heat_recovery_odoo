# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
import json
from .partner import remove_validation
_logger = logging.getLogger(__name__)


class QuickBookOnlinepartner(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'

	def export_sync_vendor(self,connection, instance_id, limit):
		mapping = self.env['quickbookonline.partner']
		exported_ids = mapping.search([('instance_id','=',instance_id),
		('partner_type','=','vendor')]).mapped('name').ids
		to_export_ids = self.env['res.partner'].with_context(res_partner_search_mode='supplier').search([('id','not in',exported_ids),
		('name','not in',[False,'',' ']),('supplier_rank','=',1)],limit=limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		if not to_export_ids.ids:
			message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
		for partner_id in to_export_ids:
			response = self.export_online_vendor(connection, partner_id, instance_id)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.partner', partner_id.id, quickbook_id, instance_id,
				{'partner_type':'vendor'})
				successfull_ids.append(partner_id.id)
			else:
				unsuccessfull_ids.append(str(partner_id.id))
				if response['message']:
					msg += '<span>({}) {}</span><br>'.format(str(partner_id.id), response['message'])
		if successfull_ids:
			message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Vendors SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
		if unsuccessfull_ids:
			message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Vendors Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def export_update_vendor(self, connection, instance_id, limit):
		mapping = self.env['quickbookonline.partner']
		to_update_ids = mapping.search([('instance_id','=',instance_id),
		('is_sync','=','yes')])
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		try:
			for to_update in to_update_ids:
				partner_id = to_update.name
				quickbook_id = to_update.quickbook_id
				response = self.update_online_vendor(connection,partner_id,quickbook_id, instance_id)
				if response.get('status'):
					to_update.is_sync = 'no'
					successfull_ids.append(partner_id.id)
				else:
					unsuccessfull_ids.append(str(partner_id.id))
					if response['message']:
						msg += '<span>({}) {}</span><br>'.format(str(partner_id.id), response['message'])
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		else:
			if successfull_ids:
				message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Vendors SuccessFull Updated To Quickbook.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
			if unsuccessfull_ids:
				message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Vendors Updated IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def update_online_vendor(self,connection,partner_id,quickbook_id, instance_id):
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
			
			schema = self.get_export_vendor_schema(partner_id)
			schema['Id'] = str(quickbook_id)
			schema['SyncToken'] = '0'
			get_url = url + 'vendor/%s/minorversion=75'%quickbook_id
			try:
				get_partner_object = client.call_online_api(get_url,'GET',None, headers=headers)
			except:
				pass
			url+= 'vendor?minorversion=75'
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'message':message
		}
			
	def get_export_vendor_schema(self, partner_id):
		split_name =partner_id.name.strip().split(' ') 
		schema = {
			'PrimaryEmailAddr':{
				'Address': partner_id.email or ''
			},
			'DisplayName': remove_validation(partner_id.name or '') + 'v',
			'FamilyName': split_name[0],
			'MiddleName': split_name[1] if len(split_name)>1 else split_name[0],
			'GivenName': split_name[-1],
			'Notes': partner_id.comment or '',
			'PrimaryPhone': {
				'FreeFormNumber': partner_id.phone.strip() if partner_id.phone else ''
			},
			'BillAddr': {
				'CountrySubDivisionCode': partner_id.state_id.code or '',
				'City': partner_id.city or '',
				'PostalCode': partner_id.zip or '',
				'Line1': partner_id.street or '',
				'Line2': partner_id.street2 or '',
				'Country': partner_id.country_id.code or ''
			},
			'ShipAddr': {
				'CountrySubDivisionCode': partner_id.state_id.code or '',
				'City': partner_id.city or '',
				'PostalCode': partner_id.zip or '',
				'Line1': partner_id.street or '',
				'Line2': partner_id.street2 or '',
				'Country': partner_id.country_id.code or ''
			},
			'Mobile':{
				'FreeFormNumber': partner_id.phone or ''
			},
			'WebAddr':{
				'URI':partner_id.website or ''
			}
		}
		return schema
	
	
	def export_online_vendor(self,connection,partner_id, instance_id):
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
			url+= 'vendor?minorversion=75'
			schema = self.get_export_vendor_schema(partner_id)
			_logger.info("===============schema============================%r",schema)
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				quickbook_id =  response.get('Vendor')['Id']
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'quickbook_id':quickbook_id,
			'message':message
		}
	

	def check_online_specific_vendor(self, connection, partner_id, instance_id):
		mapping = self.env['quickbookonline.partner']
		domain = [('instance_id','=',instance_id),
		('name','=',partner_id.id),
		('partner_type','=','vendor')]
		search = mapping.search(domain,limit=1)
		quickbook_id = False
		if search:
			quickbook_id = search.quickbook_id
		else:
			response = self.export_online_vendor(connection, partner_id, instance_id)
			_logger.info("===========================response%r",response)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.partner', partner_id.id, quickbook_id, instance_id,
				{'partner_type':'vendor'})
		return quickbook_id
		
