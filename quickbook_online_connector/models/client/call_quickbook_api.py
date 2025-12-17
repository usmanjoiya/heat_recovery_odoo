# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import api, models
import logging
import requests
from .exeception import QuickbookRestApiError,QuickbookResyncError
from .unicode_encode import unicode2encoding
from .xmltodict import ET2dict
try:
	from xml.etree import cElementTree as ElementTree
except ImportError as e:
	from xml.etree import ElementTree
_logger = logging.getLogger(__name__)


headers = {}
client = None

class CallQuickbookApi(models.TransientModel):
	_name = 'call.quickbook.api'
	_description = 'Class Use To Call Quickbook Api'

	

	@api.model
	def _parse_error(self, content):
		"""
		Take the content as string and extracts the Quickbook error
		@param content: Content of the response of Quickbook Online
		@return (Quickbook Error Code, Quickbook Online Error Message)
		"""
		# error_xml = self._parse(content)
		# Fault = error_xml['IntuitResponse']['value']['Fault']
		# error_code =  Fault['value']['Error']['value']['attrs']['code']
		# error_message =  Fault['value']['Error']['value']['Message']['value']
		_logger.info("===================================error content%r",content)
		if 'Fault' in content:
			error_message = content['Fault']['Error'][0]['Detail']
			error_code = content['Fault']['Error'][0]['code']
		else:
			error_message = content['fault']['error'][0]['message']
			error_code = content['fault']['error'][0]['code']	
		return int(error_code),error_message

	

	@api.model
	def _parse(self, content):
		encoded_content = self._encode_xml(content)
		return ET2dict(encoded_content)

	@api.model
	def _encode_xml(self, content):
		"""
		Parse the response of the webservice

		@param content: response from the webservice
		@return: an ElementTree of the content
		"""
		if not content:
			raise QuickbookRestApiError('HTTP response is empty')

		try:
			# We have to encode it in utf-8, because content has the XML header
			# cf http://lxml.de/FAQ.html#why-can-t-lxml-parse-my-xml-from-unicode-strings
			# WARNING : old versions of 'requests', for instance version 0.8.2
			# packaged in Ubuntu 12.04, return a unicode... but more recent of
			# requests, for instance 0.13.5 return a str in utf-8 !
			parsed_content = ElementTree.fromstring(unicode2encoding(content))
		except Exception as err:
			raise QuickbookRestApiError('HTTP XML Error Response is not parsable : %s' % (err,))
		return parsed_content

	@api.model
	def _check_status_code(self, response, method, url):
		"""
		Take the status code and throw an exception if the server didn't return 200 or 201 or 302 or 204 code
		@param response: response return by the client request
		@param method: request method
		@param url: request url
		@return: True or raise an exception QuickbookRestApiError
		"""
		message_by_code = {
			400: 'Bad Request',
			401: 'Unauthorized',
			403: 'Forbidden',
			404: 'Not Found',
			500: 'Internal Server Error',
			503: 'Service Unavailable',
		}
		status_code = response.status_code
		if status_code in (200, 201, 302, 204):
			content = response.json()
		else:
			content = response.json()
			status_code = response.status_code
			so_error_code, so_error_message = self._parse_error(content)
			if so_error_code==3200:
				raise QuickbookResyncError(
					'Resync Required', 410, 
					'The requested resource is no longer available at the server',410)
			if status_code in message_by_code:
				raise QuickbookRestApiError(message_by_code[status_code],
					status_code, so_error_message, so_error_code)
		return content


	@api.model
	def call_online_api(self,url, method, data=None, headers={}):
		"""
		Execute a request on the Quickbook Rest

		@param url: full url to call
		@param method: GET, POST, PUT,PATCH,DELETE
		@param data: for PUT (edit) and POST (add) only the data sent to Quickbook
		@return: dictionary content and binary data content of the response
		"""
		context = self.env.context.copy() or {}
		global client
		if client==None:
			client = requests.Session()
		request_headers = headers.copy()
		request_headers.update(headers)
		r = client.request(method, url, data=data, headers=request_headers)
		try:
			content = self._check_status_code(r, method, url)
			return content
		except QuickbookResyncError as e:
			if context.get('call_again',True):
				context['call_again'] = False
				instance_id = context.get('instance_id',False)
				if instance_id:
					connection = self.env['quickbookonline.instance']._create_quickbook_connection(instance_id, refresh_token=True)
					access_token = connection.get('access_token',False)
					if access_token:
						headers.update({'Authorization': 'bearer {}'.format(access_token)})
				return self.with_context(context).call_online_api(url, method, data, headers)
			raise QuickbookRestApiError(
					'Required Test Connection', 410, 
					'The Requested Access token is no longer available at the server so test connection again',410)
	
	@api.model
	def get_query_object(self, url, query, headers,miner_version=0):
		url+= 'query?query=%s'%query
		if miner_version:
			url+= '&minorversion=%s'%miner_version
		response = self.call_online_api(url, 'GET',headers=headers)
		return response['QueryResponse']

