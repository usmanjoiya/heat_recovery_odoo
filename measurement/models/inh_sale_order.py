from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    floor_type = fields.Selection(
        [
            ('concrete', 'Concrete Slab'),
            ('engineered_joists', 'Engineered joists'),
            ('solid_joist', 'Solid Joist')],
        string='Floor Type'
    )
    selective_diameter = fields.Selection(
        [
            ('125MM', '125MM'),
            ('150MM', '150MM'),
            ('180MM', '180MM'),
         ],
        string='Diameter'
    )

    place_type = fields.Selection(
        [('roof_vents', 'Roof Vents'), ('wall_cowl', 'Wall Cowl')],
        string='Placement'
    )

    supply_install = fields.Selection(
        [('supply_fit_commission', 'Supply, Fit and Commission'),
         ('supply_only', 'Supply Only (Self Install)')],
        string='System Overview Supplier'
    )

    supply_kit = fields.Selection(
        [('connection_kit', 'Connection Kit - Plenums, Valves, Radial pipe & Manifolds'),
         ('ext_supply_extract', 'External Supply & Extract Premium Thermal Foam Kit'),
         ('ext_supply_pvc', 'External Supply & Extract PVC Kit')],
        string='System Overview Ext 1'
    )

    supply_kit_install = fields.Selection(
        [('connection_kit', 'Connection Kit - Plenums, Valves, Radial pipe & Manifolds'),
         ('ext_supply_extract', 'External Supply & Extract Premium Thermal Foam Kit'),
         ('ext_supply_pvc', 'External Supply & Extract PVC Kit')],
        string='System Overview Ext 2'
    )
    line_price_of_kit = fields.Float('Kit price', compute='_get_line_kit_price')
    line_price_of_service_prod = fields.Float('Service Product Pricce', compute='_get_line_service_prod_price')

    no_of_bedrooms = fields.Integer(string="No. of Bedrooms")
    dwelling_total_area = fields.Float(string="Dwelling Total Area (sq m)")
    area_rate = fields.Float(string="Area Rate", compute="_compute_area_rate", store=True)
    bedroom_rate = fields.Float(string="Bedroom Rate", compute="_compute_bedroom_rate", store=True)
    extract_rate = fields.Float(string="Extract Rate", compute="_compute_extract_rate", store=True)
    correct_rate = fields.Float(string="Correct Rate", compute="_compute_correct_rate", store=True)
    req_cont_trickle = fields.Float(string="Required Continious Trickle")
    m3_h = fields.Float(string="M3/H")
    no_of_manifolds=fields.Integer(string='Manifolds',compute="_get_no_of_manifolds")
    no_of_points=fields.Integer(string='Points', compute="_compute_no_of_points")
    no_of_radial_ducting = fields.Float(
        string="No of Radial Ducting",
        compute="_compute_no_of_radial_ducting",
        store=True,
    )
    global_discount = fields.Float(string="Discount (%)", default=0.0)
    milage_one_way = fields.Integer(string="MILAGE ONE WAY")
    nights = fields.Integer(string="NIGHTS")
    coring = fields.Float(string="CORING", compute="_get_coring_value")
    commission = fields.Selection(
        [
            ('0', '0'),
            ('175', '175'),
            ('250', '250')],
        string='COMMISSIONING'
    )
    men_needed = fields.Integer(string="MEN NEEDED")
    days = fields.Integer(string="DAYS")
    trip_needed = fields.Integer(string="TRIPS NEEDED")
    base_cost = fields.Float(string="BASE COST", compute="_compute_base_cost", store=True)
    profit = fields.Float(string="PROFIT")
    total = fields.Float(string="TOTAL", compute="_get_total_cost", store=True)

    per_men_cost = fields.Float(string="Per Men Cost",default=130.00)
    per_night_cost = fields.Float(string="Per Night Cost",default=115.00)
    per_mile_cost = fields.Float(string="Per Mile Cost",default=0.45)
    total_margin = fields.Monetary(
        string='Total Margin (Goods only)',
        compute='_compute_total_margin',
        store=True,
        currency_field='currency_id'
    )


    room_measurement_ids = fields.One2many('room.measurement', 'order_id', string="Room Measurements")
    commission_table_ids = fields.One2many('commission.table', 'order_id', string="Commissioning Table")
    floor_name_ids = fields.Many2many('floor.names', 'sale_order_floor_rel', 'order_id', 'floor_id', string="Floors")


    basic_prod = fields.Many2one('product.product', string="Basic Product" ,domain="[('product_type', '=', 'base')]")
    upgraded_prod = fields.Many2one('product.product', string="Upgraded Product" ,domain="[('product_type', '=', 'upgraded')]")
    premium_prod = fields.Many2one('product.product', string="Premium Product", domain="[('product_type', '=', 'premium')]")
    alrightness_id = fields.Many2one('alrightness.pricess', string="Alrightness")
    alrightness_price = fields.Float(string='Alrightness Price', compute="_compute_alrightness_price", store=True)
    product_line_ids = fields.One2many('sale.order.product.line', 'sale_id', string="Products (Filtered)")
    calculator_tool_ids = fields.One2many('calculator.tool', 'order_id', string="Calculator Tool")
    coring_coster_line_ids = fields.One2many('coring.coster.line','order_id',string="Coring Coster")


    def _get_line_kit_price(self):
        amount = 0
        for line in self.order_line:
            if line.product_id.type != 'service' and not line.product_id.product_type:
                amount += line.price_subtotal
        self.line_price_of_kit = amount

    def _get_line_service_prod_price(self):
        amount = 0
        product = self._get_service_product()
        for line in self.order_line:
            if line.product_id.type == 'service' and line.product_id == product:
                amount += line.price_subtotal
        self.line_price_of_service_prod = amount

    @api.depends('coring_coster_line_ids')
    def _get_coring_value(self):
        for order in self:
            order.coring = sum(
                line.sub_total for line in order.coring_coster_line_ids) if order.coring_coster_line_ids else 0.0

    @api.depends('milage_one_way', 'nights', 'coring', 'commission', 'men_needed', 'days', 'trip_needed')
    def _compute_base_cost(self):
        for order in self:
            order.base_cost = 0.0
            if order.milage_one_way:
                order.base_cost += order.milage_one_way * order.per_mile_cost
            if order.nights:
                order.base_cost += order.nights * order.per_night_cost
            if order.coring:
                order.base_cost += order.coring
            if order.commission:
                commission_mapping = {
                    '0': 0.00,
                    '175': 175.00,
                    '250': 200.00,
                }
                order.base_cost += commission_mapping.get(order.commission, 0.0)
            if order.men_needed:
                order.base_cost += order.men_needed * order.per_men_cost
            if order.days:
                order.base_cost += order.days * (order.men_needed * order.per_men_cost)
            if order.trip_needed:
                total_trip_cost = (order.milage_one_way * order.per_mile_cost) * 2
                order.base_cost += total_trip_cost

    @api.depends('base_cost','profit')
    def _get_total_cost(self):
        for order in self:
            order.total = 0.0
            if order.profit:
                order.total = order.profit + order.base_cost
            else:
                order.total += order.base_cost

    @api.model
    def _get_service_product(self):
        """Helper to fetch the calculator service product"""
        product = self.env.ref('measurement.service_product_calculator_tool', raise_if_not_found=False)
        if not product:
            raise UserError(_("The service product 'Calculator Tool' is missing. Please check XML ID 'service_product_calculator_tool'."))
        return product.product_variant_id

    def action_add_calculator_product(self):
        """Add the calculator service product to order lines"""
        for order in self:
            if not order.total:
                raise UserError(_("Total value is missing, please compute it before adding the product."))

            product = order._get_service_product()

            # Check if product already exists in order lines
            existing_line = order.order_line.filtered(lambda l: l.product_id == product)
            if existing_line:
                existing_line.price_unit = order.total
                existing_line.product_uom_qty = 1
            else:
                order.order_line = [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': 1,
                    'price_unit': order.total,
                    'name': product.name,
                })]
        return True

    @api.onchange('global_discount')
    def _onchange_discounted_price(self):
        """Compute discounted price based on sale_price and discount."""
        for order in self:
            for line in order.product_line_ids:
                new_sale_price = line.product_id.list_price * (1 - (order.global_discount / 100))
                line.sale_price = new_sale_price


    def action_get_products(self):
        for order in self:
            if not order.m3_h or order.m3_h == 0.0:
                raise UserError("You must do all the process to set the M3/H value before getting products.")
            # Clear and reload products
            products = self.env['product.template'].search([('m3_h', '>', 0)])
            order.product_line_ids = [(5, 0, 0)]
            lines = []


            for prod in products:
                vals = {
                    'sale_id': order.id,
                    'product_id': prod.product_variant_id.id,
                    'product_diameter': prod.product_diameter,
                    'product_type': prod.product_type,
                    'm3_h': prod.m3_h,
                    'sale_price': prod.product_variant_id.list_price,  # 👈 capture the sale price
                    'prod_capacity': (order.m3_h / prod.m3_h * 100) if order.m3_h and prod.m3_h else 0.0,
                }
                lines.append((0, 0, vals))

            order.product_line_ids = lines

            # --- Now pick the best products per type ---
            # group lines by type

            # order.product_line_ids.filtered(lambda l: l.product_type == 'base' and l.product_variant_id.area_m2_from >= order.dwelling_total_area and l.product_variant_id.area_m2_to <= order.dwelling_total_area)
            base_line = order.product_line_ids.filtered(lambda l: l.product_type == 'base' and l.product_id.area_m2_from <= order.dwelling_total_area and l.product_id.area_m2_to >= order.dwelling_total_area)
            upgraded_line = order.product_line_ids.filtered(lambda l: l.product_type == 'upgraded' and l.product_id.area_m2_from <= order.dwelling_total_area and l.product_id.area_m2_to >= order.dwelling_total_area)
                # max(order.product_line_ids.filtered(lambda l: l.product_type == 'upgraded'),
                #                 key=lambda l: l.prod_capacity, default=False)
            premium_line =order.product_line_ids.filtered(lambda l: l.product_type == 'premium' and l.product_id.area_m2_from <= order.dwelling_total_area and l.product_id.area_m2_to >= order.dwelling_total_area)
                # max(order.product_line_ids.filtered(lambda l: l.product_type == 'premium'),
                #                key=lambda l: l.prod_capacity, default=False)

            # assign best products to sale.order fields
            order.basic_prod = base_line[0].product_id.id if base_line else False
            order.upgraded_prod = upgraded_line[0].product_id.id if upgraded_line else False
            order.premium_prod = premium_line[0].product_id.id if premium_line else False

            Product = self.env['product.product']
            attr_diameter = self.env.ref('measurement.attr_ducting_diameter')
            attr_manifolds = self.env.ref('measurement.attr_no_manifolds')
            attr_points = self.env.ref('measurement.attr_no_points')
            product = Product.search([
                ('main_kit_product', '=', True),
                ('product_template_attribute_value_ids.attribute_id.name', '=', attr_diameter.name),
                    ('product_template_attribute_value_ids.product_attribute_value_id.name', '=', self.selective_diameter),
                ('product_template_attribute_value_ids.attribute_id.name', '=', attr_manifolds.name),
                ('product_template_attribute_value_ids.product_attribute_value_id.name', '=', str(self.no_of_manifolds)),
                ('product_template_attribute_value_ids.attribute_id.name', '=', attr_points.name),
                ('product_template_attribute_value_ids.product_attribute_value_id.name', '=', str(self.no_of_points)),
            ])
            if product and not self.order_line.filtered(lambda l: l.product_id.id == product[0].id):
                product_record = product[0]  # Assuming 'product' is a recordset

                line_vals = {
                    'order_id': self.id,
                    'product_id': product_record.id,
                    'product_uom_qty': 1.0,
                    'price_unit': product_record.lst_price,
                    'tax_ids': [(6, 0, product_record.taxes_id.ids)],
                    # 'name': product_record.get_product_multiline_description_sale() or product_record.name,
                    'product_uom_id': product_record.uom_id.id,
                }

                # Create the sale order line
                self.env['sale.order.line'].with_context(no_onchange=True).create(line_vals)

                # self.order_line += self.order_line.new({
                #     'product_id': product[0],
                #     'product_uom_qty': 1,
                # })

            placement_products = self.env['placement.config'].search([]).mapped('product_id')
            placement_product_ids = placement_products.ids

            old_lines = self.order_line.filtered(lambda l: l.product_id.id in placement_product_ids)
            if old_lines:
                self.order_line -= old_lines

            for line in self.order_line:
                product = line.product_id

                ducting_attr = next(
                    (av for av in product.product_template_attribute_value_ids
                     if av.attribute_id.name == 'Ducting Diameter'),
                    None
                )
                if not ducting_attr:
                    continue

                match = re.search(r'\d+', ducting_attr.name)
                if not match:
                    continue

                diameter_value = int(match.group(0))

                placement_configs = self.env['placement.config'].search([
                    ('place_type', '=', self.place_type),
                    ('diameter', '=', diameter_value)
                ])

                existing_product_ids = self.order_line.mapped('product_id').ids

                for config in placement_configs:
                    existing_line = self.order_line.filtered(lambda l: l.product_id.id == config.product_id.id)
                    if existing_line:
                        existing_line.product_uom_qty = config.quantity
                        existing_line.part_of_id = product
                        continue

                    self.order_line += self.order_line.new({
                        'product_id': config.product_id.id,
                        'product_uom_qty': config.quantity,
                        'part_of_id': product,
                    })


    @api.depends('dwelling_total_area')
    def _compute_area_rate(self):
        for order in self:
            order.area_rate = order.dwelling_total_area * 0.3 if order.dwelling_total_area else 0.0

    @api.depends('no_of_bedrooms')
    def _compute_bedroom_rate(self):
        for order in self:
            if order.no_of_bedrooms:
                ventilation = self.env['dwelling.ventilation'].search([
                    ('bedroom_no', '=', order.no_of_bedrooms)
                ], limit=1)
                order.bedroom_rate = ventilation.min_vent_rate if ventilation else 0.0
            else:
                order.bedroom_rate = 0.0

    @api.depends('commission_table_ids.point_id')
    def _compute_extract_rate(self):
        for order in self:
            order.extract_rate = sum(order.commission_table_ids.mapped('high'))

    @api.depends('area_rate', 'bedroom_rate', 'extract_rate')
    def _compute_correct_rate(self):
        for order in self:
            order.correct_rate = max(order.area_rate, order.bedroom_rate, order.extract_rate)

    @api.onchange('extract_rate')
    def _req_cont_trickle(self):
        for order in self:
            order.req_cont_trickle = order.correct_rate

    @api.onchange('correct_rate')
    def _m3_h(self):
        for order in self:
            order.m3_h = order.correct_rate * 3.6

    @api.depends('dwelling_total_area','alrightness_id')
    def _compute_alrightness_price(self):
        first_record = self.env['alrightness.pricess'].search([], limit=1)
        for x in self:
            if x.dwelling_total_area <= first_record.area:
                x.alrightness_price = first_record.guide_price_1
            elif x.dwelling_total_area > first_record.area and x.dwelling_total_area <= first_record.area2:
                x.alrightness_price = first_record.guide_price_2
            elif x.dwelling_total_area > first_record.area2 and x.dwelling_total_area <= first_record.area3:
                x.alrightness_price = first_record.guide_price_3
            elif x.dwelling_total_area > first_record.area3:
                x.alrightness_price = first_record.guide_price_4

    def _get_no_of_manifolds(self):
        for order in self:
            if order.floor_type == "concrete":
                order.no_of_manifolds = 4
            else:
                order.no_of_manifolds = 2

    def _compute_no_of_points(self):
        for order in self:
            total_room_drops = sum(order.room_measurement_ids.mapped('supply_drops'))
            total_commission_drops = sum(order.commission_table_ids.mapped('drops'))
            order.no_of_points = total_room_drops + total_commission_drops


    @api.onchange('place_type')
    def _onchange_place_type_add_products(self):
        if not self.place_type:
            return

        placement_products = self.env['placement.config'].search([]).mapped('product_id')
        placement_product_ids = placement_products.ids

        old_lines = self.order_line.filtered(lambda l: l.product_id.id in placement_product_ids)
        if old_lines:
            self.order_line -= old_lines

        for line in self.order_line:
            product = line.product_id

            ducting_attr = next(
                (av for av in product.product_template_attribute_value_ids
                 if av.attribute_id.name == 'Ducting Diameter'),
                None
            )
            if not ducting_attr:
                continue

            match = re.search(r'\d+', ducting_attr.name)
            if not match:
                continue

            diameter_value = int(match.group(0))

            placement_configs = self.env['placement.config'].search([
                ('place_type', '=', self.place_type),
                ('diameter', '=', diameter_value)
            ])

            existing_product_ids = self.order_line.mapped('product_id').ids

            for config in placement_configs:
                existing_line = self.order_line.filtered(lambda l: l.product_id.id == config.product_id.id)
                if existing_line:
                    existing_line.product_uom_qty = config.quantity
                    existing_line.part_of_id = product
                    continue

                self.order_line += self.order_line.new({
                    'product_id': config.product_id.id,
                    'product_uom_qty': config.quantity,
                    'part_of_id': product,
                })

    @api.depends('order_line.product_id')
    def _compute_no_of_radial_ducting(self):
        for order in self:
            total_qty = 0.0
            for line in order.order_line:
                product = line.product_id
                if product.main_kit_product:
                    bom = self.env['mrp.bom'].search(
                        [('product_id', '=', product.id)],
                        limit=1
                    )
                    if bom:
                        radial_bom_line = bom.bom_line_ids.filtered(
                            lambda l: l.product_id.is_radial_pipe
                        )
                        if radial_bom_line:
                            total_qty += sum(radial_bom_line.mapped('product_qty')) * 50
            order.no_of_radial_ducting = total_qty


    def action_open_delivery_wizard(self):
        """Open the Add Shipping wizard and auto-apply custom carrier logic."""
        self.ensure_one()
        state_id = self.partner_shipping_id.state_id
        postal_id = self.partner_shipping_id.postal_id
        view_id = self.env.ref('delivery.choose_delivery_carrier_view_form').id

        carrier = self.env['delivery.carrier'].search(
            [('name', '=', 'State-Based Shipping')], limit=1
        )

        wizard = self.env['choose.delivery.carrier'].create({
            'order_id': self.id,
            'total_weight': self._get_estimated_weight(),
            'carrier_id': carrier.id if carrier else self.carrier_id.id,
        })

        wizard.state_id = state_id
        wizard.postal_id = postal_id
        wizard._onchange_carrier_id()
        wizard._get_delivery_rate()
        wizard.write({
            'delivery_price': wizard.delivery_price,
            'delivery_message': wizard.delivery_message,
        })
        return {
            'name': _('Add a shipping method'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'choose.delivery.carrier',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'res_id': wizard.id,
        }

    @api.depends('order_line.margin', 'order_line.product_id.type', 'amount_untaxed')
    def _compute_total_margin(self):
        for order in self:
            goods_lines = order.order_line.filtered(
                lambda l: l.product_id and l.product_id.type != 'service'
            )
            if goods_lines:
                order.total_margin = sum(goods_lines.mapped('margin'))
            order.total_margin += order.profit if order.profit else 0.0
