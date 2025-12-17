# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import fields, api, models
import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
	_inherit = 'account.move'

	doc_number = fields.Char(string='Qbo Doc Number')



	@api.model_create_multi
	def create(self,vals_list):
		# _logger.info("=================================vals%r",vals)
		return super().create(vals_list)    
