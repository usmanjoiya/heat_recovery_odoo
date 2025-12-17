# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models


class QuickbookOnlinePaymentMethod(models.Model):
	_name = 'quickbookonline.payment.method'
	_description = "QBO Payment Method Mapping"

	def _default_instance_name(self):
		return self.env['quickbookonline.instance'].search([], limit=1).id
	
	quickbook_id = fields.Char(string = 'Quickbook Id')
	instance_id = fields.Many2one(comodel_name = 'quickbookonline.instance',
		string = 'Instance Id',
		default = lambda self: self._default_instance_name())
	name = fields.Char('Name')
	payment_type = fields.Char('Type')	