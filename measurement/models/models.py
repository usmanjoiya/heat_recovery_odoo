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

    def _get_line_kit_price(self):
        amount = 0
        for line in self.order_line:
            if line.product_id.type != 'service' and not line.product_id.product_type:
                amount += line.price_subtotal
        self.line_price_of_kit = amount

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

    room_measurement_ids = fields.One2many('room.measurement', 'order_id', string="Room Measurements")
    commission_table_ids = fields.One2many('commission.table', 'order_id', string="Commissioning Table")
    floor_name_ids = fields.Many2many('floor.names', 'sale_order_floor_rel', 'order_id', 'floor_id', string="Floors")


    basic_prod = fields.Many2one('product.product', string="Basic Product" ,domain="[('product_type', '=', 'base')]")
    upgraded_prod = fields.Many2one('product.product', string="Upgraded Product" ,domain="[('product_type', '=', 'upgraded')]")
    premium_prod = fields.Many2one('product.product', string="Premium Product", domain="[('product_type', '=', 'premium')]")
    alrightness_id = fields.Many2one('alrightness.pricess', string="Alrightness")
    alrightness_price = fields.Float(string='Alrightness Price', compute="_compute_alrightness_price", store=True)
    product_line_ids = fields.One2many('sale.order.product.line', 'sale_id', string="Products (Filtered)")

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
            print('attribute_idsssssssssssssssssssss',attr_diameter.name,attr_manifolds.id,attr_points.id )
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
                self.order_line += self.order_line.new({
                    'product_id': product[0],
                    'product_uom_qty': 1,
                })

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


class RoomMeasurement(models.Model):
    _name = 'room.measurement'
    _description = 'Room Measurement'

    order_id = fields.Many2one('sale.order',string='Sale Order',ondelete='cascade')

    supply = fields.Char(string='Supply', compute='_compute_supply_name', store=True)
    supply_boost2 = fields.Float(string='Boost2', compute='_compute_supply_boost2', store=True)
    supply_trickle2 = fields.Float(string='Trickle2', compute='_compute_supply_trickle2', store=True)
    supply_drops = fields.Integer(string='Drops', compute='_compute_supply_drops', store=True)
    supply_ducts = fields.Integer(string='Ducts', compute='_compute_supply_ducts', store=True)

    room_id = fields.Char(string='Room #')
    length = fields.Float(string='Length (m)')
    width = fields.Float(string='Width (m)')
    area = fields.Float(string='Area (sq m)', compute='_compute_area', store=True)

    @api.depends('length', 'width')
    def _compute_area(self):
        for record in self:
            record.area = record.length * record.width

    @api.depends('room_id')
    def _compute_supply_name(self):
        for record in self:
            record.supply = record.room_id

    @api.depends('area', 'order_id.correct_rate')
    def _compute_supply_trickle2(self):
        for record in self:
            if record.order_id:
                total_area = sum(record.order_id.room_measurement_ids.mapped('area')) or 1
                for line in record.order_id.room_measurement_ids:
                    line.supply_trickle2 = line.order_id.correct_rate * (line.area / total_area)

    @api.depends('area', 'order_id.extract_rate', 'supply_trickle2')
    def _compute_supply_boost2(self):
        for record in self:
            if record.order_id:
                total_area = sum(record.order_id.room_measurement_ids.mapped('area')) or 1
                for line in record.order_id.room_measurement_ids:
                    supply_extract_rate = line.order_id.extract_rate * (line.area / total_area)
                    line.supply_boost2 = max(supply_extract_rate, line.supply_trickle2 * 1.1)

    @api.depends('supply_trickle2')
    def _compute_supply_drops(self):
        for rec in self:
            if rec.supply_trickle2 < 1:
                rec.supply_drops = 0
            elif 1 <= rec.supply_trickle2 <= 12.9:
                rec.supply_drops = 1
            elif rec.supply_trickle2 >= 13:
                rec.supply_drops = 2
            else:
                rec.supply_drops = 0

    @api.depends('supply_trickle2')
    def _compute_supply_ducts(self):
        for rec in self:
            if rec.supply_trickle2 < 1:
                rec.supply_ducts = 0
            elif 1 <= rec.supply_trickle2 <= 4:
                rec.supply_ducts = 1
            elif 4 < rec.supply_trickle2 <= 12.9999:
                rec.supply_ducts = 2
            elif rec.supply_trickle2 >= 13:
                rec.supply_ducts = 4
            else:
                rec.supply_ducts = 0


