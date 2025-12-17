# -*- coding: utf-8 -*-
##########################################################################
#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import api, fields, models
import logging
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

connection  = 'quickbookonline.instance'


class quickbookonlineManualSynchronization(models.TransientModel):
    _name = 'quickbookonline.manual.synchronisation'
    _description = "Quickbook Online Manual Synchronization"


    @api.model
    def _get_object_type(self):
        storage_type = [
        ('category','Product Category'),
        ('account','Account'),
        ('partner','Partner'),
        ('product','Product'),
        ('order','Sale Order'),
        ('invoice','Account Invoice'),
        ('payment','Account Payment'),
        ('vendor','Vendor(Supplier)'),
        ('purchase_order','Purchase Order'),
        ('bill','Bill'),
        
        ]
        return storage_type


    def _default_instance_name(self):
        return self.env[connection].search([], limit=1).id

    instance_id = fields.Many2one(
        comodel_name = connection, 
        string = 'Instance Id', 
        default = lambda self: self._default_instance_name())

    object_type = fields.Selection(
        selection = '_get_object_type',
        string = "Operation"
        )

    to_export_ids = fields.Char()

    def start_action_manual_synchronization(self):
        self.ensure_one()
        quickbookonline_synchronization = self.env['quickbookonline.synchronization'].with_company(self.instance_id.company_id).with_context(quickbook='quickbook',
        instance_id = self.instance_id.id)
        message = '<div class="alert alert-danger" role="alert"><h3 class="alert-heading"><i class="fa fa-exclamation-triangle"/> Error</h3><hr>There is an issue while Synchronizing Data</div>'
        instance_id = self.instance_id.id
        ctx = dict(self.env.context or {})
        # _logger.info("+++++++++quickbookonline_synchronization+++++++++++++:%r",ctx)
        connection = self.env['quickbookonline.instance']._create_quickbook_connection(instance_id)
        method = "export_sync_%s_data"%(self.object_type)
        if hasattr(quickbookonline_synchronization,method):
            message = getattr(quickbookonline_synchronization,method)(connection, instance_id, self.to_export_ids)
        return self.env['quickbookonline.message.wizard'].generate_message(message)

