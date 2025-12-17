# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models



class QuickbookOnlinePartner(models.Model):
    _inherit = 'quickbookonline.common'
    _name = 'quickbookonline.partner'
    _description = "QBO Partner Mapping"


    name = fields.Many2one(comodel_name = 'res.partner',string = 'Name')
    partner_type = fields.Selection([('customer','Customer'),('vendor','Vendor')], default = 'customer', string = 'Partner Type')


class Customer(models.Model):
    _inherit = "res.partner"

    def unlink(self):
        result = super(Customer,self).unlink()
        odoo_id = []
        for rec in self:
            odoo_id.append(self.env['quickbookonline.partner'].search([('odoo_id','=',rec.id)]))
        if len(odoo_id)>0:
            for rec in odoo_id:
                rec.unlink()
        return result