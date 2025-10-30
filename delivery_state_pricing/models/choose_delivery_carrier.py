# models/choose_delivery_carrier.py
from odoo import api, fields, models


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    state_id = fields.Many2one(
        "res.country.state",
        string="State"
    )
    postal_id = fields.Many2one('shipping.cost')
    postal_id_domain = fields.Many2many('postal.code' , compute="_compute_available_postal_codes",store=False)
    zip_code = fields.Char(string="Postal Code", compute="_compute_state_id")


    # @api.depends('state_id')
    # def _compute_available_postal_codes(self):
    #     if self.state_id and self.state_id.postal_ids:
    #         matching_postals = self.state_id.postal_ids.filtered(lambda p: p.state_id == self.state_id)
    #         if matching_postals:
    #             self.postal_id_domain = matching_postals
    #         else:
    #             self.postal_id_domain = False
    #             self.postal_id = False
    #     else:
    #         self.postal_id_domain = False
    #         self.postal_id = False

    @api.onchange('state_id')
    def _onchange_state_id(self):
        self.delivery_message = False
        if self.delivery_type in ('fixed', 'base_on_rule'):
            vals = self._get_delivery_rate()
            if vals.get('error_message'):
                return {'error': vals['error_message']}
        else:
            self.display_price = 0
            self.delivery_price = 0


    @api.onchange('postal_id')
    def _onchange_postal_id(self):
        self.delivery_message = False
        if self.delivery_type in ('fixed', 'base_on_rule'):
            vals = self._get_delivery_rate()
            if vals.get('error_message'):
                return {'error': vals['error_message']}
        else:
            self.display_price = 0
            self.delivery_price = 0


    @api.depends("order_id")
    def _compute_state_id(self):
        for wizard in self:
            wizard.zip_code = wizard.order_id.partner_shipping_id.zip
            wizard.state_id = wizard.order_id.partner_shipping_id.state_id
            wizard.postal_id = wizard.order_id.partner_shipping_id.postal_id

    def _get_delivery_rate(self):
        ctx = dict(self.env.context, order=self.order_id, order_weight=self.total_weight,wizard_state=self.state_id,wizard_postal_id=self.postal_id)
        vals = self.carrier_id.with_context(ctx).rate_shipment(self.order_id)
        if vals.get("success"):
            self.delivery_message = vals.get("warning_message", False)
            self.delivery_price = vals["price"]
            self.display_price = vals["carrier_price"]
            return {"no_rate": vals.get("no_rate", False)}
        return {"error_message": vals["error_message"]}




