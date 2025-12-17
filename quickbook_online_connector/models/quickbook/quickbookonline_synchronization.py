# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, api, models
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class QuickBookOnlineSynchronization(models.TransientModel):
	_name = 'quickbookonline.synchronization'
	_description = 'Transient Model For QuickBookonline Synchronization'

	@api.model
	def sync_data_of_quickbook(self,operation,getLimit,action='export'):
		bulk_synchronization = self.env['quickbookonline.bulk.synchronisation']
		instances = self.env['quickbookonline.instance'].search([])
		for instance in instances:
			limit = getattr(instance,getLimit)
			val = operation+'_'+action+'_cron'
			opr = getattr(instance,val)
			# _logger.info("========sync_data_of_quickbook opr:%r",opr)
			vals = {
				'action':action,
				'instance_id':instance.id,
				'object_type':operation,
				'limit':limit
			}
			if opr:
				sync = bulk_synchronization.create(vals)
				sync.start_action_quickbookonline_synchronization()
			else:
				_logger.error('Cron: {} {} cron is not enabled for quickbook instance'.format(action, operation))
		return True	
	
	
	def export_synchronisation(self):
		vals = {'limit':'1'}
		partial_id = self.env['quickbookonline.bulk.synchronisation'].create(vals)
		return {
			'name':'Quickbook Online Bulk Synchronizaion',
			'view_mode': 'form',
			'view_id': False,
			'res_model': 'quickbookonline.bulk.synchronisation',
			'res_id': partial_id.id,
			'type': 'ir.actions.act_window',
			'nodestroy': True,
			'target': 'new',
			'domain': '[]',
		}
	
	def import_synchronization(self):
		vals = {'action':'import',
		'limit':'1'}
		partial_id = self.env['quickbookonline.bulk.synchronisation'].create(vals)
		return {
			'name':'Quickbook Online Bulk Synchronizaion',
			'view_mode': 'form',
			'view_id': False,
			'res_model': 'quickbookonline.bulk.synchronisation',
			'res_id': partial_id.id,
			'type': 'ir.actions.act_window',
			'nodestroy': True,
			'target': 'new',
			'domain': '[]',
		} 
	

	def create_odoo_mapping(self, model , odoo_id, quickbook_id, instance_id, extra_data = {}):
		'''This function is use to create Odoo mapping
		@params
			response data --> dictionary of values
			storage_type --> storage type
			model --> model to create mappings like sale.order,res.partner
		@returns 
		newly created model obj
		'''
		vals = {
			'odoo_id':odoo_id,
			'quickbook_id':quickbook_id,
			'name': odoo_id,
			'instance_id':instance_id
		}
		if extra_data:
			vals.update(extra_data)
		res = self.env[model].create(vals)
		return res
	

	def reset_mapping(self):
		message_wizard = self.env['quickbookonline.message.wizard']
		models = [
			'quickbookonline.account',
			'quickbookonline.partner',
			'quickbookonline.payment.term.map',
			'quickbookonline.payment.method.map',
			'quickbookonline.tax',
			'quickbookonline.payment',
			'quickbookonline.invoice',
			'quickbookonline.account',
			'quickbookonline.product',
			'quickbookonline.order',
			'quickbookonline.purchase.order',
			'quickbookonline.category'
		]
		message = '<div class="alert alert-success" role="alert">SuccessFully Deleted.</div>'
		try:
			for model in models:
				ids = self.env[model].search([])
				ids.unlink()
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message_wizard.generate_message(message)

	def match_odoo_product(self, sku):
		if sku:
			product_id = self.env['product.product'].search([('default_code','=',sku)], limit=1)
			if product_id:
				return product_id
		return False
