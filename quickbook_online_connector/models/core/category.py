# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    def write(self,vals):
        mapping = self.env['quickbookonline.category']
        if self and 'quickbook' not in self.env.context:
            mapping.search([('name','in',self.ids)]).is_sync = 'yes'
        return super(ProductCategory,self).write(vals)
