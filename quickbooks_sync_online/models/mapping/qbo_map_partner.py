# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import logging

import pycountry

from odoo import fields, models

from ..utils import QboClass

_logger = logging.getLogger(__name__)

try:
    from quickbooks.objects.customer import Customer
    from quickbooks.objects.vendor import Vendor
except (ImportError, IOError) as ex:
    _logger.error(ex)


class QboMapPartner(models.Model):
    _name = 'qbo.map.partner'
    _inherit = 'qbo.map.mixin'
    _description = 'Qbo Map Partner'

    _qbo_lib_class = QboClass(Customer, Vendor)

    _res_model = 'res.partner'
    _related_field = 'partner_id'
    _reverse_field = 'qbo_partner_ids'
    _odoo_routes = {
        'active': ('["Active"]', True),
        'name.display_name': ('["DisplayName"]', ''),
        'name.given_name': ('["GivenName"]', ''),
        'name.suffix': ('["Suffix"]', ''),
        'email': ('["PrimaryEmailAddr"]["Address"]', ''),
        'phone': ('["PrimaryPhone"]["FreeFormNumber"]', ''),
        'mobile': ('["Mobile"]["FreeFormNumber"]', ''),
        'city': ('["BillAddr"]["City"]', ''),
        'street': ('["BillAddr"]["Line1"]', ''),
        'zip': ('["BillAddr"]["PostalCode"]', ''),
        'country_id.iso_code': ('["BillAddr"]["Country"]', ''),
        'country_id.state_name': ('["BillAddr"]["CountrySubDivisionCode"]', ''),
        'currency_id.currency_name': ('["CurrencyRef"]["value"]', ''),
        'company_name': ('["CompanyName"]', ''),
        'comment': ('["Notes"]', ''),
    }
    _map_routes = {
        'qbo_name': ('["DisplayName"]', ''),
    }

    partner_id = fields.Many2one(
        comodel_name=_res_model,
        string='ODOO Partner',
    )

    def _update_odoo_search_domain(self, domain):
        self.ensure_one()

        qbo_object_body = json.loads(self.qbo_object)
        dirty_vals = self._parse_routes(qbo_object_body, self.get_odoo_routes())
        cleaned_vals = self._remove_dots(dirty_vals)
        name = self._parse_name(cleaned_vals)

        domain_list = [[('name', '=', name)]]

        email = cleaned_vals['email']
        if email:
            domain_list.insert(0, [('email', '=', email)])

        return domain_list

    def _parse_country_state(self, vals):
        kwargs = {}
        country_id = state_id = False

        country_alias = vals['country_id']['iso_code']
        if country_alias and len(country_alias) == 3:
            kwargs['alpha_3'] = country_alias
        elif country_alias:
            kwargs['name'] = country_alias

        py_country = pycountry.countries.get(**kwargs) if kwargs else None

        if py_country:
            country_id = self.env['res.country'].search([
                ('code', '=', py_country.alpha_2),
            ], limit=1).id

        state_name = vals['country_id']['state_name']
        if state_name and country_id:
            state_id = self.env['res.country.state'].search([
                ('name', '=', state_name),
                ('country_id', '=', country_id)
            ]).id
        return country_id, state_id

    def _extract_currency_name(self, lower=False):
        qbo_object_body = json.loads(self.qbo_object)
        dirty_vals = self._parse_routes(qbo_object_body, self.get_odoo_routes())
        cleaned_vals = self._remove_dots(dirty_vals)
        currency_name = cleaned_vals['currency_id']['currency_name'] or ''
        return currency_name.lower() if lower else currency_name

    def _to_odoo_currency(self, vals):
        currency_id = False
        currency_name = vals['currency_id']['currency_name']

        if currency_name:
            currency_id = self.env['res.currency'].search([
                ('name', '=', currency_name),
            ]).id
        return currency_id

    def _parse_name(self, vals):
        suffix = f'({self.qbo_lib_type})'
        currency_ref = vals['currency_id']['currency_name'] or ''
        name = vals['name']['display_name']

        name = name.replace(suffix, '').strip()
        if currency_ref:
            name = name.replace(f'[{currency_ref}]', '').strip()
        return name

    def _adjust_odoo_values(self, vals):
        res = super(QboMapPartner, self)._adjust_odoo_values(vals)
        name = self._parse_name(res)
        currency_id = self._to_odoo_currency(res)
        country_id, state_id = self._parse_country_state(res)
        company_name = res.pop('company_name', False)

        vals_to_update = {
            'name': name,
            'country_id': country_id,
            'state_id': state_id,
            'currency_id': currency_id,
            'is_company': not bool(company_name),  # TODO: assign parent partner (parent_id)
        }
        if self.qbo_lib_type == 'customer':
            vals_to_update['customer_rank'] = 1
        else:
            vals_to_update['supplier_rank'] = 1

        res.update(vals_to_update)
        return res