class CommissionTable(models.Model):
    _name = 'commission.table'
    _description = 'COMMISSIONING TABLE (l/s)'
    _order = 'sequence, id'  # ensures sorting by sequence

    sequence = fields.Integer(string='Sequence',default=10)

    order_id = fields.Many2one('sale.order',string='Sale Order',ondelete='cascade')
    floor_id = fields.Many2one('floor.names',string="Floor")

    point_id = fields.Many2one('commission.point', string='Point')
    extract = fields.Char(related="point_id.extract")
    high = fields.Float(related="point_id.high" ,string="Point")
    boost = fields.Float(string='Boost')
    boost2 = fields.Float(string='Boost 2', compute='_compute_boost2', store=True)
    trickle = fields.Float(string='Trickle')
    trickle2 = fields.Float(string='Trickle 2',compute='_compute_trickle2', store=True)
    drops = fields.Integer(string='Drops', compute='_compute_drops', store=True)
    ducts = fields.Integer(string='75mm Ducts', compute='_compute_ducts', store=True)

    @api.depends('order_id.correct_rate', 'high', 'order_id.extract_rate')
    def _compute_trickle2(self):
        for record in self:
            if record.order_id and record.order_id.extract_rate:
                record.trickle2 = record.order_id.correct_rate * (record.high / record.order_id.extract_rate)
            else:
                record.trickle2 = 0.0

    @api.depends('high','trickle2')
    def _compute_boost2(self):
        for record in self:
            record.boost2 = max(record.high,record.trickle2 * 1.1)

    @api.depends('trickle2')
    def _compute_drops(self):
        for rec in self:
            if rec.trickle2 < 1:
                rec.drops = 0
            elif 1 <= rec.trickle2 <= 12.9:
                rec.drops = 1
            elif rec.trickle2 >= 13:
                rec.drops = 2
            else:
                rec.drops = 0

    @api.depends('trickle2')
    def _compute_ducts(self):
        for rec in self:
            if rec.trickle2 < 1:
                rec.ducts = 0
            elif 1 <= rec.trickle2 <= 4:
                rec.ducts = 1
            elif 4 < rec.trickle2 <= 12.9999:
                rec.ducts = 2
            elif rec.trickle2 >= 13:
                rec.ducts = 4
            else:
                rec.ducts = 0


class CommissionPoint(models.Model):
    _name = 'commission.point'
    _description = 'DWELLING RATES MVHR'


    name = fields.Char(string='name', readonly=True,compute='_compute_name', store=True)
    extract = fields.Char(string='Extract')
    high = fields.Float(string='High L/S')

    @api.depends('extract', 'high')
    def _compute_name(self):
        for rec in self:
            if rec.extract and rec.high:
                rec.name = f"{rec.extract} - {rec.high}"
            elif rec.extract:
                rec.name = rec.extract
            else:
                rec.name = "Unnamed"



class DwellingVentilation(models.Model):
    _name = 'dwelling.ventilation'
    _description = 'Whole Dwelling Ventilation'

    bedroom_no = fields.Integer(string="Bedrooms")
    min_vent_rate = fields.Float(string='Minimum Ventilation Rates (l/s)')


class FloorNames(models.Model):
    _name = 'floor.names'
    _description = 'Floor Names'
    _rec_name = "floor_name"

    floor_name = fields.Char(string='Floor Name')


class PostalCode(models.Model):
    _name = 'postal.code'
    _description = 'Portal Code'

    name = fields.Char(string='Postal code')
    state_id = fields.Many2one('res.country.state')

class ResPartner(models.Model):
    _inherit = 'res.partner'

    postal_id = fields.Many2one('shipping.cost')
    postal_id_domain = fields.Many2many('postal.code')


    @api.model
    def create(self, vals):
        """Set postal_id automatically on create, based on zip."""
        for val in vals:
            if val.get('zip') and not val.get('postal_id'):
                postal = self.env['shipping.cost']._get_postal_from_zip(val['zip'])
                if postal:
                    val['postal_id'] = postal.id
        return super().create(vals)

    def write(self, vals):
        """Update postal_id automatically when zip changes."""
        res = super().write(vals)
        if 'zip' in vals:
            for partner in self:
                postal = self.env['shipping.cost']._get_postal_from_zip(partner.zip)
                partner.postal_id = postal.id if postal else False
        return res


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    name = fields.Char(string='Postal code')
    postal_ids = fields.One2many('postal.code', 'state_id')
    cost = fields.Float(String='Cost')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_diameter = fields.Text(string="Product Diameter (mm)")
    main_kit_product = fields.Boolean('Main Kit Prodcut')
    area_m2_from = fields.Integer()
    area_m2_to = fields.Integer()
    product_type = fields.Selection(
        [
            ('base', 'Base'),
            ('upgraded', 'Upgraded'),
            ('premium', 'Premium'),
        ],
        string="Product Type"
    )

    m3_h = fields.Float(string="Flow Rate (m³/h)")

    prod_capacity = fields.Float(string="Product Capacity")







