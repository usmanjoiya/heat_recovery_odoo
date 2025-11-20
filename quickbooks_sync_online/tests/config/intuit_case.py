# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import datetime, timedelta

from odoo.tools import convert_file
from odoo.tests import tagged, TransactionCase
from odoo.modules.module import get_resource_from_path


IMPORT_MODELS_ALL = [
    'qbo.map.term',
    'qbo.map.payment.method',
]
IMPORT_MODELS_BY_BATCH = [
    'qbo.map.account',
    'qbo.map.tax',
    'qbo.map.taxcode',
    'qbo.map.partner',
    'qbo.map.product',
]
request_client = 'intuitlib.client.AuthClient.refresh'


class IntuitCred:

    qbo_env = 'sandbox'

    company_id = 0000000000000000000
    client_id = 'client_id_kl3j4h5f234kl5jfh200Y'
    client_secret = 'client_secret_zlxjdfhbl34kuj5vh34'

    qbo_access_token = 'access_token_kderW#$V%vSDFDFGDFGdfgGDRTH'
    qbo_refresh_token = 'refresh_token_kjahc_SADfSDdghscnaseir34clkdfn'

    auth_url = 'https://appcenter.intuit.com/connect/oauth2?blablabla'
    sequrity_group = 'quickbooks_sync_online.qbo_security_group_manager'


@tagged('-at_install', 'post_install')
class OdooCompanyInit(TransactionCase):

    def setUp(self):
        super(OdooCompanyInit, self).setUp()
        self._load_xml('init_company.xml')
        self.company = self.env.ref('quickbooks_sync_online.test_odoo_company')
        self.company.write({
            'qbo_client_id': IntuitCred.client_id,
            'qbo_client_secret': IntuitCred.client_secret,
            'qbo_company_id': IntuitCred.company_id,
            'qbo_environment': IntuitCred.qbo_env,
            'partner_id': self.env.ref('quickbooks_sync_online.test_main_partner').id,
            'qbo_export_out_invoice': True,
            'qbo_export_in_invoice': True,
            'qbo_export_out_refund': True,
            'qbo_export_in_refund': True,
        })
        self.user = self.env['res.users'].with_context({
            'no_reset_password': True,
        }).create({
            'name': 'Test QBO Odoo User',
            'company_id': self.company.id,
            'company_ids': self.company.ids,
            'login': 'user',
            'email': 'user@intuit.com',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(IntuitCred.sequrity_group).id,
            ])],
        })
        self.settings = self.env['res.config.settings'].create({
            'company_id': self.company.id,
        })

    def _load_xml(self, filename):
        file_path = get_resource_from_path('quickbooks_sync_online', 'tests/data', filename)
        convert_file(
            self.env, 'quickbooks_sync_online', 'tests/data/%s' % filename,
            {}, 'init', False, 'test', file_path,
        )

    def _set_up_connection(self):
        vals = {
            'qbo_access_token': IntuitCred.qbo_access_token,
            'qbo_refresh_token': IntuitCred.qbo_refresh_token,
            'access_token_update_point': datetime.now() + timedelta(hours=1),
            'refresh_token_update_point': datetime.now() + timedelta(days=100),
        }
        self.company.write(vals)
