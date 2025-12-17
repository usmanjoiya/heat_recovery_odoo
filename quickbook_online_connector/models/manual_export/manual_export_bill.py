# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import _, models
import ast


class QuickBookOnlineBillFun(models.TransientModel):
    _inherit = 'quickbookonline.synchronization'

    def export_sync_bill_data(self,connection, instance_id, to_export_id):
        message = ''
        mapping = self.env['quickbookonline.bill']
        exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
        to_export_ids = self.env['account.move'].search([('id','not in',exported_ids),
        ('state','not in',['cancel','draft']),('move_type','=','in_invoice')])
        to_export_id = ast.literal_eval(to_export_id)
        mapped_ids = list(filter(lambda x: x in exported_ids, to_export_id)) or False
        if not to_export_ids.ids:
            message = '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Warning</h3><hr>Message : Nothing To Export</div>' 
        if mapped_ids:
            message = '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Warning</h3><hr>Message : {} Bills already mapped, Ids : {}.</div>'.format(len(mapped_ids), mapped_ids)
        ids_to_export = []
        export_ids = []
        for i in to_export_id:
            export_ids.append(self.env['account.move'].browse(i))
        for i in export_ids:
            if i in to_export_ids:
                ids_to_export.append(i)
        successfull_ids, unsuccessfull_ids = [],[]
        msg = ''
       
        try:
            for invoice_id in ids_to_export:
                response = self.export_online_bill(connection, invoice_id, instance_id)
                if response.get('status'):
                    quickbook_id = response['quickbook_id']
                    invoice_id.doc_number = response['doc_number']
                    self.create_odoo_mapping('quickbookonline.bill', invoice_id.id, quickbook_id, instance_id)
                    successfull_ids.append(invoice_id.id)
                else:
                    unsuccessfull_ids.append(str(invoice_id.id))
                    if response['message']:
                        msg += '<span>({}) {}</span><br>'.format(str(invoice_id.id), response['message'])
        except Exception as e:
            message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
        else:
            if successfull_ids:
                message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Bills SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
            if unsuccessfull_ids:
                message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Bills Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
        return message
