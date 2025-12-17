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
	
	
	def import_import_partner(self,connection, instance_id, limit):
		TimeModified = connection.get('importCustomerTime')
		if TimeModified:
			query = "WHERE Metadata.LastUpdatedTime>='%s' OrderBy Metadata.LastUpdatedTime"%TimeModified
		else:
			query = 'OrderBy Metadata.LastUpdatedTime'
		message,TimeModified = self.import_get_partner(connection, instance_id, limit, query)
		if TimeModified:
			self.env['quickbookonline.instance'].browse(instance_id).importCustomerTime = TimeModified
		return message
	

	def import_get_partner(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from Customer %s MAXRESULTS %d"%(statement,limit)
		res_partner = self.env['res.partner']
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
			customers = response.get('Customer',[])
			success_ids = []
			for customer in customers:
				vals = self.get_import_customer_vals(customer, connection, instance_id)
				domain = [('instance_id','=',instance_id),
				('quickbook_id','=',customer['Id']),
				('partner_type','=','customer')]
				TimeModified = customer['MetaData']['LastUpdatedTime']
				search = mapping.search(domain,limit=1)
				if search:
					search.name.write(vals)
				else:
					odoo_id = res_partner.create(vals)
					success_ids.append(self.create_odoo_mapping('quickbookonline.partner', odoo_id.id, customer['Id'], instance_id,{'created_by':'import',
					'partner_type':'customer'}))
			message += '{} Partners SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message,TimeModified
	

	def get_import_customer_vals(self, customer, connection, instance_id):
		vals = {}
		ParentRef = customer.get('ParentRef',False)
		if ParentRef:
			odoo_id = self.import_get_specific_customer(connection,ParentRef['value'],instance_id)
			vals['parent_id'] = odoo_id
		vals['customer_rank'] = 1
		vals['name'] = customer.get('DisplayName')
		vals['phone'] = customer.get('PrimaryPhone',{}).get('FreeFormNumber',False)
		vals['email'] = customer.get('PrimaryEmailAddr',{}).get('Address',False)
		vals['comment'] = customer.get('Notes') or False
		vals['vat'] = customer.get('ResaleNumber') or False
		if customer.get('BillAddr'):
			BillAddr = customer['BillAddr']
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

	def import_get_specific_customer(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.partner']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id),
		('partner_type','=','customer')]
		Customer = False
		find = mapping.search(domain,limit=1)
		if find:
			Customer = find.odoo_id
		else:
			query = "WHERE Id='%s'"%quickbook_id
			self.import_get_partner(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				Customer = find.odoo_id
		return Customer
