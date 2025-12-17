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



class AccountPayment(models.Model):
    _inherit = 'product.category'

    def qbo_export_data(self):
        model = self.env['quickbookonline.manual.synchronisation']
        to_export_id = self.ids
        vals = {
            'object_type' : 'category',
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

class QuickBookOnlineCategoryFun(models.TransientModel):
    _inherit = 'quickbookonline.synchronization'

    def export_sync_category_data(self,connection, instance_id, to_export_id):
        mapping = self.env['quickbookonline.category']
        exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
        to_export_ids = self.env['product.category'].search([('id','not in',exported_ids)])
        successfull_ids, unsuccessfull_ids = [],[]
        to_export_id = ast.literal_eval(to_export_id)
        ids_to_export = []
        export_ids = []
        for i in to_export_id:
            export_ids.append(self.env['product.category'].browse(i))
        for i in export_ids:
            if i in to_export_ids:
                ids_to_export.append(i)
        msg = ''
        message = ''
        if not ids_to_export:
            message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Warning</h3><hr>Message : Already mapped. So, Nothing To Export</div>'
        if not to_export_ids.ids and ids_to_export:
            message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
        try:
            for category_id in ids_to_export:
                response = self.export_online_category(connection, category_id, instance_id)
                if response.get('status'):
                    quickbook_id = response['quickbook_id']
                    self.create_odoo_mapping('quickbookonline.category', category_id.id, quickbook_id, instance_id)
                    successfull_ids.append(category_id.id)
                else:
                    unsuccessfull_ids.append(str(category_id.id))
                    if response['message']:
                        msg += '<span>({}) {}</span><br>'.format(str(category_id.id), response['message'])
        except Exception as e:
             message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
        else:
            if successfull_ids:
                message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Categorie SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
            if unsuccessfull_ids:
                message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Categories Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
        return message
