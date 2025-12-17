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



class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def qbo_export_data(self):
        # _logger.info("++++++++++++Action Server Purchase Order+++++++++:%r",self)
        model = self.env['quickbookonline.manual.synchronisation']
        to_export_id = self.ids
        vals = {
            'object_type' : 'purchase_order',
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


class QuickBookOnlinePurchaseOrderFun(models.TransientModel):
    _inherit = 'quickbookonline.synchronization'

    def export_sync_purchase_order_data(self,connection, instance_id, to_export_id):
        mapping = self.env['quickbookonline.purchase.order']
        exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
        to_export_ids = self.env['purchase.order'].search([('id','not in',exported_ids),
        ('state','not in',['cancel']),('order_line','!=',False)])
        to_export_id = ast.literal_eval(to_export_id)
        ids_to_export = []
        export_ids = []
        for i in to_export_id:
            export_ids.append(self.env['purchase.order'].browse(i))
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
            for order_id in ids_to_export:
                response = self.export_online_purchase_order(connection, order_id, instance_id)
                if response.get('status'):
                    quickbook_id = response['quickbook_id']
                    order_id.doc_number = response['doc_number']
                    self.create_odoo_mapping('quickbookonline.purchase.order', order_id.id, quickbook_id, instance_id)
                    successfull_ids.append(order_id.id)
                else:
                    unsuccessfull_ids.append(str(order_id.id))
                    if response['message']:
                        msg += '<span>({}) {}</span><br>'.format(str(order_id.id), response['message'])
        except Exception as e:
            message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
        else:
            if successfull_ids:
                message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Purchase Orders SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
            if unsuccessfull_ids:
                message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Purchase Orders Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
        return message
