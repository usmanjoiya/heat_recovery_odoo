# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def write(self,vals):
        mapping = self.env['quickbookonline.product']
        if self and 'quickbook' not in self.env.context:
            mapping.search([('name','in',self.ids)]).is_sync = 'yes'
        return super(ProductProduct,self).write(vals)
