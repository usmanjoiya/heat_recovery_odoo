# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
import json
_logger = logging.getLogger(__name__)

def get_quickbook_account_type(qb_account_type):
    return {
        'asset_cash': 'Bank', 
        'asset_receivable': 'Accounts Receivable', 
        'liability_payable': 'Accounts Payable', 
        'asset_fixed': 'Fixed Asset', 
        'asset_current': 'Other Current Asset', 
        'liability_credit_card': 'Credit Card', 
        'liability_current': 'Other Current Liability', 
        'equity': 'Equity', 
        'income': 'Income', 
        'expense': 'Expense', 
        'expense_direct_cost': 'Cost of Goods Sold', 
        'income_other': 'Other Income'
        }.get(qb_account_type, 'Cost of Goods Sold')

class QuickBookOnlineAccount(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'

	def export_sync_account(self,connection, instance_id, limit):
		mapping = self.env['quickbookonline.account']
		exported_ids = mapping.search([('instance_id','=',instance_id)]).mapped('name').ids
		to_export_ids = self.env['account.account'].search([('id','not in',exported_ids)],limit=limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		if not to_export_ids.ids:
			message += '<div class="alert alert-warning" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : Nothing To Export</div>'
		try:
			for account_id in to_export_ids:
				response = self.export_online_account(connection, account_id, instance_id)
				if response.get('status'):
					quickbook_id = response['quickbook_id']
					self.create_odoo_mapping('quickbookonline.account', account_id.id, quickbook_id, instance_id)
					successfull_ids.append(account_id.id)
				else:
					unsuccessfull_ids.append(str(account_id.id))
					if response['message']:
						msg += '<span>({}) {}</span><br>'.format(str(account_id.id), response['message'])
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		else:
			if successfull_ids:
				message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} Accounts SuccessFull Exported.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
			if unsuccessfull_ids:
				message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Accounts Exported IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message
	
	def export_update_account(self, connection, instance_id, limit):
		mapping = self.env['quickbookonline.account']
		to_update_ids = mapping.search([('instance_id','=',instance_id),
		('is_sync','=','yes')],limit = limit)
		successfull_ids, unsuccessfull_ids = [],[]
		msg = ''
		message = ''
		for to_update in to_update_ids:
			account_id = to_update.name
			quickbook_id = to_update.quickbook_id
			response = self.update_online_account(connection,account_id,quickbook_id, instance_id)
			if response.get('status'):
				to_update.is_sync = 'no'
				successfull_ids.append(account_id.id)
			else:
				unsuccessfull_ids.append(str(account_id.id))
				if response['message']:
					msg += '<span>({}) {}</span><br>'.format(str(account_id.id), response['message'])
		if successfull_ids:
			message += '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>{} SuccessFull Accounts Updated To Quickbook.<br><br>Success Ids : {}.</div>'.format(len(successfull_ids),successfull_ids)
		if unsuccessfull_ids:
			message += '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>UnsuccessFull Accounts Updated IDs {}<br><br><span>Response Message</span><br>{}</div>'.format(unsuccessfull_ids,msg)
		return message


	def export_online_account(self,connection,account_id, instance_id):
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
			url+= 'account?minorversion=75'
			schema = {
				'Name':account_id.name,
				'AccountType': get_quickbook_account_type(account_id.account_type or ''),
				'AcctNum': account_id.code[:15] if account_id.code else ''
			}
			_logger.info("==============================================schema%r",schema)		
			try:
				response = client.call_online_api(url, 'POST', json.dumps(schema),headers = headers)
				quickbook_id =  response.get('Account')['Id']
				status = True
			except Exception as e:
				message = str(e)
		return{
			'status':status,
			'quickbook_id':quickbook_id,
			'message':message
		}
	

	def check_online_specific_account(self, connection, account_id, instance_id):
		mapping = self.env['quickbookonline.account']
		domain = [('instance_id','=',instance_id),
		('name','=',account_id.id)]
		search = mapping.search(domain,limit=1)
		quickbook_id = False
		if search:
			quickbook_id = search.quickbook_id
		else:
			response = self.export_online_account(connection, account_id, instance_id)
			if response.get('status'):
				quickbook_id = response['quickbook_id']
				self.create_odoo_mapping('quickbookonline.account', account_id.id, quickbook_id, instance_id)
		return quickbook_id
		
