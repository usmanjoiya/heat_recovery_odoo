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



class QuickbookDesktopPaymentMethodMap(models.Model):
	_inherit = 'quickbookonline.common'
	_name = 'quickbookonline.payment.method.map'
	_description = "QBO Payment Method Mapping Manual"
		

	name = fields.Many2one(comodel_name = 'account.journal',string = 'Odoo Journal')
	quickbook_payment_method = fields.Many2one('quickbookonline.payment.method', string='Quickbook Payment Method')
	quickbook_id = fields.Char(related='quickbook_payment_method.quickbook_id')
	
	@api.onchange('name')
	def change_odoo_id(self):
		for rec in self:
			rec.odoo_id = rec.name.id

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if 'odoo_id' not in vals and vals.get('name'):
				vals['odoo_id'] = vals['name']
		return super(QuickbookDesktopPaymentMethodMap,self).create(vals_list)
