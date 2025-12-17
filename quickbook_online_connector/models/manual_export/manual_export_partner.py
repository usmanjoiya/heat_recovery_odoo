# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, models
import logging, ast
_logger = logging.getLogger(__name__)



class ResPartner(models.Model):
    _inherit = 'res.partner'

    def qbo_export_data(self):
        model = self.env['quickbookonline.manual.synchronisation']
        to_export_id = self.ids
        check = self[0]
        for rec in self:
            _logger.info("=============export_data ResPartner Method called rec.read:%r",rec.customer_rank)
            _logger.info("=============export_data ResPartner Method called rec.read:%r",rec.supplier_rank)
        if check.supplier_rank:
            vals = {
                'object_type' : 'vendor',
                'to_export_ids' : to_export_id,
            }
            new = model.create(vals)
            return {
                'name':'Select Instance',
                'view_mode': 'form',
                'res_model': 'quickbookonline.manual.synchronisation',
                'res_id': new.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        else:
            vals = {
                'object_type' : 'partner',
                'to_export_ids' : to_export_id,
            }
            new = model.create(vals)
            return {
                'name':'Select Instance',
                'view_mode': 'form',
                'res_model': 'quickbookonline.manual.synchronisation',
                'res_id': new.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }

class QuickBookOnlinePartnerFun(models.TransientModel):
    _inherit = 'quickbookonline.synchronization'

    def export_sync_partner_data(self,connection, instance_id, to_export_id):
        mapping = self.env['quickbookonline.partner']
        exported_ids = mapping.search([('instance_id','=',instance_id),
        ('partner_type','=','customer')]).mapped('name').ids
        to_export_ids = self.env['res.partner'].with_context(res_partner_search_mode='customer').search([('id','not in',exported_ids),
        ('name','not in',[False,'',' ']),('customer_rank','=',1)])
        to_export_id = ast.literal_eval(to_export_id)
        ids_to_export = []
        export_ids = []
        for i in to_export_id:
            export_ids.append(self.env['res.partner'].browse(i))
        for i in export_ids:
            if i in to_export_ids:
                ids_to_export.append(i)
        successfull_ids, unsuccessfull_ids = [],[]
        msg = ''
        message = ''
        if not ids_to_export:
            message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Warning</h3><hr>Message : Already mapped. So, Nothing To Export</div>'
        if not to_export_ids.ids and ids_to_export:
            message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
        try:
            for partner_id in ids_to_export:
                response = self.export_online_partner(connection, partner_id, instance_id)
                if response.get('status'):
                    quickbook_id = response['quickbook_id']
                    self.create_odoo_mapping('quickbookonline.partner', partner_id.id, quickbook_id, instance_id)
                    successfull_ids.append(partner_id.id)
                else:
                    unsuccessfull_ids.append(str(partner_id.id))
                    if response['message']:
                        msg += '<span>({}) {}</span><br>'.format(str(partner_id.id), response['message'])
        except Exception as e:
            message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
        else:
            if successfull_ids:
                message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Customers SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
            if unsuccessfull_ids:
                message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Customers Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
        return message
