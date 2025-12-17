# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models



class QuickbookOnlineOrder(models.Model):
    _inherit = 'quickbookonline.common'
    _name = 'quickbookonline.purchase.order'
    _description = "QBO Payment Term Mapping"
    
    name = fields.Many2one(comodel_name= 'purchase.order',string='Name')


class Purchase(models.Model):
    _inherit = "purchase.order"

    def unlink(self):
        result = super(Purchase,self).unlink()
        odoo_id = []
        for rec in self:
            odoo_id.append(self.env['quickbookonline.purchase.order'].search([('odoo_id','=',rec.id)]))
        if len(odoo_id)>0:
            for rec in odoo_id:
                rec.unlink()
        return result