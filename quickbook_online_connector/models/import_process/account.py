# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import _, models
import logging
_logger = logging.getLogger(__name__)

def get_odoo_account_type(qb_account_type):
    return  {
        'Bank': 'asset_cash',
		'Accounts Receivable': 'asset_receivable',
		'Accounts Payable': 'liability_payable',
		'Fixed Asset': 'asset_fixed',
		'Other Current Asset': 'asset_current',
		'Credit Card': 'liability_credit_card',
		'Long Term Liability': 'liability_current',
		'Other Current Liability': 'liability_current',
		'Equity': 'equity',
		'Income': 'income',
		'Expense': 'expense',
		'Other Expense': 'expense',
		'Cost of Goods Sold': 'expense_direct_cost',
		'Other Income': 'income_other',
    }.get(qb_account_type, 'asset_cash')

class quickbookonlineSynchronization(models.TransientModel):
	_inherit = 'quickbookonline.synchronization'
	
	
	def import_import_account(self,connection, instance_id, limit):
		query = 'OrderBy Metadata.LastUpdatedTime'
		message = self.import_get_account(connection, instance_id, limit, query)
		return message
	

	def import_get_account(self, connection, instance_id, limit, statement = 1):
		url = connection.get('url')
		query = "select * from Account %s MAXRESULTS %d"%(statement,limit)
		account_account = self.env['account.account']
		mapping = self.env['quickbookonline.account']
		message = '<div class="alert alert-success" role="alert"><h3 class="alert-heading"><i class="fa fa-smile-o"/>Congratulations !</h3><hr>'
		client = self.env['call.quickbook.api']
		access_token = connection.get('access_token')
		try:
			headers = {
				'Content-type':'text/plain',
				'Accept': 'application/json',
				'Authorization':'Bearer %s'%access_token
			}
			response = client.get_query_object(url, query, headers)
			accounts = response.get('Account',[])
			success_ids = []
			for account in accounts:
				vals = self.get_import_account_vals(account, connection, instance_id)
				if not vals['code']:
					_logger.info("=====================================valscode%r",vals)
					vals['code'] = self.env['ir.sequence'].next_by_code('account.account')
				domain = [('instance_id','=',instance_id),
				('quickbook_id','=',account['Id'])]
				search = mapping.search(domain,limit=1)
				if not search:
					account_id = account_account.search([('code','=',vals['code'])],limit=1)
					if account_id:
						odoo_id = account_id
						odoo_id.is_quickbook = True
					else:
						odoo_id = account_account.create(vals)
					success_ids.append(self.create_odoo_mapping('quickbookonline.account', odoo_id.id, account['Id'], instance_id,{'created_by':'import'
						}))
				else:
					search.mapped('name').is_quickbook = True
			message += '{} Accounts SuccessFully Imported</div>'.format(len(success_ids))
		except Exception as e:
			message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>Message : {}</div>'.format(str(e))
		return message
		
	def get_import_account_vals(self, account, connection, instance_id):
		vals = {
			'name':account.get('Name'),
			'code':account.get('AcctNum',False),
			'is_quickbook':True
			}
		# account_user = self.env['account.account.type']
		account_type = get_odoo_account_type(account.get('AccountType'))
		# user_type = account_user.search([('name','=',account_type)],limit=1)
		if account_type:
			vals['account_type'] = account_type
			if account_type in ('asset_receivable', 'liability_payable'):
				vals['reconcile'] = True
		else:
			# user_type = account_user.search([],limit=1)
			account_id = self.env['account.account'].search([],limit=1)
			if account_id:
				vals['account_type'] = account_id.account_type
				if account_type in ('asset_receivable', 'liability_payable'):
					vals['reconcile'] = True
			else:
				vals['account_type'] = False
		return vals

	def import_get_specific_account(self, connection, quickbook_id, instance_id):
		mapping = self.env['quickbookonline.account']
		domain = [('quickbook_id','=',quickbook_id),
		('instance_id','=',instance_id)]
		account = False
		find = mapping.search(domain,limit=1)
		if find:
			account = find.odoo_id
		else:
			query = "WHERE Id='%s'"%quickbook_id
			self.import_get_account(connection,instance_id,1,query)
			find = mapping.search(domain,limit=1)
			if find:
				account = find.odoo_id
		return account
