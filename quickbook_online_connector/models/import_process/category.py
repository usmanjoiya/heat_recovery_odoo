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
	
	
	def import_import_category(self,connection, instance_id, limit):
		TimeModified = connection.get('importCategoryTime')
		if TimeModified:
			query = "AND Metadata.LastUpdatedTime>='%s' OrderBy Metadata.LastUpdatedTime"%TimeModified
		else:
			query = 'OrderBy Metadata.LastUpdatedTime'
		message,TimeModified = self.import_get_category(connection, instance_id, limit, query)
		if TimeModified:
			self.env['quickbookonline.instance'].browse(instance_id).importCategoryTime = TimeModified
		return message
	

	def import_get_category(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from Item where Type='Category' %s MAXRESULTS %d"%(statement,limit)
		product_category = self.env['product.category']
		mapping = self.env['quickbookonline.category']
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
			Categories = response.get('Item',[])
			success_ids = []
			for category in Categories:
				ParentRef = category.get('ParentRef',False)
				vals={'name':category['Name']}
				if ParentRef:
					odoo_id = self.import_get_specific_cateory(connection,ParentRef['value'],instance_id)
					vals['parent_id'] = odoo_id
				domain = [('instance_id','=',instance_id),
				('quickbook_id','=',category['Id'])]
				TimeModified = category['MetaData']['LastUpdatedTime']
				search = mapping.search(domain,limit=1)
				if search:
					search.name.write(vals)
				else:
					odoo_id = product_category.create(vals)
					success_ids.append(self.create_odoo_mapping('quickbookonline.category', odoo_id.id, category['Id'], instance_id,{'created_by':'import'}))
			message += '{} Categories SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message,TimeModified



	def import_get_specific_cateory(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.category']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id)]
		category = False
		find = mapping.search(domain,limit=1)
		if find:
			category = find.odoo_id
		else:
			query = "AND Id='%s'"%quickbook_id
			self.import_get_category(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				category = find.odoo_id
		return category
