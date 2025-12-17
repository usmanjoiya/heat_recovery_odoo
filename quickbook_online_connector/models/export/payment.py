# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
import json
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)


class QuickBookOnlineAccount(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'

	def export_sync_payment(self,connection, instance_id, limit):
		mapping = self.env['quickbookonline.payment']
		exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
		to_export_ids = self.env['account.payment'].search([('id','not in',exported_ids),
		('state','!=','cancelled'),('payment_type','=','inbound'),('partner_type','=','customer')],limit=limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		if not to_export_ids.ids:
			message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
		try:
			for order_id in to_export_ids:
				response = self.export_online_payment(connection, order_id, instance_id)
				if response.get('status'):
					quickbook_id = response['quickbook_id']
					self.create_odoo_mapping('quickbookonline.payment', order_id.id, quickbook_id, instance_id)
					successfull_ids.append(order_id.id)
				else:
					unsuccessfull_ids.append(str(order_id.id))
					if response['message']:
						msg += '<span>({}) {}</span><br>'.format(str(order_id.id), response['message'])
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		else:
			if successfull_ids:
				message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Payments SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
			if unsuccessfull_ids:
				message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Payments Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def get_export_payment_schema(self, connection, payment, instance_id):
		schema = {
			'TotalAmt': payment.amount or 0,
			'UnappliedAmt':0,
			'PaymentRefNum':payment.name,
			'CustomerRef':{'value':self.check_online_specific_partner(connection,payment.partner_id, instance_id)},
		}
		if payment.date:
			schema['TxnDate'] =  payment.date.strftime("%Y-%m-%d")
		if payment.journal_id:
			quickbook_id = self.get_quickbook_payment_method(payment.journal_id,instance_id)
			if not quickbook_id:
				self.env.cr.commit()
				raise UserError('Please Map Following Journal To Quickbook Payment Method(%s)'%payment.journal_id.name)
			schema['PaymentMethodRef'] = {
				'value':str(quickbook_id)
			}

		if payment.memo:
			invoice_id = self.env['account.move'].search([('name','=',payment.memo)],limit=1)
			if invoice_id:
				invoice_quickbook_id = self.check_online_specific_invoice(connection,invoice_id,instance_id)
				if invoice_quickbook_id:
					schema['Line'] = [{
						'Amount':payment.amount or 0,
						'LinkedTxn':[{
							'TxnId':str(invoice_quickbook_id),
							'TxnType':'Invoice'
						}]
					}]
		_logger.info("=====================================schema%r",[schema,payment])
		return schema

	def get_quickbook_payment_method(self, journal_id, instance_id):
		quickbook_id = ''
		domain = [('name','=',journal_id.id),('instance_id','=',instance_id)]
		search = self.env['quickbookonline.payment.method.map'].search(domain,limit=1)
		if search:
			quickbook_id =search.quickbook_id
		return quickbook_id

	def export_online_payment(self,connection,order_id, instance_id):
		status = False
		url = connection.get('url')
		access_token = connection.get('access_token')
		client = self.env['call.quickbook.api']
		quickbook_id = ''
		message = 'SuccessFully Exported'
		if url and access_token:
			headers = {
				'Content-type':'application/json',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			url+= 'payment?minorversion=75'			
			schema = self.get_export_payment_schema(connection, order_id, instance_id)
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				quickbook_id =  response.get('Payment')['Id']
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'quickbook_id':quickbook_id,
			'message':message
		}
	

	def check_online_specific_payment(self, connection, order_id, instance_id):
		mapping = self.env['quickbookonline.payment']
		domain = [('instance_id','=',instance_id),
		('name','=',order_id.id)]
		search = mapping.search(domain,limit=1)
		quickbook_id = False
		if search:
			quickbook_id = search.quickbook_id
		else:
			response = self.export_online_payment(connection, order_id, instance_id)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.payment', order_id.id, quickbook_id, instance_id)
		return quickbook_id
		
