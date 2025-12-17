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
	
	
	def import_import_vendor(self,connection, instance_id, limit):
		TimeModified = connection.get('importVendorTime')
		if TimeModified:
			query = "WHERE Metadata.LastUpdatedTime>='%s' OrderBy Metadata.LastUpdatedTime"%TimeModified
		else:
			query = 'OrderBy Metadata.LastUpdatedTime'
		message,TimeModified = self.import_get_vendor(connection, instance_id, limit, query)
		if TimeModified:
			self.env['quickbookonline.instance'].browse(instance_id).importVendorTime = TimeModified
		return message
	

	def import_get_vendor(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from vendor %s MAXRESULTS %d"%(statement,limit)
		_logger.info("====================================query%r",query)
		res_vendor = self.env['res.partner']
		mapping = self.env['quickbookonline.partner']
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
			vendors = response.get('Vendor',[])
			success_ids = []
			for vendor in vendors:
				vals = self.get_import_vendor_vals(vendor, connection, instance_id)
				domain = [('instance_id','=',instance_id),
				('quickbook_id','=',vendor['Id']),
				('partner_type','=','vendor')]
				TimeModified = vendor['MetaData']['LastUpdatedTime']
				search = mapping.search(domain,limit=1)
				if search:
					search.name.write(vals)
				else:
					odoo_id = res_vendor.create(vals)
					success_ids.append(self.create_odoo_mapping('quickbookonline.partner', odoo_id.id, vendor['Id'], instance_id,{'created_by':'import',
					'partner_type':'vendor'}))
			message += '{} Vendors SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message,TimeModified
	

	def get_import_vendor_vals(self, vendor, connection, instance_id):
		vals = {}
		ParentRef = vendor.get('ParentRef',False)
		if ParentRef:
			odoo_id = self.import_get_specific_vendor(connection,ParentRef['value'],instance_id)
			vals['parent_id'] = odoo_id
		vals['supplier_rank'] = 1
		vals['name'] = vendor.get('DisplayName')
		vals['phone'] = vendor.get('PrimaryPhone',{}).get('FreeFormNumber',False)
		vals['email'] = vendor.get('PrimaryEmailAddr',{}).get('Address',False)
		vals['comment'] = vendor.get('Notes') or False
		if vendor.get('BillAddr'):
			BillAddr = vendor['BillAddr']
			vals['city'] = BillAddr.get('City') or False
			vals['zip']	= BillAddr.get('PostalCode') or False
			vals['street'] = BillAddr.get('Line1') or False
			vals['street2'] = BillAddr.get('Line2') or False
			if BillAddr.get('CountrySubDivisionCode'):
				country = self.env['res.country'].search([('code','=',BillAddr.get('CountrySubDivisionCode'))],limit=1)
				if country:
					vals['country_id'] = country.id
					if BillAddr.get('CountrySubDivisionCode'):
						state = self.env['res.country.state'].search([('code','=',BillAddr.get('CountrySubDivisionCode')),
						('country_id','=',country.id)],limit=1)
						if state:
							vals['state_id'] = state.id
						else:
							dic ={
								'country_id':country.id,
								'code': BillAddr['CountrySubDivisionCode'],
								'name':BillAddr['CountrySubDivisionCode']
								}
							stateObj = self.env['res.country.state'].create(dic)
							vals['state_id'] = stateObj.id
		return vals

	def import_get_specific_vendor(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.partner']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id),
		('partner_type','=','vendor')]
		vendor = False
		find = mapping.search(domain,limit=1)
		if find:
			vendor = find.odoo_id
		else:
			query = "WHERE Id='%s'"%quickbook_id
			self.import_get_vendor(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				vendor = find.odoo_id
		return vendor
