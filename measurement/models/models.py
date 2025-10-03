from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    floor_type = fields.Selection(
        [('concrete', 'Concrete'), ('timber', 'Timber')],
        string='Floor Type'
    )
    place_type = fields.Selection(
        [('top', 'Top'), ('wall', 'Wall')],
        string='Placement'
    )

    no_of_bedrooms = fields.Integer(string="No. of Bedrooms")
    dwelling_total_area = fields.Float(string="Dwelling Total Area (sq m)")
    area_rate = fields.Float(string="Area Rate", compute="_compute_area_rate", store=True)
    bedroom_rate = fields.Float(string="Bedroom Rate", compute="_compute_bedroom_rate", store=True)
    extract_rate = fields.Float(string="Extract Rate", compute="_compute_extract_rate", store=True)
    correct_rate = fields.Float(string="Correct Rate", compute="_compute_correct_rate", store=True)
    req_cont_trickle = fields.Float(string="Required Continious Trickle")
    m3_h = fields.Float(string="M3/H")

    room_measurement_ids = fields.One2many('room.measurement', 'order_id', string="Room Measurements")
    commission_table_ids = fields.One2many('commission.table', 'order_id', string="Commissioning Table")
    floor_name_ids = fields.Many2many('floor.names', 'sale_order_floor_rel', 'order_id', 'floor_id', string="Floors")


    basic_prod = fields.Many2one('product.product', string="Basic Product" ,domain="[('product_type', '=', 'base')]")
    upgraded_prod = fields.Many2one('product.product', string="Upgraded Product" ,domain="[('product_type', '=', 'upgraded')]")
    premium_prod = fields.Many2one('product.product', string="Premium Product", domain="[('product_type', '=', 'premium')]")

    product_line_ids = fields.One2many('sale.order.product.line', 'sale_id', string="Products (Filtered)")

    def action_get_products(self):
        for order in self:
            if not order.m3_h or order.m3_h == 0.0:
                raise UserError("You must do all the process to set the M3/H value before getting products.")
            # Clear and reload products
            products = self.env['product.template'].search([('product_diameter', '>', 0)])
            order.product_line_ids = [(5, 0, 0)]
            lines = []

            for prod in products:
                vals = {
                    'sale_id': order.id,
                    'product_id': prod.product_variant_id.id,
                    'product_diameter': prod.product_diameter,
                    'product_type': prod.product_type,
                    'm3_h': prod.m3_h,
                    'prod_capacity': (order.m3_h / prod.m3_h * 100) if order.m3_h and prod.m3_h else 0.0,
                }
                lines.append((0, 0, vals))

            order.product_line_ids = lines

            # --- Now pick the best products per type ---
            # group lines by type
            base_line = max(order.product_line_ids.filtered(lambda l: l.product_type == 'base'),
                            key=lambda l: l.prod_capacity, default=False)
            upgraded_line = max(order.product_line_ids.filtered(lambda l: l.product_type == 'upgraded'),
                                key=lambda l: l.prod_capacity, default=False)
            premium_line = max(order.product_line_ids.filtered(lambda l: l.product_type == 'premium'),
                               key=lambda l: l.prod_capacity, default=False)

            # assign best products to sale.order fields
            order.basic_prod = base_line.product_id.id if base_line else False
            order.upgraded_prod = upgraded_line.product_id.id if upgraded_line else False
            order.premium_prod = premium_line.product_id.id if premium_line else False

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

    @api.onchange('req_cont_trickle')
    def _m3_h(self):
        for order in self:
            order.m3_h = order.req_cont_trickle * 3.6


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


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_diameter = fields.Float(string="Product Diameter (mm)")

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


# class SaleOrderLine(models.Model):
#     _inherit = 'sale.order.line'
#
#     sale_id = fields.Many2one('sale.order', string="Sale Order", ondelete="cascade")
#
#     prod_capacity = fields.Float(string="Product Capacity", readonly=True)
#     product_diameter = fields.Float(string="Product Diameter (mm)")
#
#     product_type = fields.Selection(
#         [
#             ('base', 'Base'),
#             ('upgraded', 'Upgraded'),
#             ('premium', 'Premium'),
#         ],
#         string="Product Type"
#     )
#
#     m3_h = fields.Float(string="Flow Rate (m³/h)")



class SaleOrderProductLine(models.Model):
    _name = 'sale.order.product.line'
    _description = 'Filtered Products for Sale Order'

    sale_id = fields.Many2one('sale.order', string="Sale Order", ondelete="cascade")
    product_id = fields.Many2one('product.product', string="Product")
    product_diameter = fields.Float(string="Diameter (mm)")
    product_type = fields.Selection([
        ('base', 'Base'),
        ('upgraded', 'Upgraded'),
        ('premium', 'Premium'),
    ], string="Product Type")
    m3_h = fields.Float(string="M³/h")
    prod_capacity = fields.Float(string="Capacity")


class ProductProduct(models.Model):
    _inherit = "product.product"

    product_type = fields.Selection(related="product_tmpl_id.product_type", store=True, readonly=True)
