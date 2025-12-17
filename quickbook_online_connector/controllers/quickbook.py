# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   "License URL : <https://store.webkul.com/license.html/>"
#
##########################################################################

import logging
from odoo import http
from odoo.http import Response
import base64
from odoo.http import request
# from odoo.addons.web.controllers.main import Binary
from datetime import datetime
from odoo import http, SUPERUSER_ID
_logger = logging.getLogger(__name__)


class QuickbookOnlineConnector(http.Controller):

	@http.route('/quickbook_online_connector',type='http',auth='user')
	def quickbook_online_connector(self,*args,**kwargs):
		connection = request.env['quickbookonline.instance'].search([('active','=',True)],limit=1)
		try:
			get = connection.create_online_connection(kwargs)
			action_id = request.env.ref('quickbook_online_connector.quickbook_online_connection_mapping').id
			url = "/web#id={}&action={}&model=quickbookonline.instance&view_type=form".format(connection.id,action_id)
			return request.redirect(url)
		except Exception as e:
			_logger.error("=========Error Found While Generating Access Token========%r",str(e))
	

	@http.route('/quickbook_online_connector/fetch_instace_id',type='jsonrpc',auth='user')
	def fetch_instace_id(self,*args, **kwargs):
		instance_id = request.session.get('instance_id',False)
		instance_env = request.env['quickbookonline.instance']
		connection = instance_env.search([('active','=',True)])
		if not instance_id and connection:
			request.session['instance_id'] = connection[0].id
			instance_id = connection[0].id
		if connection and instance_id not in connection.ids:
			request.session['instance_id'] = connection[0].id
			instance_id = connection[0].id
		current_date = datetime.now().strftime("%d %b %Y")
		return {'instance_id':instance_id,'current_date':current_date}
	
	@http.route('/quickbook_online_connector/change_instance_id',type='jsonrpc',auth='user')
	def change_instance_id(self,instance_id=1):
		request.session['instance_id'] = int(instance_id)
		return {'instance_id':int(instance_id)}
	

	@http.route('/quickbook_online_connector/fetch_instace_details',type='jsonrpc',auth='user')
	def fetch_instace_details(self,*args, **kwargs):
		selection_instance = {}
		connection = request.env['quickbookonline.instance'].search([('active','=',True)])
		for instance in connection:
			selection_instance[instance.id] = instance.name
		return selection_instance
	

	@http.route('/quickbook_online_connector/fetch_instance_extra_details',type='jsonrpc',auth='user')
	def fetch_instance_extra_details(self,instance_id = False,*args, **kwargs):
		data = {}
		models = {'order':'quickbookonline.order','purchase_order':'quickbookonline.purchase.order',
		'invoice':'quickbookonline.invoice',
		'product':'quickbookonline.product','partner':'quickbookonline.partner','category':'quickbookonline.category'}
		for key,value in models.items():
			html = ''
			count = request.env[value].search_count([('instance_id','=',instance_id)])
			data[key] = {
				'count':count,
			}
			html = self.get_graph_html(instance_id, count, value,html,'#972C8C')
			html = self.get_graph_html(instance_id, count, value,html,'#3BCE99','import')
			data[key]['html'] = html
		img_url = f'/web/content/res.company/{SUPERUSER_ID}/logo'
		data['image'] = img_url
		return data
	
	def get_graph_html(self,instance_id, count, model,html,color, operation='export'):
		if not count:
			percentage = 0
		else:
			count_operation = request.env[model].search_count([('created_by','=',operation),('instance_id','=',instance_id)])
			percentage = int((count_operation*100)/count)
		html+= '''
			<span style="background-color: {};flex: 0 0 {}%;height:10px;"></span>
		'''.format(color,percentage)
		return html
	
	@http.route('/quickbook_online_connector/get_synchronisation_id', type ='jsonrpc', auth='user')
	def get_synchronisation_id(self, action='export', instance=1, *args, **kwargs):
		bulk_synchronization = request.env['quickbookonline.bulk.synchronisation']
		vals = {
				'action':action,
				'instance_id':int(instance)
			}
		sync = bulk_synchronization.create(vals)
		return {'id':sync.id}
	
	@http.route('/quickbook_online_connector/fetch_sales_doughnut_data',type='jsonrpc',auth='user')
	def fetch_sales_doughnut_data(self, instance_id=1):
		color = {
		'draft':'#45F18A',
		'sale':'#007AFF',
		'done':'#5E2160'
		}
		select_sql_clause = """SELECT count(state) as total_state,
		state 
		FROM sale_order where id in 
		(select name from quickbookonline_order where instance_id=%d)
		AND state in ('draft','sale','done')
		group by state"""%instance_id
		request.env.cr.execute(select_sql_clause)
		query_results = request.env.cr.dictfetchall()
		data = {'sale_data':{},'sale_statuses':[],'color':[]}
		sale_data = {result['state'].strip():result['total_state'] for result in query_results}
		for check in color:
			data['sale_data'][check] = sale_data.get(check,0)
			data['color'].append(color[check])
			data['sale_statuses'].append(check.capitalize())
		return data
	
	@http.route('/quickbook_online_connector/fetch_purchase_doughnut_data',type='jsonrpc',auth='user')
	def fetch_purchase_doughnut_data(self, instance_id=1):
		color = {
		'draft':'#45F18A',
		'purchase':'#007AFF',
		'done':'#5E2160'
		}
		select_sql_clause = """SELECT count(state) as total_state,
		state 
		FROM purchase_order where id in 
		(select name from quickbookonline_purchase_order where instance_id=%d)
		AND state in ('draft','purchase','done')
		group by state"""%instance_id
		request.env.cr.execute(select_sql_clause)
		query_results = request.env.cr.dictfetchall()
		data = {'purchase_data':{},'purchase_statuses':[],'color':[]}
		purchase_data = {result['state'].strip():result['total_state'] for result in query_results}
		for check in color:
			data['purchase_data'][check] = purchase_data.get(check,0)
			data['color'].append(color[check])
			data['purchase_statuses'].append(check.capitalize())
		return data

	@http.route('/quickbook_online_connector/get_dashboard_line_data',type = 'jsonrpc', auth = 'user')
	def get_dashboard_line_data(self,instance_id = 1,month=False,invoice=True,payment=True):
		labels = [
				'Mon', 'Tue',
				'Wed', 'Thu', 'Fri',
				'Sat', 'Sun'
			]
		if month:
			query_move = """
			select to_char(create_date, 'Dy') AS "day",count(*) as total_count
			FROM quickbookonline_invoice WHERE to_char(create_date,'Mon') ='%s' AND instance_id = %d
			GROUP BY to_char(create_date, 'Dy')
			"""%(month,instance_id)
			query_payment = """
			select to_char(create_date, 'Dy') AS "day",count(id) as total_count
			FROM quickbookonline_payment WHERE to_char(create_date,'Mon') ='%s' AND instance_id = %d
			GROUP BY to_char(create_date, 'Dy')
			"""%(month,instance_id)
		else:
			query_move = """
			select to_char(create_date, 'Dy') AS "day",count(*) as total_count
			FROM quickbookonline_invoice WHERE instance_id = %d
			GROUP BY to_char(create_date, 'Dy')
			"""%instance_id
			query_payment = """
			select to_char(create_date, 'Dy') AS "day",count(*) as total_count
			FROM quickbookonline_payment WHERE instance_id = %d
			GROUP BY to_char(create_date, 'Dy')
			"""%instance_id
		data = {'labels':labels,
		'datasets':[]}
		if invoice:
			invoice_vals = {
					'label': "Customer Invoice",
					'fill': False,
					'lineTension': 1,
					'backgroundColor': "#FFB661",
					'borderColor': "#5E2160", 
					'borderCapStyle': False,
					'borderDash': [],
					'borderDashOffset': 0.0,
					'borderJoinStyle': 'miter',
					'pointBorderColor': "#5E2160",
					'pointBackgroundColor': "white",
					'pointBorderWidth': 1,
					'pointHoverRadius': 8,
					'pointHoverBackgroundColor': "#5E2160",
					'pointHoverBorderColor': "#FFB661",
					'pointHoverBorderWidth': 2,
					'pointRadius': 4,
					'pointHitRadius': 10,
					'data': [],
					'spanGaps': True,
				  }
			request.env.cr.execute(query_move)
			invoice_data = {data['day'].strip():data['total_count'] for data in request.env.cr.dictfetchall()}
			for label in labels:
				invoice_vals['data'].append(int(invoice_data.get(label,0)))
			data['datasets'].append(invoice_vals)
		if payment:
			payment_vals = {
					'label': "Customer Payment",
					'fill': False,
					'lineTension': 1,
					'backgroundColor': "#201CD9",
					'borderColor': "#2492E1", 
					'borderCapStyle': False,
					'borderDash': [],
					'borderDashOffset': 0.0,
					'borderJoinStyle': 'miter',
					'pointBorderColor': "#201CD9",
					'pointBackgroundColor': "white",
					'pointBorderWidth': 1,
					'pointHoverRadius': 8,
					'pointHoverBackgroundColor': "#201CD9",
					'pointHoverBorderColor': "#2492E1",
					'pointHoverBorderWidth': 2,
					'pointRadius': 4,
					'pointHitRadius': 10,
					'data': [],
					'spanGaps': True,
				  }
			request.env.cr.execute(query_payment)
			payment_data = {data['day'].strip():data['total_count'] for data in request.env.cr.dictfetchall()}
			for label in labels:
				payment_vals['data'].append(int(payment_data.get(label,0)))
			data['datasets'].append(payment_vals)
		return {
			'data':data
		}


	@http.route('/quickbook_online_connector/webhook',type='http', methods=['POST'], auth='public', csrf=False)
	def quickbook_online_connector_webhook(self, **post):
		connection = request.env['quickbookonline.instance'].search([('active','=',True)],limit=1)
		
		_logger.error("=========Error Found While Generating Access Token========%r",post)
		
		# try:
		# 	get = connection.create_online_connection(kwargs)
		# 	action_id = request.env.ref('quickbook_online_connector.quickbook_online_connection_mapping').id
		# 	url = "/web#id={}&action={}&model=quickbookonline.instance&view_type=form".format(connection.id,action_id)
		# 	return http.local_redirect(url)
		# except Exception as e:
		# 	_logger.error("=========Error Found While Generating Access Token========%r",str(e))
	
			
