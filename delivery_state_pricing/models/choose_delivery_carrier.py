# models/choose_delivery_carrier.py
from odoo import api, fields, models


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        compute="_compute_state_id",
        store=False,
        readonly=False,
    )

    @api.depends("order_id")
    def _compute_state_id(self):
        for wizard in self:
            wizard.state_id = wizard.order_id.partner_shipping_id.state_id

    def _get_delivery_rate(self):
        ctx = dict(self.env.context, order=self.order_id, order_weight=self.total_weight)
        vals = self.carrier_id.with_context(ctx).rate_shipment(self.order_id)
        if vals.get("success"):
            self.delivery_message = vals.get("warning_message", False)
            self.delivery_price = vals["price"]
            self.display_price = vals["carrier_price"]
            return {"no_rate": vals.get("no_rate", False)}
        return {"error_message": vals["error_message"]}




