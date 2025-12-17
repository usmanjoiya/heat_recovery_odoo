# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
import json


class QuickBookOnlineAccount(models.TransientModel):
    _inherit = 'quickbookonline.synchronization'
    
    def export_sync_bill(self,connection, instance_id, limit):
        mapping = self.env['quickbookonline.bill']
        exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
        to_export_ids = self.env['account.move'].search([('id','not in',exported_ids),
		('state','not in',['cancel','draft']),('move_type','=','in_invoice')],limit=limit)
        successfull_ids, unsuccessfull_ids = [],[]
        msg = ''
        message = ''
        if not to_export_ids.ids:
            message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
        try:
            for invoice_id in to_export_ids:
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
	
    def get_bill_lines_schema(self, connection, move_invoice, instance_id):
        invoiceLines = []
        for invoiceLine in move_invoice.invoice_line_ids:  
            productName = self.check_online_specific_product(connection, invoiceLine.product_id, instance_id)
            tax_code = ''
            if connection.get('quickbook_account_code'):
                if invoiceLine.tax_ids:
                    tax_code = connection['quickbook_account_code'].name
            schema = {
            'Description': invoiceLine.name or '',
            'DetailType': 'ItemBasedExpenseLineDetail',
            'Amount':invoiceLine.quantity*invoiceLine.price_unit or 0
            }
            schema['ItemBasedExpenseLineDetail'] = {
                'Qty': invoiceLine.quantity or 0,
                'UnitPrice': invoiceLine.price_unit or 0,
                'ItemRef': {'value':productName}
            }
            if tax_code:
                schema['ItemBasedExpenseLineDetail']['TaxCodeRef'] = {'value':tax_code}
            else:
                schema['ItemBasedExpenseLineDetail']['TaxCodeRef'] = {'value':'NON'}
				
            invoiceLines.append(schema)
        return invoiceLines
	
    
    def get_export_bill_schema(self, connection, move_invoice, instance_id):
        schema = {}
        if move_invoice.partner_id and move_invoice.partner_id.parent_id:
            partner_id = move_invoice.partner_id.parent_id
        else:
            partner_id = move_invoice.partner_id
        schema = {
            'TotalAmt': move_invoice.amount_total or 0,
            'VendorRef':{'value':self.check_online_specific_vendor(connection,partner_id, instance_id)},
        }
        if move_invoice.invoice_date:
            schema['TxnDate'] =  move_invoice.invoice_date.strftime("%Y-%m-%d")
        if move_invoice.invoice_date_due:
            schema['DueDate'] = move_invoice.invoice_date_due.strftime("%Y-%m-%d")
        if move_invoice.invoice_origin:
            purchase_order = self.env['purchase.order'].search([('name','=',move_invoice.invoice_origin)],limit=1)
            if purchase_order:
                purchase_quickbook_id = self.check_online_specific_purchase_order(connection, purchase_order, instance_id)
                schema.update({
                    'LinkedTxn':[{
                        'TxnId':purchase_quickbook_id,
                        'TxnType':'PurchaseOrder'
                        }]})
          
        schema['DocNumber'] = str(move_invoice.name)
        if move_invoice.invoice_payment_term_id:
            SalesTermRef = self.get_sales_term_ref(move_invoice.invoice_payment_term_id, instance_id)
            if SalesTermRef:
                schema['SalesTermRef'] = {'value':SalesTermRef}
        schema['Line'] = self.get_bill_lines_schema(connection, move_invoice, instance_id)
        return schema
    
    
    def export_online_bill(self,connection,invoice_id, instance_id):
        status = False
        url = connection.get('url')
        access_token = connection.get('access_token')
        client = self.env['call.quickbook.api']
        quickbook_id = ''
        message = 'SuccessFully Exported'
        doc_number = ''
        if url and access_token:
            headers = {
                'Content-type':'application/json',
                'Accept': 'application/json',
                'Authorization':'Bearer %s'%access_token
            }
            url+= 'bill?minorversion=75'
            schema = self.get_export_bill_schema(connection, invoice_id, instance_id)
            try:
                response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
                quickbook_id =  response.get('Bill')['Id']
                doc_number = response['Bill']['DocNumber']
                status = True
            except Exception as e:
                message = str(e)
            return{
                'status':status,
                'quickbook_id':quickbook_id,
                'doc_number':doc_number,
                'message':message
            }
	

    def check_online_specific_bill(self, connection, invoice_id, instance_id):
        mapping = self.env['quickbookonline.bill']
        domain = [('instance_id','=',instance_id),
        ('name','=',invoice_id.id)]
        search = mapping.search(domain,limit=1)
        quickbook_id = False
        if search:
            quickbook_id = search.quickbook_id
        else:
            response = self.export_online_bill(connection, invoice_id, instance_id)
            if response.get('status'):
                quickbook_id = response['quickbook_id']
                self.create_odoo_mapping('quickbookonline.bill', invoice_id.id, quickbook_id, instance_id)
        return quickbook_id
		
