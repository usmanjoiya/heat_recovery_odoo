# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class QboHelpWizard(models.TransientModel):
    _name = 'qbo.help.wizard'
    _description = 'Explicit indication of partner type.'

    qbo_partner_type = fields.Selection(
        selection=[
            ('customer', 'Customer'),
            ('vendor', 'Vendor'),
            ('customer,vendor', 'Both of them'),
        ],
        string='Export Partner(s) as',
        default='customer',
    )

    information = fields.Text(
        string='Information',
    )

    def run_wizard(self, name, view_id, ctx):
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
            'context': ctx,
        }

    def submit_params(self):
        active_ids = self.env.context.get('active_ids')
        partners = self.env['res.partner'].browse(active_ids)
        ctx = {
            'qbo_partner_type': self.qbo_partner_type,
            'skip_qbo_partner_wizard': True,
        }
        partners.with_context(**ctx).export_partner_to_qbo()
