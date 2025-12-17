# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, fields, models
import logging
_logger = logging.getLogger(__name__)



class QuickbookOnlineBill(models.Model):
    _inherit = 'quickbookonline.common'
    _name = 'quickbookonline.bill'
    _description = 'QuickBookOnline Bills'
    
    
    name = fields.Many2one(comodel_name= 'account.move',string='Name')
    
class Invoice(models.Model):
    _inherit = "account.move"

    def unlink(self):
        result = super(Invoice,self).unlink()
        odoo_id = []
        for rec in self:
            odoo_id.append(self.env['quickbookonline.bill'].search([('odoo_id','=',rec.id)]))
        if len(odoo_id)>0:
            for rec in odoo_id:
                rec.unlink()
        return result
