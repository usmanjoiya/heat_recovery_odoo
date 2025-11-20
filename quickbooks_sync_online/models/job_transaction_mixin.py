# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, models, fields, SUPERUSER_ID


class JobTransactionMixin(models.AbstractModel):
    _name = 'job.transaction.mixin'
    _description = 'Job Transaction Mixin'

    job_transaction_count = fields.Integer(
        string='Job Transaction Count',
        copy=False,
    )

    def increment_counter(self):
        self.ensure_one()
        self.job_transaction_count += 1

    def increment_counter_force(self):
        with self.env.registry.cursor() as new_cr:
            new_env = api.Environment(new_cr, SUPERUSER_ID, {})
            self.with_env(new_env).increment_counter()

    def update_transaction_kwargs(self):
        self.ensure_one()
        return {'check_external': True} if self.job_transaction_count else {}
