# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self,vals):
        mapping = self.env['quickbookonline.partner']
        if self and 'quickbook' not in self.env.context:
            mapping.search([('name','in',self.ids)]).is_sync = 'yes'
        return super(ResPartner,self).write(vals)
