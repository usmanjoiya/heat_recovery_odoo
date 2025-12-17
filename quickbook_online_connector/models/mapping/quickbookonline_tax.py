# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models



class QuickbookOnlineTax(models.Model):
    _inherit = 'quickbookonline.common'
    _name = 'quickbookonline.tax'
    _description = "QBO Tax Mapping"
    
    name = fields.Many2one(comodel_name= 'account.tax',string='Name')

class Tax(models.Model):
    _inherit = "account.tax"

    def unlink(self):
        result = super(Tax,self).unlink()
        odoo_id = []
        for rec in self:
            odoo_id.append(self.env['quickbookonline.tax'].search([('odoo_id','=',rec.id)]))
        if len(odoo_id)>0:
            for rec in odoo_id:
                rec.unlink()
        return result