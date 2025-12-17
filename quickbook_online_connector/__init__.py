# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from . import models
from . import controllers
from . import wizard

def pre_init_check(cr):
	from odoo.service import common
	from odoo.exceptions import UserError
	version_info = common.exp_version()
	server_serie = version_info.get('server_serie')
	if float(server_serie) != 19.0:
		raise UserError('Module support Odoo series 19.0 found {}.'.format(server_serie))
