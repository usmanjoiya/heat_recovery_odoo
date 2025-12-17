# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models



class QuickbookOnlineProduct(models.Model):
    _inherit = 'quickbookonline.common'
    _name = 'quickbookonline.product'
    _description = "QBO Product Mapping"
    
    name = fields.Many2one(comodel_name= 'product.product',string='Name')


class ProductProduct(models.Model):
    _inherit = "product.product"

    def unlink(self):
        result = super(ProductProduct,self).unlink()
        odoo_id = []
        for rec in self:
            odoo_id.append(self.env['quickbookonline.product'].search([('odoo_id','=',rec.id)]))
        if len(odoo_id)>0:
            for rec in odoo_id:
                rec.unlink()
        return result