class SaleOrderProductLine(models.Model):
    _name = 'sale.order.product.line'
    _description = 'Filtered Products for Sale Order'

    sale_id = fields.Many2one('sale.order', string="Sale Order", ondelete="cascade")
    product_id = fields.Many2one('product.product', string="Product")
    product_diameter = fields.Text(string="Diameter (mm)")
    product_type = fields.Selection([
        ('base', 'Base'),
        ('upgraded', 'Upgraded'),
        ('premium', 'Premium'),
    ], string="Product Type")
    m3_h = fields.Float(string="M³/h")
    prod_capacity = fields.Float(string="Capacity")
    already_link = fields.Boolean(string='Linked', compute='_already_link_on_sale')

    sale_price = fields.Float(string="Sale Price")
    discount = fields.Float(string="Discount (%)", default=0.0)
    discounted_price = fields.Float(string="Discounted Price")

    def _already_link_on_sale(self):
        for line in self:
            link = False
            if line.sale_id and line.sale_id.state in ('sale', 'cancel'):
                link = True
            elif line.sale_id and line.sale_id.order_line:
                get_product = line.sale_id.order_line.filtered(lambda l: l.product_id.id == line.product_id.id)
                if get_product:
                    link = True
            line.already_link = link



    def action_add_to_order_line(self):
        """Add the selected product to the sale order lines."""
        for rec in self:
            if not rec.sale_id:
                raise UserError("No related Sale Order found.")
            if not rec.product_id:
                raise UserError("No product selected to add.")

            order = rec.sale_id

            # Check if the product is already in order lines
            existing_line = order.order_line.filtered(lambda l: l.product_id.id == rec.product_id.id)
            kit_exist = order.order_line.filtered(lambda l: l.product_id.main_kit_product == True)
            if existing_line:
                # If already exists, increase quantity
                existing_line.product_uom_qty += 1
            else:
                # Otherwise create a new sale.order.line
                self.env['sale.order.line'].create({
                    'order_id': order.id,
                    'product_id': rec.product_id.id,
                    'name': rec.product_id.display_name,
                    'product_uom_qty': 1,
                    'price_unit': rec.sale_price,
                    'tax_ids': [(6, 0, rec.product_id.taxes_id.ids)],
                    'part_of_id': kit_exist[0].product_id.id if kit_exist else False,
                })


class ProductProduct(models.Model):
    _inherit = "product.product"

    product_type = fields.Selection(related="product_tmpl_id.product_type", store=True, readonly=True)
    is_radial_pipe = fields.Boolean('Is Radial Pipe')

    @api.depends('list_price', 'price_extra', 'standard_price')
    @api.depends_context('uom')
    def _compute_product_lst_price(self):
        to_uom = None
        if 'uom' in self.env.context:
            to_uom = self.env['uom.uom'].browse(self.env.context['uom'])

        for product in self:
            if to_uom:
                list_price = product.uom_id._compute_price(product.list_price, to_uom)
            else:
                list_price = product.list_price
            if not product.categ_id:
                product.lst_price = list_price + product.price_extra
            else:
                product.lst_price = product.standard_price * product.categ_id.x_factor if product.categ_id.x_factor else 1

    # @api.depends('standard_price')
    # @api.onchange('standard_price')
    # def _compute_sale_price_variant(self):
    #     """When cost changes on a variant, update its sale price if category is 'Kit'."""
    #     for product in self:
    #         category = product.categ_id
    #         if product:
    #             if category and category.x_factor:
    #                 product.lst_price = product.standard_price * category.x_factor if category.x_factor else 1

    # @api.depends('standard_price', 'categ_id.x_factor', 'categ_id.name')
    # def _compute_lst_price_from_factor(self):
    #     """Ensure lst_price updates automatically if category is 'Kit'."""
    #     for product in self:
    #         category = product.categ_id
    #         if category and category.name.lower() == 'kit' and category.x_factor:
    #             product.lst_price = product.standard_price * category.x_factor



