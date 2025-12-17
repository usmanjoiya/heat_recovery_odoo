#!/usr/bin/env python
# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################

__author__ = "Deepak Singh Gusain <deepak.singh509@webkul.com>"

class QuickbookRestApiError(Exception):
	"""Generic Quickbook Api error class

	To catch these, you need to import it in you code e.g. :
	from odoo.addons.quickbook_online_connector.models import execption
	from odoo.addons.quickbook_online_connector.models.exception import QuickbookRestApiError
	"""

	def __init__(self, msg, error_code=None, so_error_message='', so_error_code=None):
		self.msg = msg
		self.error_code = error_code
		self.so_error_message = so_error_message
		self.so_error_code = so_error_code

	def __str__(self):
		message=''
		if self.error_code==401:
			message='Code 401- Invalid QuickBook Oauth2 Information'
		message=message+repr(self.so_error_message)
		return message

class QuickbookResyncError(QuickbookRestApiError):
	'''
		Generic QuickbookResyncError error class
		This Class Inherits QuickbookRestApiError Class And Will Use When Access Token Will Expire
	'''
	pass
