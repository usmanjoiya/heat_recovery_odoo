# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    doc_number = fields.Char(string='Qbo Doc Number')    