# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models

from logging import getLogger
_logger = getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, **kwargs):
        """
            Makes the move done and if all moves are done,it will finish the picking.
            @return:
        """
        res = super()._action_done(**kwargs)
        res.post_operation(stock_operation='_action_done')
        return res

    def _action_confirm(self, *args, **kwargs):
        """ Confirms stock move or put it in waiting if it's linked to another move.
        """
        res = super()._action_confirm(*args, **kwargs)
        res.post_operation(stock_operation='_action_confirm')
        return res

    def _action_cancel(self, *args, **kwargs):
        cancelled = self.filtered(lambda self: self.state == 'cancel')
        res = super()._action_cancel(*args, **kwargs)
        if not cancelled:
            self.post_operation(stock_operation='_action_cancel')
        return res

    def post_operation(self, stock_operation):
        if self.env.context.get('restrict_stock_sync'): # Don't sync stock during products import
            return
        domain = [('connection_status', '=', True),('active', '=', True)]
        instance_id = self.env['quickbookonline.instance'].search(domain, limit=1)
        for move in self:
            product_id = move.product_id
            if move.origin and move.picking_type_id.code == 'outgoing':
                sale_id = self.env['sale.order'].search([('name','=',move.origin)])
                if sale_id:
                    mapping_obj = self.env['quickbookonline.order']
                    match = mapping_obj.search([
                        ('instance_id','=', instance_id.id),
                        ('odoo_id','=', sale_id.id)])
                    if match:
                        continue
            if instance_id:
                source_location_id = move.location_id
                dest_location_id = move.location_dest_id
                mapping = self.env['quickbookonline.product'].search([
                    ('instance_id','=', instance_id.id),
                    ('odoo_id','=', product_id.id)
                ], limit=1)
                if mapping:
                    if not instance_id.auto_sync_stock:
                        continue
                    if stock_operation == '_action_confirm':
                        continue
                    location_ids = instance_id.location_id + instance_id.location_id.child_ids
                    if source_location_id in location_ids or dest_location_id in location_ids:
                        qty = instance_id.get_quantity(product_id)
                        instance_id.sync_realtime_quantity(instance_id, mapping, qty)
