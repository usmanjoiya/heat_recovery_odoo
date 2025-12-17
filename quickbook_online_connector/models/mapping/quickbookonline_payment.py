# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models



class QuickbookOnlinePayment(models.Model):
    _inherit = 'quickbookonline.common'
    _name = 'quickbookonline.payment'
    _description = "QBO Payment Mapping"
    
    name = fields.Many2one(comodel_name= 'account.payment',string='Name')


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def unlink(self):
        result = super(AccountPayment,self).unlink()
        odoo_id = []
        for rec in self:
            odoo_id.append(self.env['quickbookonline.payment'].search([('odoo_id','=',rec.id)]))
        if len(odoo_id)>0:
            for rec in odoo_id:
                rec.unlink()
        return result
