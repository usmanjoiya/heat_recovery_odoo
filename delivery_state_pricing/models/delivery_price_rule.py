from odoo import models, fields, api, _
from odoo.tools.misc import format_amount

class DeliveryPriceRule(models.Model):
    _inherit = 'delivery.price.rule'

    variable = fields.Selection(
        selection_add=[
            ("state", "State"),
            ("country", "Country"),
        ],
        ondelete={
            "state": "set default",
            "country": "set default",
        },
    )
    country_id = fields.Many2one(
        'res.country',
        string="Country",
    )
    state_id = fields.Many2one(
        'res.country.state',
        string="State",
    )
    postal_id = fields.Many2one('shipping.cost')
    available_state_ids = fields.Many2many(
        'res.country.state',
    )

    zip_code = fields.Char(string="Postal Code")

    postal_id_domain = fields.Many2many('postal.code')

    @api.depends('carrier_id.state_ids')
    def _compute_available_states(self):
        for rule in self:
            rule.available_state_ids = rule.carrier_id.state_ids

    # Override compute name so it reflects state pricing
    @api.depends('state_id', 'list_base_price', 'currency_id')
    def _compute_name(self):
        for rule in self:
            price = rule.currency_id and format_amount(
                self.env, rule.list_base_price, rule.currency_id
            ) or "%.2f" % rule.list_base_price

            if rule.variable == "country" and rule.postal_id:
                rule.name = _("Country %s → %s") % (rule.country_id.name, price)
            elif rule.variable == "state" and rule.state_id:
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
        state = self.env.context.get("wizard_state") or (order.partner_shipping_id.state_id if order else False)
        postal_id = self.env.context.get("wizard_postal_id") or (order.partner_shipping_id.postal_id if order else False)
        order_weight = self.env.context.get("order_weight")
        #
        # if postal_id:
        #     cost = postal_id.cost
        # elif state:
        #     cost = state.cost

        for rule in rules:
            if self._match_rule(order, rule, state, postal_id):
                factor = 1.0
                if rule.variable_factor == "weight":
                    factor = weight
                elif rule.variable_factor == "quantity":
                    factor = quantity
                elif rule.variable_factor == "volume":
                    factor = volume
                elif rule.variable_factor == "wv":
                    factor = wv

                # Pick cost based on rule type
                if rule.variable == "state" and state:
                    if order_weight > 0.00:
                        price = state.cost * order_weight
                    else:
                        price = state.cost
                elif rule.variable == "country" and postal_id:
                    if order_weight > 0.00:
                        price = postal_id.cost * order_weight
                    else:
                        price = postal_id.cost
                else:
                    price = rule.list_base_price

                # price = cost           #rule.list_base_price + (rule.list_price * factor)
                break
        return price

    def _match_rule(self, order, rule, state=None, postal_id=None):
        # if not state:
        #     state = order.partner_shipping_id.state_id if order else False
        # if not postal_id:
        #     postal_id = order.partner_shipping_id.postal_id if order else False

        if rule.variable == "country":
            return True

        elif rule.variable == "state":
            return True

        elif rule.variable == "weight":
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
