# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, api, fields, models
import requests, json



class QuickbookDesktopPaymentTermMap(models.Model):
	_inherit = 'quickbookonline.common'
	_name = 'quickbookonline.payment.term.map'
	_description = "QBO Payment Term Mapping Manual"
		

	name = fields.Many2one(comodel_name = 'account.payment.term',string = 'Name')
	quickbook_payment_term = fields.Many2one('quickbookonline.payment.term', string='Quickbook Payment Term')
	quickbook_id = fields.Char(related='quickbook_payment_term.quickbook_id')
	
	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if 'odoo_id' not in vals and vals.get('name'):
				vals['odoo_id'] = vals['name']
		return super(QuickbookDesktopPaymentTermMap,self).create(vals_list)
