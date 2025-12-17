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
	
	
	def import_import_invoice(self,connection, instance_id, limit):
		TimeModified = connection.get('importInvoiceTime')
		if TimeModified:
			query = "WHERE Metadata.CreateTime>'%s' OrderBy Metadata.CreateTime"%TimeModified
		else:
			query = 'OrderBy Metadata.CreateTime'
		message,TimeModified = self.import_get_invoice(connection, instance_id, limit, query)
		if TimeModified:
			self.env['quickbookonline.instance'].browse(instance_id).importInvoiceTime = TimeModified
		return message
	

	def import_get_invoice(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from invoice  %s MAXRESULTS %d"%(statement,limit)
		_logger.info("============================================query%r",query)
		invoice_invoice = self.env['account.move']
		mapping = self.env['quickbookonline.invoice']
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
			invoices = response.get('Invoice',[])
			success_ids = []
			for invoice in invoices:
				domain = [('instance_id','=',instance_id),
				('quickbook_id','=',invoice['Id'])
				]
				TimeModified = invoice['MetaData']['CreateTime']
				search = mapping.search(domain,limit=1)
				sale_quickbook_id = False
				if not search:
					LinkedTxn =  invoice.get('LinkedTxn',[])
					for linked in LinkedTxn:
						if linked['TxnType'] == 'Estimate':
							sale_quickbook_id = linked['TxnId']
							sale_order = self.import_get_specific_order(connection, sale_quickbook_id, instance_id)
							if sale_order:
								status, invoiceId = self.create_order_invoice(sale_order)
								if status:
									success_ids.append(self.create_odoo_mapping('quickbookonline.invoice', invoiceId, 
										invoice['Id'], instance_id,{'created_by':'import'}))
					if not sale_quickbook_id:
						invoice_line_vals = self.createImportInvoiceLines(invoice, connection, instance_id)
						vals = self.get_import_invoice_vals(invoice, connection, instance_id)
						if invoice_line_vals:
							vals.update({'invoice_line_ids':invoice_line_vals})
						odoo_id = invoice_invoice.create(vals)
						success_ids.append(self.create_odoo_mapping('quickbookonline.invoice', odoo_id.id, 
						invoice['Id'], instance_id,{'created_by':'import'}).id)
			message += '{} Invoices SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message,TimeModified
	
	@api.model
	def create_order_invoice(self, saleObj):
		invoice_id = False
		status = False
		try:
			invoiceId = saleObj.invoice_ids
			if saleObj.state == 'draft':
				saleObj.action_confirm()
			if not invoiceId:
				invoiceId = saleObj._create_invoices()
			elif len(invoiceId)>1:
				invoiceId = invoiceId[0]
			if invoiceId:
				invoice_id = invoiceId.id
			status = True
		except:
			pass
		return status, invoice_id

	def get_import_invoice_vals(self, invoice, connection, instance_id):
		vals = {}
		vals = {
				'currency_id':connection.get('default_pricelist_id').currency_id.id if connection.get('default_pricelist_id') else False,
				'team_id': connection.get('default_sales_team').id,
				'invoice_user_id':connection.get('default_sales_user').id,
				'move_type':'out_invoice',
				'invoice_date_due': invoice.get('DueDate',False),
				'invoice_date': invoice['TxnDate']
		}
		vals['partner_id'] = self.import_get_specific_customer(connection, invoice.get('CustomerRef',{}).get('value'), instance_id)
		vals['doc_number'] = invoice['DocNumber']
		journal_id=self.env['account.journal'].search([('type','=','sale')])
		if not journal_id:
			_logger.warning('Please create journal of type sale ..')
			raise Warning('Please create journal of type sale ..')
		SalesTermRef = invoice.get('SalesTermRef',{}).get('value')
		if SalesTermRef:
			odoo_id = self.get_import_payment_term_id(SalesTermRef, instance_id)
			if odoo_id:
				vals['invoice_payment_term_id'] = odoo_id
		return vals


	def createImportInvoiceLines(self, invoice, connection, instance_id):
		tax_id = []
		if connection.get('apply_tax_after_discount') != invoice.get('ApplyTaxAfterDiscount'):
			_logger.error("ApplyTaxAfterDiscount is not Match at the QuickBook End")
		invoiceLines = invoice.get('Line',[])
		TaxLines = invoice.get('TxnTaxDetail',{}).get('TaxLine',[])
		for TaxLine in TaxLines:
			tax = self.get_online_import_tax(TaxLine['TaxLineDetail']['TaxRateRef']['value'],instance_id)
			if tax:
				tax_id.append(tax)
		data=[]
		discount = False
		discountLineDetail = invoiceLines[-1]
		if discountLineDetail.get('DetailType') == 'DiscountLineDetail':
			if connection.get('apply_tax_after_discount') and discountLineDetail.get('DiscountLineDetail',{}).get('PercentBased'):
				discount = discountLineDetail.get('DiscountLineDetail',{}).get('DiscountPercent',0)
		for line in invoiceLines:
			vals = {}
			if line['DetailType'] in ['SalesItemLineDetail','DiscountLineDetail']:
				if line['DetailType'] == 'DiscountLineDetail':
					if discount:
						continue
					else:
						if line.get('Amount'):
							vals.update(self.get_discount_product(instance_id))
							vals.pop('product_uom',False)
							vals['tax_ids'] = False
							price_unit = -float(line.get('Amount'))
							quantity = 1.0
							description =  line.get('DiscountLineDetail',{}).get('name') or 'Discount Applied On Invoice'
				# Tax will be applied on invoice discount line when ApplyTaxAfterDiscount willl be True
				# It should be discount after tax in quickbook
							if tax_id and invoice.get('ApplyTaxAfterDiscount'):
								vals['tax_ids'] = [(6, 0, tax_id)]
						else:
							continue

				else:
					product_id = self.import_get_specific_product(connection,line['SalesItemLineDetail']['ItemRef']['value'],instance_id)
					vals['product_id'] = product_id
					vals['tax_ids'] = False
					price_unit = float(line.get('SalesItemLineDetail',{}).get('UnitPrice',1))
					quantity = float(line.get('SalesItemLineDetail',{}).get('Qty',1))
					description =  line.get('Description')
					code_ref = line.get('SalesItemLineDetail',{}).get('TaxCodeRef',{}).get('value')
					# NON: Tax is not applied to this line
					if not code_ref == "NON" and tax_id:
						vals['tax_ids'] = [(6, 0, tax_id)]
					if connection.get('apply_tax_after_discount') and discount:
						vals['discount'] = discount
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

		
	def import_get_specific_invoice(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.invoice']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id)]
		invoice = False
		find = mapping.search(domain,limit=1)
		if find:
			invoice = find.name
		else:
			query = "WHERE Id='%s'"%quickbook_id
			self.import_get_invoice(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				invoice = find.name
		return invoice
