# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models


class QuickbookOnlineCommon(models.Model):
	_name = 'quickbookonline.common'
	_description = 'This model is for storing mapping of data'

	def _default_instance_name(self):
		return self.env['quickbookonline.instance'].search([], limit=1).id
	
	odoo_id = fields.Integer(string = 'Odoo Id')
	quickbook_id = fields.Char(string = 'Quickbook Id')
	is_sync = fields.Selection([('yes','Yes'),('no','No')], default = 'no', string = 'Update Required')
	instance_id = fields.Many2one(comodel_name = 'quickbookonline.instance',
		string = 'Instance Id',
		default = lambda self: self._default_instance_name())
	created_by = fields.Char(string="Created By", default="export")