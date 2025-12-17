# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, api, models
import logging
_logger = logging.getLogger(__name__)


class quickbookonlineSynchronization(models.TransientModel):
    _inherit = 'quickbookonline.synchronization'

 
    def import_import_bill (self,connection, instance_id, limit):
        TimeModified = connection.get('importBillTime')
        if TimeModified:
            query = "WHERE Metadata.CreateTime>'%s' OrderBy Metadata.CreateTime"%TimeModified
        else:
            query = 'OrderBy Metadata.CreateTime'
        message,TimeModified = self.import_get_bill(connection, instance_id, limit, query)
        if TimeModified:
            self.env['quickbookonline.instance'].browse(instance_id).importBillTime = TimeModified
        return message
        
    def import_get_bill(self, connection, instance_id, limit, statement = 1):
        url = connection.get('url')
        query = "select * from bill  %s MAXRESULTS %d"%(statement,limit)
        bill_object = self.env['account.move']
        mapping = self.env['quickbookonline.bill']
        message = '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>'
        TimeModified = False
        client = self.env['call.quickbook.api']
        access_token = connection.get('access_token')
        try:
            headers = {
                'Content-type':'text/plain',
                'Accept': 'application/json',
                'Authorization':'Bearer %s'%access_token
            }
            response = client.get_query_object(url, query, headers,75)
            bills = response.get('Bill',[])
            success_ids = []
            for bill in bills:
                domain = [('instance_id','=',instance_id),
                ('quickbook_id','=',bill['Id'])
                ]
                TimeModified = bill['MetaData']['CreateTime']
                search = mapping.search(domain,limit=1)
                purchase_quickbook_id = False
                if not search:
                    LinkedTxn =  bill.get('LinkedTxn',[])
                    for linked in LinkedTxn:
                        if linked['TxnType'] == 'PurchaseOrder':
                            purchase_quickbook_id = linked['TxnId']
                            purchase_order = self.import_get_specific_purchase_order(connection, purchase_quickbook_id, instance_id)
                            if purchase_order:
                                status, billId = self.create_purchase_order_bill(purchase_order)
                                if status:
                                    success_ids.append(self.create_odoo_mapping('quickbookonline.bill', billId, bill['Id'], instance_id,{'created_by':'import'}).id)
                    if not purchase_quickbook_id:
                        bill_line_vals = self.createImportBillLines(bill, connection, instance_id)
                        vals = self.get_import_bill_vals(bill, connection, instance_id)
                        if bill_line_vals:
                            vals.update({'invoice_line_ids':bill_line_vals})
                            odoo_id = bill_object.create(vals)
                            success_ids.append(self.create_odoo_mapping('quickbookonline.bill', odoo_id.id, bill['Id'], instance_id,{'created_by':'import'}).id)
            message += '{} Bills SuccessFully Imported</div>'.format(len(success_ids))
        except Exception as e:
            message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
        return message,TimeModified
    
    @api.model
    def create_purchase_order_bill(self, purchaseObj):
        invoice_id = False
        status = False
        try:
            invoiceId = purchaseObj.invoice_ids
            if purchaseObj.state == 'draft':
                purchaseObj.button_confirm()
            if not invoiceId:
                invoiceId = purchaseObj.action_create_invoice()
            if invoiceId:
                invoice_id = invoiceId.get('res_id') or False
                status = True
        except:
            pass
        return status, invoice_id
    
    def get_import_bill_vals(self, bill, connection, instance_id):
        vals = {}
        vals = {
                'currency_id':connection.get('default_pricelist_id').currency_id.id if connection.get('default_pricelist_id') else False,
                'team_id': connection.get('default_sales_team').id,
                'invoice_user_id':connection.get('default_sales_user').id,
                'move_type':'in_invoice',
                'invoice_date_due': bill.get('DueDate',False),
                'invoice_date': bill['TxnDate']
        }
        vals['partner_id'] = self.import_get_specific_vendor(connection, bill.get('VendorRef',{}).get('value'), instance_id)
        vals['doc_number'] = bill.get('DocNumber')
        journal_id=self.env['account.journal'].search([('type','=','purchase')])
        if not journal_id:
            _logger.warning('Please create journal of type purchase ..')
            raise Warning('Please create journal of type purchase ..')
        SalesTermRef = bill.get('SalesTermRef',{}).get('value')
        if SalesTermRef:
            odoo_id = self.get_import_payment_term_id(SalesTermRef, instance_id)
            if odoo_id:
                vals['invoice_payment_term_id'] = odoo_id
        return vals

    
    def createImportBillLines(self, bill, connection, instance_id):
        tax_id = []
        billLines = bill.get('Line',[])
        TaxLines = bill.get('TxnTaxDetail',{}).get('TaxLine',[])
        if TaxLines:
            for TaxLine in TaxLines:
                tax = self.get_online_import_tax(TaxLine['TaxLineDetail']['TaxRateRef']['value'],instance_id)
                if tax:
                    tax_id.append(tax)
        data=[]
        for line in billLines:
            vals = {}
            if line['DetailType'] in ['ItemBasedExpenseLineDetail']:
                product_id = self.import_get_specific_product(connection,line['ItemBasedExpenseLineDetail']['ItemRef']['value'],instance_id)
                vals['product_id'] = product_id
                vals['tax_ids'] = False
                price_unit = float(line.get('ItemBasedExpenseLineDetail',{}).get('UnitPrice',1))
                quantity = float(line.get('ItemBasedExpenseLineDetail',{}).get('Qty',1))
                description =  line.get('Description')
                code_ref = line.get('ItemBasedExpenseLineDetail',{}).get('TaxCodeRef',{}).get('value')
				# NON: Tax is not applied to this line
                if not code_ref == "NON" and tax_id:
                    vals['tax_ids'] = [(6, 0, tax_id)]

                vals['price_unit'] =float(price_unit)
                vals['name'] = description
                productObj = self.env['product.product'].browse(
					vals['product_id'])
                if productObj.property_account_income_id:
                    vals['account_id']= productObj.property_account_income_id.id
                elif productObj.categ_id.property_account_income_categ_id:
                    vals['account_id'] = productObj.categ_id.property_account_income_categ_id.id
                else:
                    vals['account_id']= connection.get('quickbook_income_account').id
                vals.update({'product_uom_id': productObj.uom_id.id})
                if not vals['name']:
                    vals['name'] = productObj.description if productObj.description else productObj.name
                if not vals['name']:
                    vals['name'] = 'invoice product'
                vals['quantity'] = quantity
                vals['display_type'] = "product"
                if vals['price_unit']:
                    if vals['price_unit']<0:
                        vals.update({'price_unit':price_unit})
                    else:
                        vals.update({'price_unit':price_unit})
                elif vals.get('tax_ids'):
                    vals['tax_base_amount'] = 0
                if vals:
                    data.append((0,0,vals))
        return data

		
    def import_get_specific_bill(self, connection, quickbook_id, instance_id):
        mapping = self.env['quickbookonline.bill']
        domain = [('quickbook_id','=',quickbook_id),
        ('instance_id','=',instance_id)]
        bill = False
        find = mapping.search(domain,limit=1)
        if find:
            bill = find.name
        else:
            query = "WHERE Id='%s'"%quickbook_id
            self.import_get_bill(connection,instance_id,1,query)
            find = mapping.search(domain,limit=1)
            if find:
                bill = find.name
        return bill
