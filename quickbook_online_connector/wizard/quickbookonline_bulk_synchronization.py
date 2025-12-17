# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import api, fields, models
import logging
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

connection  = 'quickbookonline.instance'


class quickbookonlineBulkSynchronization(models.TransientModel):
	_name = 'quickbookonline.bulk.synchronisation'
	_description = "Quickbook Online Bulk Synchronization"


	@api.model
	def _get_object_type(self):
		storage_type = [
			('category','Product Category'),
			('account','Account'),
			('partner','Partner'),
			('product','Product'),
			('order','Sale Order'),
			('invoice','Account Invoice'),
			('bill','Bills'),
			('payment','Account Payment'),
			('vendor','Vendor(Supplier)'),
			('purchase_order','Purchase Order'),
		]
		return storage_type
	
	@api.model
	def _get_limit(self):
		limit = [
			('1',1),
			('10',10),
			('50',50),
			('100',100),
			('200',200),
			('300',300),
			('500',500),
			('1000',1000),
			('2000',2000),
		]
		return limit

	def _default_instance_name(self):
		return self.env[connection].search([], limit=1).id

	action = fields.Selection(
		selection =[('import', 'Import Data'), ('export', 'Export Data')], 
		string = 'Import/Export', 
		default = "export", 
		required = True,
		readonly = True,
		help = """Import Data: Import Data From Quickbook Online. Export Data:Export Data To Quickbook""")
	
	action_2 = fields.Selection(
		selection = [('sync', 'Export'), ('update', 'Update')], 
		string = 'Export/Update', 
		default = "sync", 
		required = True,
		readonly = True,
		help = """Export:Export Data. Update:Update Data""")
	
	action_3 = fields.Selection(
		selection = [('import', 'Import'), ('update', 'Update')], 
		string = 'Action', 
		default = "import", 
		required = True,
		readonly = True,
		help = """Import: Import Data. Update:Update Data""")

	instance_id = fields.Many2one(
		comodel_name = connection, 
		string = 'Instance Id', 
		default = lambda self: self._default_instance_name())
	
	object_type = fields.Selection(
		selection = '_get_object_type',
		string = "Operation"
		)
	limit = fields.Selection(
		selection = '_get_limit',
		string = 'Limit',
	)
	
	def start_action_quickbookonline_synchronization(self):
		self.ensure_one()
		if self.action=='export':
			action = self.action_2
		else:
			action = self.action_3
		method = "%s_%s_%s"%(self.action,action,self.object_type)
		quickbookonline_synchronization = self.env['quickbookonline.synchronization'].with_company(self.instance_id.company_id).with_context(quickbook='quickbook',
		instance_id = self.instance_id.id)
		message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>There is an issue while Synchronizing Data</div>'
		instance_id = self.instance_id.id
		connection = self.env['quickbookonline.instance']._create_quickbook_connection(instance_id)
		if hasattr(quickbookonline_synchronization,method):
			message = getattr(quickbookonline_synchronization,method)(connection, instance_id, int(self.limit))
		return self.env['quickbookonline.message.wizard'].generate_message(message)