class AlrightnessPricess(models.Model):
    _name = "alrightness.pricess"
    _description = 'Alrightness Pricess'


    name = fields.Char(string="Name")

    area = fields.Float(string="Area 1 (m²)")
    area2 = fields.Float(string="Area 2 (m²)")
    area3 = fields.Float(string="Area 3 (m²)")
    area4 = fields.Float(string="Area 4 (m²)")

    guide_price_1 = fields.Float(string="Guide Price 1")
    guide_price_2 = fields.Float(string="Guide Price 2")
    guide_price_3 = fields.Float(string="Guide Price 3")
    guide_price_4 = fields.Float(string="Guide Price 4")


    @api.onchange('guide_price_1')
    def _change_guide_price(self):
        for x in self:
            x.guide_price_2 = x.guide_price_1 * 2
            x.guide_price_3 = x.guide_price_1 * 3
            x.guide_price_4 = x.guide_price_1 * 4



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    part_of_id = fields.Many2one('product.product',string="Part Of")


class StockRule(models.Model):
    _inherit = 'stock.rule'

    @api.model
    def _run_manufacture(self, procurements):
        """
        Extends Odoo's _run_manufacture() to also attach 'part_of_id' products
        as raw materials in Manufacturing Orders linked to a Sale Order.
        """
        result = super()._run_manufacture(procurements)

        for procurement, rule in procurements:
            product = procurement.product_id
            sale_line_id = procurement.values.get('sale_line_id')
            if not sale_line_id:
                continue

            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            order = sale_line.order_id

            # Find the manufacturing order created for this product
            mo_domain = [
                ('product_id', '=', product.id),
                ('origin', '=', procurement.origin or order.name)
            ]
            mo = self.env['mrp.production'].search(mo_domain, limit=1)
            if not mo:
                continue

            # Find related sale order lines whose "part_of_id" = this product
            related_lines = order.order_line.filtered(
                lambda l: l.part_of_id and l.part_of_id == sale_line.product_id
            )

            for comp_line in related_lines:
                self.env['stock.move'].create({
                    'description_picking': comp_line.product_id.display_name,
                    'product_id': comp_line.product_id.id,
                    'product_uom_qty': comp_line.product_uom_qty,
                    'product_uom': comp_line.product_uom_id.id,
                    'location_id': mo.location_src_id.id,
                    'location_dest_id': mo.location_dest_id.id,
                    'raw_material_production_id': mo.id,
                    'company_id': mo.company_id.id,
                    'state': 'draft',
                    'sale_line_id': comp_line.id,
                })

        return result


class PlacementConfig(models.Model):
    _name = "placement.config"
    _description = 'Placement Config'


    name = fields.Char(string="Name")

    place_type = fields.Selection(
        [('roof_vents', 'Roof Vents'), ('wall_cowl', 'Wall Cowl')],
        string='Placement'
    )
    diameter = fields.Integer(string="Diameter (mm)")
    quantity = fields.Integer(string="QTY")
    product_id = fields.Many2one('product.product', string="Product")




class ShippingCost(models.Model):
    _name = 'shipping.cost'
    _description = 'Shipping Cost'

    name = fields.Char(string='Postal code')
    cost = fields.Float(string='Cost')
    country_id = fields.Many2one('res.country', string="Country")

    @api.model
    def _get_postal_from_zip(self, zip_code):
        """Find matching shipping.cost record by checking prefixes of zip (5→4→3→2)."""
        if not zip_code:
            return False
        zip_code = zip_code.strip().upper()
        ShippingCost = self.env['shipping.cost']
        for length in [5, 4, 3, 2]:
            prefix = zip_code[:length]
            postal = ShippingCost.search([('name', '=', prefix)], limit=1)
            if postal:
                return postal
        return False


class ResCountry(models.Model):
    _inherit = 'res.country'

    shipping_cost_ids = fields.One2many('shipping.cost','country_id')


class ProductCategory(models.Model):
    _inherit = 'product.category'

    x_factor = fields.Float(
        string='X Factor',
        default=2.25,
        help='Custom multiplier factor for this category'
    )