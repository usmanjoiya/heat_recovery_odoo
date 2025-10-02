from odoo import models, fields, api, _
from odoo.tools.misc import format_amount

class DeliveryPriceRule(models.Model):
    _inherit = 'delivery.price.rule'

    variable = fields.Selection(
        selection_add=[("state", "State")],
        ondelete={"state": "set default"},
    )

    state_id = fields.Many2one(
        'res.country.state',
        string="State",
        domain="[('id', 'in', available_state_ids)]",
    )

    available_state_ids = fields.Many2many(
        'res.country.state',
        compute="_compute_available_states",
        store=False,
    )

    @api.depends('carrier_id.state_ids')
    def _compute_available_states(self):
        for rule in self:
            rule.available_state_ids = rule.carrier_id.state_ids

    # Override compute name so it reflects state pricing
    @api.depends('state_id', 'list_base_price', 'currency_id')
    def _compute_name(self):
        for rule in self:
            if rule.state_id:
                price = rule.currency_id and format_amount(self.env, rule.list_base_price,
                                                           rule.currency_id) or "%.2f" % rule.list_base_price
                rule.name = _("State %s → %s") % (rule.state_id.name, price)
            else:
                super()._compute_name()


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    def _get_price_from_picking(self, total, weight, volume, quantity, wv=0):
        self.ensure_one()
        order = self.env.context.get("order")
        price = 0.0
        rules = self.env["delivery.price.rule"].search([("carrier_id", "=", self.id)], order="sequence")
        for rule in rules:
            if self._match_rule(order, rule):
                # Compute factor properly
                factor = 1.0
                if rule.variable_factor == "weight":
                    factor = weight
                elif rule.variable_factor == "quantity":
                    factor = quantity
                elif rule.variable_factor == "volume":
                    factor = volume
                elif rule.variable_factor == "wv":
                    factor = wv

                price = rule.list_base_price + (rule.list_price * factor)
                break
        return price

    def _match_rule(self, order, rule):
        """Check state or other conditions."""
        state = order.partner_shipping_id.state_id if order else False

        if rule.variable == "state":
            # Match by exact state
            return rule.state_id and state and (rule.state_id.id == state.id)

        # Fallbacks: weight, qty, volume
        if rule.variable == "weight":
            value = order.shipping_weight
        elif rule.variable == "quantity":
            value = sum(order.order_line.mapped("product_uom_qty"))
        elif rule.variable == "volume":
            value = sum(order.order_line.mapped("product_id.volume"))
        else:
            return False

        if rule.operator == "==":
            return value == rule.max_value
        elif rule.operator == "<=":
            return value <= rule.max_value
        elif rule.operator == "<":
            return value < rule.max_value
        elif rule.operator == ">=":
            return value >= rule.max_value
        elif rule.operator == ">":
            return value > rule.max_value
        return False
