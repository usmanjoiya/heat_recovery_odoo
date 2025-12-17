# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models



class QuickbookOnlineAccount(models.Model):
    _inherit = 'quickbookonline.common'
    _name = 'quickbookonline.account'
    _description = "QBO Account Mapping"
    
    name = fields.Many2one(comodel_name= 'account.account',string='Name')


class Account(models.Model):
    _inherit = "account.account"

    def unlink(self):
        result = super(Account,self).unlink()
        odoo_id = []
        for rec in self:
            odoo_id.append(self.env['quickbookonline.account'].search([('odoo_id','=',rec.id)]))
        if len(odoo_id)>0:
            for rec in odoo_id:
                rec.unlink()
        return result