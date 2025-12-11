# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import re

from werkzeug.exceptions import BadRequest

from odoo import http, SUPERUSER_ID


def get_number_after_dot(s):
    match = re.search(r'\.(\d+)$', s)
    if match:
        return int(match.group(1))
    return None


class OAuthController(http.Controller):

    @http.route('/qbo/callback', type='http', auth='user')
    def callback(self, state, code, realmId, *args, **kw):
        """Intuit authentication response handler."""

        company_id = get_number_after_dot(state)

        if not company_id:
            return BadRequest('Bad csrf! Rejected!')

        company = http.request.env['res.company']\
            .with_user(SUPERUSER_ID).browse(company_id).exists()

        if not company:
            return BadRequest(f'Company (id={company_id}) not found! Rejected!')

        if state != company.qbo_csrf_token:
            return BadRequest('Invalid csrf! Rejected!')

        client = company._get_qbo_auth_client(exclude_access_token=True)
        client.get_bearer_token(code, realm_id=realmId)

        company.qbo_company_id = realmId
        company._update_from_auth_client(client)
        company._validate_intuit_company_info()

        company._compute_next_call()

        return http.request.redirect('/web')
