# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    doc_number = fields.Char(string='Qbo Doc Number')    