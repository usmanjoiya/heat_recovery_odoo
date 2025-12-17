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

class QuickBookOnlinepartner(models.TransientModel):
    _inherit = 'quickbookonline.synchronization'

    def export_sync_vendor_data(self,connection, instance_id, to_export_id):
        mapping = self.env['quickbookonline.partner']
        exported_ids = mapping.search([('instance_id','=',instance_id),
        ('partner_type','=','vendor')]).mapped('name').ids
        to_export_ids = self.env['res.partner'].with_context(res_partner_search_mode='supplier').search([('id','not in',exported_ids),
        ('name','not in',[False,'',' ']),('supplier_rank','=',1)])
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
                response = self.export_online_vendor(connection, partner_id, instance_id)
                if response.get('status'):
                    quickbook_id = response['quickbook_id']
                    self.create_odoo_mapping('quickbookonline.partner', partner_id.id, quickbook_id, instance_id,
                    {'partner_type':'vendor'})
                    successfull_ids.append(partner_id.id)
                else:
                    unsuccessfull_ids.append(str(partner_id.id))
                    if response['message']:
                        msg += '<span>({}) {}</span><br>'.format(str(partner_id.id), response['message'])
        except Exception as e:
            message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
        else:
            if successfull_ids:
                message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Vendors SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
            if unsuccessfull_ids:
                message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Vendors Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
        return message
