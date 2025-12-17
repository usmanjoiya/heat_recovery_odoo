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
	
	
	def import_import_payment(self,connection, instance_id, limit):
		TimeModified = connection.get('importPaymentTime')
		if TimeModified:
			query = "WHERE Metadata.CreateTime>'%s' OrderBy Metadata.CreateTime"%TimeModified
		else:
			query = 'OrderBy Metadata.CreateTime'
		message,TimeModified = self.import_get_payment(connection, instance_id, limit, query)
		if TimeModified:
			self.env['quickbookonline.instance'].browse(instance_id).importPaymentTime = TimeModified
		return message
	

	def import_get_payment(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from payment  %s MAXRESULTS %d"%(statement,limit)
		_logger.info("============================================query%r",query)
		payment_payment = self.env['account.payment']
		mapping = self.env['quickbookonline.payment']
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
			payments = response.get('Payment',[])
			success_ids = []
			for payment in payments:
				domain = [('instance_id','=',instance_id),
				('quickbook_id','=',payment['Id'])
				]
				TimeModified = payment['MetaData']['CreateTime']
				search = mapping.search(domain,limit=1)
				if not search:
					odoo_invoice_id = False
					vals = self.get_import_payment_vals(payment, connection, instance_id)
					_logger.info("=================================================payment%r",payment)
					LinkedLine = payment.get('Line',[])
					for lxl in LinkedLine:
						for check in lxl.get('LinkedTxn',[]):
							if check['TxnType'] == 'Invoice':
								invoice_quickbook_id = check['TxnId']
								odoo_invoice_id = self.import_get_specific_invoice(connection,invoice_quickbook_id, instance_id)
								if odoo_invoice_id:
									status, payment_id = self.set_order_paid(vals['journal_id'],odoo_invoice_id)
									if status:
										success_ids.append(self.create_odoo_mapping('quickbookonline.payment', payment_id, 
											payment['Id'], instance_id,{'created_by':'import'}))
					if not odoo_invoice_id:
						odoo_id = payment_payment.create(vals)
						success_ids.append(self.create_odoo_mapping('quickbookonline.payment', odoo_id.id, 
						payment['Id'], instance_id,{'created_by':'import'}))
			message += '{} Payments SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message,TimeModified

	def get_import_payment_vals(self, payment, connection, instance_id):
		vals = {
			'partner_id':self.import_get_specific_customer(connection, payment.get('CustomerRef',{}).get('value'), instance_id),
			'payment_type':'inbound',
			'partner_type':'customer',
			# 'payment_date':payment.get('TxnDate',False),
			'date':payment.get('TxnDate',False),
			'amount': payment.get('TotalAmt'),
			# 'payment_method_id':1,
			'journal_id':self.env['account.journal'].search([('type','in',['bank','cash'])],limit=1).id
		}
		method_id = payment.get('PaymentMethodRef',{}).get('value')
		if method_id:
			vals['journal_id'] = self.get_import_journal_id(method_id, instance_id)
			if not vals['journal_id']:
				raise Warning('Please Map All The Journals')
		vals['payment_method_id'] = self.get_default_payment_method(vals.get('journal_id'))
		return vals
	

	@api.model
	def set_order_paid(self, journalId,invoiceObj):
		ctx = dict(self.env.context or {})
		status = False
		payment_id = False
		try:
			if invoiceObj.state == 'posted':
				invoiceId = invoiceObj.id
			elif invoiceObj.state == 'draft':
				invoiceObj.action_post()
				invoiceId = invoiceObj.id
			# Setting Context for Payment Wizard
			register_wizard = self.env['account.payment.register'].with_context({
                    'active_model': 'account.move',
                    'active_ids': [invoiceId]
                })
			register_wizard_obj = register_wizard.create({
				'journal_id': journalId
			})
			payment_data = register_wizard_obj.action_create_payments()
			payment_id = payment_data.get('res_id')
			status = True
		except Exception as e:
			_logger.info("================Error While Creating Payment%r",str(e))
		return status,payment_id
	
	@api.model
	def get_default_payment_method(self, journalId):
		""" @params journal_id: Journal Id for making payment
				@params context : Must have key 'ecommerce' and then return payment payment method based on Odoo Bridge used else return the default payment method for Journal
				@return: Payment method ID(integer)"""
		paymentMethodObjs = self.env['account.journal'].browse(
			journalId)._default_inbound_payment_methods()
		if paymentMethodObjs:
			return paymentMethodObjs[0].id
		return False
	

	def get_import_journal_id(self, quickbook_id, instance_id):
		journal = self.env['quickbookonline.payment.method.map']
		domain = [('instance_id','=',instance_id),('quickbook_id','=',quickbook_id)]
		journal_id = journal.search(domain,limit=1)
		if journal_id:
			return journal_id.odoo_id
		return False
		
	def import_get_specific_payment(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.payment']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id)]
		payment = False
		find = mapping.search(domain,limit=1)
		if find:
			payment = find.name
		else:
			query = "WHERE Id='%s'"%quickbook_id
			self.import_get_payment(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				payment = find.name
		return payment
