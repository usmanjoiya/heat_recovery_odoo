# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)

class AccountAccount(models.Model):
	_inherit = 'account.account'

	is_quickbook = fields.Boolean(string='Is Quickbook', default = False)
