# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)


class QuickbookOnlineMessageWizard(models.TransientModel):
	_name = "quickbookonline.message.wizard"
	_description = "Message Wizard For Quickbook Online View"
	
	text = fields.Html(string='Message', readonly=True, translate=True)

	def generate_message(self, message, name='Message/Summary'):
		partial_id = self.create({'text':message}).id
		return {
			'name':name,
			'view_mode': 'form',
			'view_id': False,
			'res_model': 'quickbookonline.message.wizard',
			'res_id': partial_id,
			'type': 'ir.actions.act_window',
			'nodestroy': True,
			'target': 'new',
			'domain': '[]',
		}
