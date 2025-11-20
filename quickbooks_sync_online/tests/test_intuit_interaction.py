# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import datetime, date
from unittest.mock import patch

from odoo.tests import tagged
from odoo.exceptions import ValidationError, UserError

from .config.request_patcher import RequestPatcher
from .config.intuit_case import (
    IMPORT_MODELS_ALL,
    IMPORT_MODELS_BY_BATCH,
    request_client,
    OdooCompanyInit,
)

from ..models.utils import TAXABLE, NON_TAXABLE


PRODUCT = 'item'
VENDOR = 'vendor'
CUSTOMER = 'customer'
INVOICE = 'invoice'
CREDIT_NOTE = 'creditmemo'
BILL = 'bill'
PAYMENT = 'payment'
SALE_ORDER = 'salesreceipt'


@tagged('-at_install', '-standard', 'post_install', 'qbo_test_api')
class TestIntuitInteraction(OdooCompanyInit):

    def setUp(self):
        super(TestIntuitInteraction, self).setUp()
        self._ctx = {
            'queue_job__no_delay': 1,
            'apply_company': self.company.id,
        }
        self.patcher = RequestPatcher()
        self._set_up_connection()
        self._fill_the_dadabase()
        self._load_xml('init_accounts.xml')
        self.map_default_company_outstanding_account()
        self.map_default_company_stock_account()

        def intuit_is_us_company_patch(*args, **kw):
            return True

        self.patch(type(self.company), 'intuit_is_us_company', intuit_is_us_company_patch)

    @patch(request_client)
    def _fill_the_dadabase(self, *args):
        for _name in IMPORT_MODELS_ALL:
            model_id = self.env[_name]
            for map_type in model_id.qbo_map_list():
                with self.patcher(map_type):
                    model_id._get_all_data_from_qbo(self.company, map_type)

        for _name in IMPORT_MODELS_BY_BATCH:
            model_id = self.env[_name]
            for map_type in model_id.qbo_map_list():
                with self.patcher(map_type):
                    model_id._get_data_from_qbo(self.company, map_type)

    def create_tax(self):
        return self.env['account.tax'].create({
            'name': '15% Test',
            'type_tax_use': 'sale',
            'amount': 15,
            'tax_group_id': self.env.ref('quickbooks_sync_online.tax_group_15_test').id,
            'company_id': self.company.id,
            'amount_type': 'percent',
        })

    def proxy_models(self):
        model_names = sum([IMPORT_MODELS_ALL, IMPORT_MODELS_BY_BATCH], [])
        return [self.env[name] for name in model_names]

    def map_all_accounts(self):
        intuit_accounts = self.env['qbo.map.account'].search([
            ('company_id', '=', self.company.id),
        ])
        intuit_accounts.try_to_map(do_create=False)
        return intuit_accounts.filtered('account_id')

    def map_cost_of_gods_sold(self):
        account = self.env['qbo.map.account'].search([
            ('qbo_name', '=', 'Cost of Goods Sold (test)'),
            ('company_id', '=', self.company.id),
        ])
        account.try_to_map(do_create=False)

    def map_sales_income(self):
        account = self.env['qbo.map.account'].search([
            ('qbo_name', '=', 'Sales of Product Income (test)'),
            ('company_id', '=', self.company.id),
        ])
        account.try_to_map(do_create=False)

    def map_default_company_outstanding_account(self):
        self.company.write({
            'account_journal_payment_debit_account_id':
                self.env.ref('quickbooks_sync_online.o_receipts').id,
            'account_journal_payment_credit_account_id':
                self.env.ref('quickbooks_sync_online.o_payments').id,
        })

    def map_default_company_stock_account(self):
        self.company.write({
            'qbo_default_stock_valuation_account_id': self.env.ref('quickbooks_sync_online.stk').id,
        })

    def map_inventory_asset(self):
        account = self.env['qbo.map.account'].search([
            ('qbo_name', '=', 'Inventory Asset (test)'),
            ('company_id', '=', self.company.id),
        ])
        account.try_to_map(do_create=False)

    def map_account_payable(self):
        account = self.env['qbo.map.account'].search([
            ('qbo_name', '=', 'Accounts Payable (A/P) (test)'),
            ('company_id', '=', self.company.id),
        ])
        account.try_to_map(do_create=False)

    def map_default_payment(self):
        self.company.write({
            'qbo_def_journal_id': self.env.ref('quickbooks_sync_online.bank_journal').id,
        })
        cash_method = self.env['qbo.map.payment.method'].search([
            ('qbo_id', '=', '1'),
            ('company_id', '=', self.company.id),
        ])
        cash_method.write({
            'journal_id': self.env.ref('quickbooks_sync_online.cash_journal').id,
        })

    def test_import_count(self):
        for model_id in self.proxy_models():
            for map_type in model_id.qbo_map_list():
                records_count = model_id.search_count([
                    ('company_id', '=', self.company.id),
                    ('qbo_lib_type', '=', map_type),
                ])
                remote_records_count = self.patcher.get_records_count(map_type)
                self.assertEqual(records_count, remote_records_count)

    def test_map_or_create_inventory_product_from_map_object(self):
        inventory_214 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '214'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(inventory_214.qbo_name, 'Flag_AWSECrfaew')
        self.assertEqual(inventory_214.display_name, '[8976] Flag_AWSECrfaew')
        self.assertEqual(inventory_214.stock_keeping_unit, '8976')
        self.assertEqual(inventory_214.product_id.id, False)
        self.assertEqual(inventory_214.qbo_lib_type, PRODUCT)
        self.assertEqual(inventory_214.company_id, self.company)

        inventory_214._create_odoo_instance()
        product1 = inventory_214.product_id

        self.assertTrue(product1.active)
        self.assertEqual(product1.name, 'Flag_AWSECrfaew')
        self.assertEqual(product1.type, 'product')
        self.assertEqual(product1.description_sale, 'Sale Description')
        self.assertEqual(product1.description_purchase, '')
        self.assertEqual(product1.default_code, '8976')
        self.assertEqual(product1.list_price, 90)
        self.assertEqual(product1.standard_price, 78)

        # Another one
        inventory_215 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '215'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(inventory_215.qbo_name, 'Corner Desk Black_jhdrThg')
        self.assertEqual(inventory_215.display_name, '[FURN_1118_1] Corner Desk Black_jhdrThg')
        self.assertEqual(inventory_215.stock_keeping_unit, 'FURN_1118_1')
        self.assertEqual(inventory_215.product_id.id, False)
        self.assertEqual(inventory_215.qbo_lib_type, PRODUCT)
        self.assertEqual(inventory_215.company_id, self.company)

        inventory_215._create_odoo_instance()
        product2 = inventory_215.product_id

        self.assertTrue(product2.active)
        self.assertEqual(product2.name, 'Corner Desk Black_jhdrThg')
        self.assertEqual(product2.type, 'product')
        self.assertEqual(product2.description_sale, False)
        self.assertEqual(product2.description_purchase, '')
        self.assertEqual(product2.default_code, 'FURN_1118_1')
        self.assertEqual(product2.list_price, 85)
        self.assertEqual(product2.standard_price, 78)

        # Unmap models and create odoo product copy
        records = inventory_214 + inventory_215
        records.write({'product_id': False})
        product1.copy({
            'name': 'Flag_AWSECrfaew',
            'default_code': '8976',
        })
        # Try to map
        records.try_to_map(summary=False)
        # Check mapping result
        self.assertEqual(inventory_214.product_id.id, False)
        self.assertEqual(inventory_215.product_id.id, product2.id)

    def test_map_or_create_consumable_product_from_map_object(self):
        consum_127 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '127'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(consum_127.qbo_name, 'Table_Ert254g')
        self.assertEqual(consum_127.display_name, '[89977898] Table_Ert254g')
        self.assertEqual(consum_127.stock_keeping_unit, '89977898')
        self.assertEqual(consum_127.product_id.id, False)
        self.assertEqual(consum_127.qbo_lib_type, PRODUCT)
        self.assertEqual(consum_127.company_id, self.company)

        consum_127._create_odoo_instance()
        product1 = consum_127.product_id

        self.assertTrue(product1.active)
        self.assertEqual(product1.name, 'Table_Ert254g')
        self.assertEqual(product1.type, 'consu')
        self.assertEqual(product1.description_sale, False)
        self.assertEqual(product1.description_purchase, '')
        self.assertEqual(product1.default_code, '89977898')
        self.assertEqual(product1.list_price, 99.9)
        self.assertEqual(product1.standard_price, 67.8)

        # Another one
        consum_137 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '137'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(consum_137.qbo_name, 'Another Table_Ert254g')
        self.assertEqual(consum_137.display_name, 'Another Table_Ert254g')
        self.assertEqual(consum_137.stock_keeping_unit, False)
        self.assertEqual(consum_137.product_id.id, False)
        self.assertEqual(consum_137.qbo_lib_type, PRODUCT)
        self.assertEqual(consum_137.company_id, self.company)

        consum_137._create_odoo_instance()
        product2 = consum_137.product_id

        self.assertTrue(product2.active)
        self.assertEqual(product2.name, 'Another Table_Ert254g')
        self.assertEqual(product2.type, 'consu')
        self.assertEqual(product2.description_sale, False)
        self.assertEqual(product2.description_purchase, 'Some purchase description..')
        self.assertEqual(product2.default_code, False)
        self.assertEqual(product2.list_price, 89)
        self.assertEqual(product2.standard_price, 0)

        # Unmap models and create odoo product copy
        records = consum_127 + consum_137
        records.write({'product_id': False})
        product1.copy({
            'name': 'Table_Ert254g',
            'default_code': '89977898',
        })
        # Try to map
        records.try_to_map(summary=False)
        # Check mapping result
        self.assertEqual(consum_127.product_id.id, False)
        self.assertEqual(consum_137.product_id.id, product2.id)

    def test_map_or_create_service_product_from_map_object(self):
        service_3 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '3'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(service_3.qbo_name, 'Concrete3_QDSVCrt')
        self.assertEqual(service_3.display_name, 'Concrete3_QDSVCrt')
        self.assertEqual(service_3.stock_keeping_unit, False)
        self.assertEqual(service_3.product_id.id, False)
        self.assertEqual(service_3.qbo_lib_type, PRODUCT)
        self.assertEqual(service_3.company_id, self.company)

        service_3._create_odoo_instance()
        product1 = service_3.product_id

        self.assertTrue(product1.active)
        self.assertEqual(product1.name, 'Concrete3_QDSVCrt')
        self.assertEqual(product1.type, 'service')
        self.assertEqual(product1.description_sale, 'Concrete for fountain installation')
        self.assertEqual(product1.description_purchase, '')
        self.assertEqual(product1.default_code, False)
        self.assertEqual(product1.list_price, 0)
        self.assertEqual(product1.standard_price, 0)

        # Another one
        service_4 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '4'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(service_4.qbo_name, 'Design CevrTw45')
        self.assertEqual(service_4.display_name, 'Design CevrTw45')
        self.assertEqual(service_4.stock_keeping_unit, False)
        self.assertEqual(service_4.product_id.id, False)
        self.assertEqual(service_3.qbo_lib_type, PRODUCT)
        self.assertEqual(service_3.company_id, self.company)

        service_4._create_odoo_instance()
        product2 = service_4.product_id

        self.assertTrue(product2.active)
        self.assertEqual(product2.name, 'Design CevrTw45')
        self.assertEqual(product2.type, 'service')
        self.assertEqual(product2.description_sale, 'Custom Design')
        self.assertEqual(product2.description_purchase, '')
        self.assertEqual(product2.default_code, False)
        self.assertEqual(product2.list_price, 75)
        self.assertEqual(product2.standard_price, 0)

        # Unmap models and create odoo product copy
        records = service_3 + service_4
        records.write({'product_id': False})
        product1.copy({'name': 'Concrete3_QDSVCrt'})
        # Try to map
        records.try_to_map(summary=False)
        # Check mapping result
        self.assertEqual(service_3.product_id.id, False)
        self.assertEqual(service_4.product_id.id, product2.id)

    def test_map_or_create_unsupported_type_from_map_object(self):
        category_64 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '64'),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(category_64.qbo_name, 'T-Shirt Unisex')
        self.assertEqual(category_64.stock_keeping_unit, False)
        self.assertEqual(category_64.product_id.id, False)
        self.assertEqual(category_64.qbo_lib_type, PRODUCT)
        self.assertEqual(category_64.company_id, self.company)

        with self.assertRaises(ValidationError):
            category_64._create_odoo_instance()

    def test_map_or_create_customer_from_map_object(self):
        vals_customer_3 = {
            'country_id': {
                'iso_code': 'USA',
                'state_name': 'CA',
            },
            'currency_id': {
                'currency_name': 'USD',
            },
        }
        map_customer_2 = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '2'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(map_customer_2.qbo_name, 'Bill Windsurf Shop_acESRCdfg')
        self.assertEqual(map_customer_2.partner_id.id, False)
        self.assertEqual(map_customer_2.company_id, self.company)

        map_customer_2._create_odoo_instance()
        customer1 = map_customer_2.partner_id

        self.assertTrue(customer1.active)
        self.assertEqual(customer1.name, 'Bill Windsurf Shop_acESRCdfg')
        self.assertEqual(customer1.email, 'Surf_acESRCdfg@Intuit.com')
        self.assertEqual(customer1.phone, '789104354611')
        self.assertEqual(customer1.mobile, '1213156415')
        self.assertEqual(customer1.city, '12 Ocean Dr.')
        self.assertEqual(customer1.street, 'Half Moon Bay')
        self.assertEqual(customer1.zip, '94213')

        # currency_id = map_customer_2._to_odoo_currency(vals_customer_3)
        country_id, state_id = map_customer_2._parse_country_state(vals_customer_3)

        self.assertEqual(customer1.country_id.id, country_id)
        self.assertEqual(customer1.state_id.id, state_id)
        # self.assertEqual(customer1.currency_id.id, currency_id)

        self.assertEqual(customer1.is_company, False)  # There is a customer's related CompanyName
        self.assertEqual(customer1.comment.striptags(), 'Ipsum lorem')
        self.assertEqual(customer1.customer_rank, 1)

        # Unmap models and create odoo product copy
        map_customer_2.write({'partner_id': False})
        customer1_copy = customer1.copy()

        # Have the two similar email addresses
        map_customer_2.try_to_map(summary=False)
        self.assertEqual(map_customer_2.partner_id.id, False)

        # Map by email
        customer1.unlink()
        map_customer_2.try_to_map(summary=False)
        self.assertEqual(map_customer_2.partner_id, customer1_copy)

        # Map by name
        map_customer_2.write({'partner_id': False})
        customer1_copy.write({
            'name': 'Bill Windsurf Shop_acESRCdfg',
            'email': '__Surf_acESRCdfg@Intuit.com',
        })
        map_customer_2.try_to_map(summary=False)
        self.assertEqual(map_customer_2.partner_id, customer1_copy)

    def test_map_or_create_vendor_from_map_object(self):
        vals_vendor_30 = {
            'country_id': {
                'iso_code': 'US',
                'state_name': 'CA',
            },
            'currency_id': {
                'currency_name': 'USD',
            },
        }
        map_vendor_30 = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '30'),
            ('qbo_lib_type', '=', VENDOR),
            ('company_id', '=', self.company.id),
        ])
        self.assertEqual(map_vendor_30.qbo_name, 'Books by Bessie_sadfVcdt54')
        self.assertEqual(map_vendor_30.partner_id.id, False)
        self.assertEqual(map_vendor_30.company_id, self.company)

        map_vendor_30._create_odoo_instance()
        vendor1 = map_vendor_30.partner_id

        self.assertTrue(vendor1.active)
        self.assertEqual(vendor1.name, 'Books by Bessie_sadfVcdt54')
        self.assertEqual(vendor1.email, 'Books_sadfVcdt54@Intuit.com')
        self.assertEqual(vendor1.phone, '(650) 555-7745')
        self.assertEqual(vendor1.mobile, '')
        self.assertEqual(vendor1.city, 'Palo Alto')
        self.assertEqual(vendor1.street, '15 Main St.')
        self.assertEqual(vendor1.zip, '94303')

        # currency_id = map_vendor_30._to_odoo_currency(vals_vendor_30)
        country_id, state_id = map_vendor_30._parse_country_state(vals_vendor_30)

        self.assertEqual(vendor1.country_id.id, country_id)
        self.assertEqual(vendor1.state_id.id, state_id)
        # self.assertEqual(vendor1.currency_id.id, currency_id)

        self.assertEqual(vendor1.is_company, False)  # There is a vendors's related CompanyName
        self.assertEqual(vendor1.comment, '')
        self.assertEqual(vendor1.customer_rank, 0)
        self.assertEqual(vendor1.supplier_rank, 1)

        # Unmap models and create odoo product copy
        map_vendor_30.write({'partner_id': False})
        vendor1_copy = vendor1.copy()

        # Have the two similar email addresses
        map_vendor_30.try_to_map(summary=False)
        self.assertEqual(map_vendor_30.partner_id.id, False)

        # Map by email
        vendor1.unlink()
        map_vendor_30.try_to_map(summary=False)
        self.assertEqual(map_vendor_30.partner_id, vendor1_copy)

        # Map by name
        map_vendor_30.write({'partner_id': False})
        vendor1_copy.write({
            'name': 'Books by Bessie_sadfVcdt54',
            'email': '__Books_sadfVcdt54@Intuit.com',
        })
        map_vendor_30.try_to_map(summary=False)
        self.assertEqual(map_vendor_30.partner_id, vendor1_copy)

    def test_auto_map_accounts(self):
        mapped_account_ids = self.map_all_accounts().mapped('qbo_id')
        for qbo_id in ['33', '81', '79', '113']:
            self.assertIn(qbo_id, mapped_account_ids)

    @patch(request_client)
    def test_update_map_product_from_odoo_product(self, *args):
        # Unmap default company stock account
        self.company.write({
            'qbo_default_stock_valuation_account_id': False,
        })
        records = self.env['qbo.map.product'].search([
            ('qbo_id', 'in', ['67', '71']),
            ('company_id', '=', self.company.id),
        ])
        self.assertTrue(len(records) == 2)
        inventory_67 = records.filtered(lambda r: r.qbo_id == '67')
        inventory_71 = records.filtered(lambda r: r.qbo_id == '71')

        inventory_67.with_context(**self._ctx).create_instance_in_odoo()
        product1 = inventory_67.product_id
        self.assertTrue(product1.id)

        # Assert raise due to product has no a mapping
        inventory_67.write({'product_id': False})
        with self.assertRaises(ValidationError):
            product1._get_map_instance_or_raise(PRODUCT, self.company.id)

        # Assert raise due to product has the several mapping
        records.write({'product_id': product1.id})
        with self.assertRaises(ValidationError):
            product1._get_map_instance_or_raise(PRODUCT, self.company.id)

        inventory_71.write({'product_id': False})
        get_inventory_67 = product1._get_map_instance_or_raise(PRODUCT, self.company.id)
        self.assertEqual(inventory_67, get_inventory_67)

        # Assert raise due to unmapped accounts
        with self.assertRaises(ValidationError):
            product1._check_requirements(self.company)

        self.map_sales_income()
        self.map_cost_of_gods_sold()
        self.map_inventory_asset()
        product1._check_requirements(self.company)

        # Update product after all checks
        with self.patcher(PRODUCT):
            product1.with_context(**self._ctx).update_product_in_qbo()

    @patch(request_client)
    def test_update_map_partner_from_odoo_partner(self, *args):
        records = self.env['qbo.map.partner'].search([
            ('qbo_id', 'in', ['3', '4']),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])
        self.assertTrue(len(records) == 2)
        customer_3 = records.filtered(lambda r: r.qbo_id == '3')
        customer_4 = records.filtered(lambda r: r.qbo_id == '4')

        customer_3.with_context(**self._ctx).create_instance_in_odoo()
        partner1 = customer_3.partner_id
        self.assertTrue(partner1.id)

        # Deactivate the next code because there may be several map-objects
        # with the different currencies

        # # Assert raise due to patrner has no a mapping
        # customer_3.write({'partner_id': False})
        # with self.assertRaises(UserError):
        #     partner1.with_context(**self._ctx).update_partner_in_qbo()

        # # Assert raise due to patrner has the several mapping
        # records.write({'partner_id': partner1.id})
        # with self.assertRaises(UserError):
        #     partner1.with_context(**self._ctx).update_partner_in_qbo()

        customer_4.unlink()

        # Update the patrner after all checks
        with self.patcher(CUSTOMER):
            partner1.with_context(**self._ctx).update_partner_in_qbo()

    def test_check_qbo_duplicate_function(self):
        inventory_214 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '214'),
            ('company_id', '=', self.company.id),
        ])
        product1 = self.env['product.product'].create({
            'name': inventory_214.qbo_name,
            'default_code': inventory_214.stock_keeping_unit,
        })

        # Has a duplicate
        try:
            product1._check_qbo_duplicate(self.company.id)
        except ValidationError as ex:
            self.assertIn(
                'Product with the same name "%s" already exists in "Mapping/Products".'
                % product1.display_name,
                ex.args[0]
            )

        product2 = self.env['product.product'].create({
            'name': 'Random Name',
        })
        inventory_214.write({'product_id': product2.id})

        # Has a duplicate with the other related partner
        try:
            product1._check_qbo_duplicate(self.company.id)
        except ValidationError as ex:
            self.assertIn(
                'Product with the same name "%s" already exists in "Mapping/Products". '
                'Moreover it already has a related odoo object.'
                % product1.display_name,
                ex.args[0]
            )

        inventory_214.unlink()

        product1._check_qbo_duplicate(self.company.id)

    def test_check_constraints_export_customer_to_qbo(self):
        ctx = {
            'qbo_partner_type': CUSTOMER,
            'skip_qbo_partner_wizard': True,
        }
        ctx.update(self._ctx)
        partner1 = self.env['res.partner'].create({
            'name': 'John Wayne Customer',
        })
        # 1. No map-partner before export
        qbo_partner_ids = partner1.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(qbo_partner_ids)

        # 2. Assert raise due to more than one related map-objects exists
        map_partners = self.env['qbo.map.partner'].search([
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ], limit=2)
        self.assertTrue(len(map_partners) == 2)
        map_partners.write({'partner_id': partner1.id})

        with self.assertRaises(ValidationError):
            partner1.with_context(**ctx).export_partner_to_qbo()

        # 3. Export going to be skipped due to the one map-partner exists
        map_partners[0].write({'partner_id': False})
        instance_before = partner1.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        partner1.with_context(**ctx).export_partner_to_qbo()

        instance_after = partner1.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertEqual(instance_before, instance_after)

        # 4. Assert raise due to map-partner with the same name has already existed
        map_partners[1].write({
            'qbo_name': 'John Wayne Customer (customer)',
            'partner_id': False
        })
        with self.assertRaises(ValidationError):
            partner1.with_context(**ctx).export_partner_to_qbo()

        # 5. Assert raise due map-partner with the same name already exists other related partner
        partner2 = self.env['res.partner'].create({
            'name': 'John Wayne Customer2',
        })
        map_partners[1].write({
            'partner_id': partner2.id,
        })
        with self.assertRaises(ValidationError):
            partner1.with_context(**ctx).export_partner_to_qbo()

    @patch(request_client)
    def test_export_customer_to_qbo(self, *args):
        ctx = {
            'qbo_partner_type': CUSTOMER,
            'skip_qbo_partner_wizard': True,
        }
        ctx.update(self._ctx)
        partner = self.env['res.partner'].create({
            'name': 'John Wayne Customer',
        })
        # No map-partner before export
        map_partner = partner.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(map_partner)

        # Perform export
        self.assertTrue(partner.with_company(self.company).qbo_state == 'todo')

        with self.patcher(CUSTOMER):
            partner.with_context(**ctx).export_partner_to_qbo()

        # Map-partner exist
        map_partner = partner.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(map_partner) == 1)
        self.assertTrue(map_partner.qbo_lib_type == CUSTOMER)
        self.assertTrue(partner.with_company(self.company).qbo_state == 'proxy')

    def test_check_constraints_export_vendor_to_qbo(self):
        ctx = {
            'qbo_partner_type': VENDOR,
            'skip_qbo_partner_wizard': True,
        }
        ctx.update(self._ctx)
        partner1 = self.env['res.partner'].create({
            'name': 'John Wayne Vendor',
        })
        # 1. No map-partner before export
        qbo_partner_ids = partner1.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(qbo_partner_ids)

        # 2. Assert raise due to more than one related map-objects exists
        map_partners = self.env['qbo.map.partner'].search([
            ('qbo_lib_type', '=', VENDOR),
            ('company_id', '=', self.company.id),
        ], limit=2)
        self.assertTrue(len(map_partners) == 2)
        map_partners.write({'partner_id': partner1.id})

        with self.assertRaises(ValidationError):
            partner1.with_context(**ctx).export_partner_to_qbo()

        # 3. Export going to be skipped due to the one map-partner exists
        map_partners[0].write({'partner_id': False})
        instance_before = partner1.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        partner1.with_context(**ctx).export_partner_to_qbo()

        instance_after = partner1.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertEqual(instance_before, instance_after)

        # 4. Assert raise due to map-partner with the same name has already existed
        map_partners[1].write({
            'qbo_name': 'John Wayne Vendor (vendor)',
            'partner_id': False
        })
        with self.assertRaises(ValidationError):
            partner1.with_context(**ctx).export_partner_to_qbo()

        # 5. Assert raise due map-partner with the same name already exists other related partner
        partner2 = self.env['res.partner'].create({
            'name': 'John Wayne Vendor2',
        })
        map_partners[1].write({
            'partner_id': partner2.id,
        })
        with self.assertRaises(ValidationError):
            partner1.with_context(**ctx).export_partner_to_qbo()

    @patch(request_client)
    def test_export_vendor_to_qbo(self, *args):
        ctx = {
            'qbo_partner_type': VENDOR,
            'skip_qbo_partner_wizard': True,
        }
        ctx.update(self._ctx)
        partner = self.env['res.partner'].create({
            'name': 'John Wayne Vendor',
        })
        # No map-partner before export
        map_partner = partner.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(map_partner)

        # Perform export
        self.assertTrue(partner.with_company(self.company).qbo_state == 'todo')
        with self.patcher(VENDOR):
            partner.with_context(**ctx).export_partner_to_qbo()

        # Map-partner exist
        map_partner = partner.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(map_partner) == 1)
        self.assertTrue(map_partner.qbo_lib_type == VENDOR)
        self.assertTrue(partner.with_company(self.company).qbo_state == 'proxy')

    @patch(request_client)
    def test_export_inventory_product(self, *args):
        self.map_all_accounts()
        product = self.env['product.product'].create({
            'name': 'Inventory product',
            'type': 'product',
        })
        qbo_product_ids = product.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(qbo_product_ids)
        self.assertTrue(product.with_company(self.company).qbo_state == 'todo')

        with self.patcher(PRODUCT):
            product.with_context(**self._ctx).export_product_to_qbo()

        qbo_product_ids = product.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(qbo_product_ids) == 1)
        self.assertTrue(product.with_company(self.company).qbo_state == 'proxy')

    @patch(request_client)
    def test_check_constraints_export_inventory_product(self, *args):
        # Unmap default company stock account
        self.company.write({
            'qbo_default_stock_valuation_account_id': False,
        })
        product1 = self.env['product.product'].create({
            'name': 'Inventory product',
            'type': 'product',
        })

        # 1. No map-product before export
        qbo_product_ids = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(qbo_product_ids)
        self.assertTrue(product1.with_company(self.company).qbo_state == 'todo')

        # 2. Assert raise due to more than one related mapping exists
        map_products = self.env['qbo.map.product'].search([
            ('qbo_lib_type', '=', PRODUCT),
            ('company_id', '=', self.company.id),
        ], limit=2)
        self.assertTrue(len(map_products) == 2)
        map_products.write({'product_id': product1.id})

        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 3. Export going to be skipped due to the one map-product exists
        map_products[0].write({'product_id': False})
        instance_before = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        product1.with_context(**self._ctx).export_product_to_qbo()

        instance_after = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertEqual(instance_before, instance_after)

        # 4. Assert raise due to map-product with the same name has already existed
        map_products[1].write({
            'qbo_name': 'Inventory product',
            'product_id': False
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 5. Assert raise due map-product with the same name already exists other related product
        product2 = self.env['product.product'].create({
            'name': 'Inventory product',
        })
        map_products[1].write({
            'product_id': product2.id,
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 6. Assert raise due to unmapped accounts
        map_products.write({
            'qbo_name': 'Just erase names',
            'product_id': False,
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 7. Map only income account
        self.map_sales_income()
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 8. Map income + expense accounts
        self.map_sales_income()
        self.map_cost_of_gods_sold()
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 9. Map income + expense + inventory accounts
        self.map_sales_income()
        self.map_cost_of_gods_sold()
        self.map_inventory_asset()

        with self.patcher(PRODUCT):
            product1.with_context(**self._ctx).export_product_to_qbo()

        qbo_product_ids = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(qbo_product_ids) == 1)
        self.assertTrue(product1.with_company(self.company).qbo_state == 'proxy')

    @patch(request_client)
    def test_export_service_product(self, *args):
        self.map_all_accounts()
        product = self.env['product.product'].create({
            'name': 'Service product',
            'type': 'service',
        })
        qbo_product_ids = product.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(qbo_product_ids)
        self.assertTrue(product.with_company(self.company).qbo_state == 'todo')

        with self.patcher(PRODUCT):
            product.with_context(**self._ctx).export_product_to_qbo()

        qbo_product_ids = product.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(qbo_product_ids) == 1)
        self.assertTrue(product.with_company(self.company).qbo_state == 'proxy')

    @patch(request_client)
    def test_check_constraints_export_service_product(self, *args):
        product1 = self.env['product.product'].create({
            'name': 'Service product',
            'type': 'service',
        })
        self.assertTrue(product1.with_company(self.company).qbo_state == 'todo')

        # 1. No map-product before export
        qbo_product_ids = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(qbo_product_ids)

        # 2. Assert raise due to more than one related mapping exists
        map_products = self.env['qbo.map.product'].search([
            ('qbo_lib_type', '=', PRODUCT),
            ('company_id', '=', self.company.id),
        ], limit=2)
        self.assertTrue(len(map_products) == 2)
        map_products.write({'product_id': product1.id})

        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 3. Export going to be skipped due to the one map-product exists
        map_products[0].write({'product_id': False})
        instance_before = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        product1.with_context(**self._ctx).export_product_to_qbo()

        instance_after = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertEqual(instance_before, instance_after)

        # 4. Assert raise due to map-product with the same name has already existed
        map_products[1].write({
            'qbo_name': 'Service product',
            'product_id': False
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 5. Assert raise due map-product with the same name already exists other related product
        product2 = self.env['product.product'].create({
            'name': 'Service product',
        })
        map_products[1].write({
            'product_id': product2.id,
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 6. Assert raise due to unmapped accounts
        map_products.write({
            'qbo_name': 'Just erase names',
            'product_id': False,
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 7. Map only income account
        self.map_sales_income()
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 8. Map income + expense accounts
        self.map_sales_income()
        self.map_cost_of_gods_sold()

        with self.patcher(PRODUCT):
            product1.with_context(**self._ctx).export_product_to_qbo()

        qbo_product_ids = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(qbo_product_ids) == 1)
        self.assertTrue(product1.with_company(self.company).qbo_state == 'proxy')

    @patch(request_client)
    def test_export_consu_product(self, *args):
        self.map_all_accounts()
        product = self.env['product.product'].create({
            'name': 'Consumable product',
            'type': 'consu',
        })
        qbo_product_ids = product.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(qbo_product_ids)
        self.assertTrue(product.with_company(self.company).qbo_state == 'todo')

        with self.patcher(PRODUCT):
            product.with_context(**self._ctx).export_product_to_qbo()

        qbo_product_ids = product.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(qbo_product_ids) == 1)
        self.assertTrue(product.with_company(self.company).qbo_state == 'proxy')

    @patch(request_client)
    def test_check_constraints_export_consu_product(self, *args):
        product1 = self.env['product.product'].create({
            'name': 'Consumable product',
            'type': 'consu',
        })
        self.assertTrue(product1.with_company(self.company).qbo_state == 'todo')

        # 1. No map-product before export
        qbo_product_ids = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertFalse(qbo_product_ids)

        # 2. Assert raise due to more than one related mapping exists
        map_products = self.env['qbo.map.product'].search([
            ('qbo_lib_type', '=', PRODUCT),
            ('company_id', '=', self.company.id),
        ], limit=2)
        self.assertTrue(len(map_products) == 2)
        map_products.write({'product_id': product1.id})

        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 3. Export going to be skipped due to the one map-product exists
        map_products[0].write({'product_id': False})
        instance_before = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        product1.with_context(**self._ctx).export_product_to_qbo()

        instance_after = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertEqual(instance_before, instance_after)

        # 4. Assert raise due to map-product with the same name has already existed
        map_products[1].write({
            'qbo_name': 'Consumable product',
            'product_id': False
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 5. Assert raise due map-product with the same name already exists other related product
        product2 = self.env['product.product'].create({
            'name': 'Consumable product',
        })
        map_products[1].write({
            'product_id': product2.id,
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 6. Assert raise due to unmapped accounts
        map_products.write({
            'qbo_name': 'Just erase names',
            'product_id': False,
        })
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 7. Map only income account
        self.map_sales_income()
        with self.assertRaises(ValidationError):
            product1.with_context(**self._ctx).export_product_to_qbo()

        # 8. Map income + expense accounts
        self.map_sales_income()
        self.map_cost_of_gods_sold()

        with self.patcher(PRODUCT):
            product1.with_context(**self._ctx).export_product_to_qbo()

        qbo_product_ids = product1.qbo_product_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(qbo_product_ids) == 1)
        self.assertTrue(product1.with_company(self.company).qbo_state == 'proxy')

    @patch(request_client)
    def test_export_customer_invoice(self, *args):
        self.map_all_accounts()

        map_product = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '1'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '2'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        map_product.with_context(**self._ctx).create_instance_in_odoo()
        map_customer.with_context(**self._ctx).create_instance_in_odoo()

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': map_customer.partner_id.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 10.0,
                'quantity': 1,
                'product_id': map_product.product_id.id,
            })],
        })

        # Confirm invoice
        invoice.action_post()
        # Map-invoice before export
        qbo_invoice_ids = invoice.qbo_invoice_ids.filtered(
            lambda r: r.qbo_lib_type == INVOICE
        )
        self.assertFalse(qbo_invoice_ids)
        self.assertTrue(invoice.with_company(self.company).qbo_state == 'todo')

        with self.patcher(INVOICE):
            invoice.with_context(**self._ctx).export_invoice_to_qbo()

        # Map-invoice after export
        qbo_invoice_ids = invoice.qbo_invoice_ids.filtered(
            lambda r: r.qbo_lib_type == INVOICE
        )
        self.assertTrue(len(qbo_invoice_ids) == 1)
        self.assertEqual(invoice.with_company(self.company).qbo_state, 'proxy')
        self.assertEqual(invoice.with_company(self.company).qbo_transaction_info, '')

    @patch(request_client)
    def test_constraints_export_customer_invoice(self, *args):
        customer = self.env['res.partner'].create({
            'name': 'Test Invoice Customer',
        })
        product = self.env['product.product'].create({
            'name': 'Test Invoice Product',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
        })
        self.assertTrue(invoice.with_company(self.company).qbo_state == 'todo')

        # 2.
        try:
            invoice.with_context(**self._ctx).export_invoice_to_qbo()
        except ValidationError as ex:
            self.assertIn('You need to assign partner', ex.args[0])

        # 3.
        invoice.write({
            'partner_id': customer.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 10.0,
                'quantity': 1,
                'product_id': product.id,
            })],
        })

        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.assertTrue(map_customer)
        map_customer.write({'partner_id': customer.id})

        map_product = self.env['qbo.map.product'].search([
            ('qbo_lib_type', '=', PRODUCT),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.assertTrue(map_product)
        map_product.write({'product_id': product.id})

        # 4.
        try:
            invoice.with_context(**self._ctx).export_invoice_to_qbo()
        except ValidationError as ex:
            self.assertIn('Confirm invoice', ex.args[0])

        invoice.action_post()

        # 5.
        with self.patcher(INVOICE):
            invoice.with_context(**self._ctx).export_invoice_to_qbo()
        self.assertTrue(invoice.with_company(self.company).qbo_state == 'proxy')

        # Map-invoice after export
        qbo_invoice_ids = invoice.qbo_invoice_ids.filtered(
            lambda r: r.qbo_lib_type == INVOICE
        )
        self.assertTrue(len(qbo_invoice_ids) == 1)
        self.assertEqual(invoice.with_company(self.company).qbo_state, 'proxy')
        self.assertEqual(invoice.with_company(self.company).qbo_transaction_info, '')

    @patch(request_client)
    def test_export_vendor_bill(self, *args):
        self.map_all_accounts()

        map_product = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '67'),
            ('company_id', '=', self.company.id),
        ])
        map_vendor = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '31'),
            ('qbo_lib_type', '=', VENDOR),
            ('company_id', '=', self.company.id),
        ])

        map_product.with_context(**self._ctx).create_instance_in_odoo()
        map_vendor.with_context(**self._ctx).create_instance_in_odoo()

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': date.today(),
            'partner_id': map_vendor.partner_id.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.expenses_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 10.0,
                'quantity': 1,
                'product_id': map_product.product_id.id,
            })],
        })

        # Confirm invoice
        bill.action_post()
        # Map-invoice before export
        qbo_invoice_ids = bill.qbo_invoice_ids.filtered(
            lambda r: r.qbo_lib_type == BILL
        )
        self.assertFalse(qbo_invoice_ids)
        self.assertTrue(bill.with_company(self.company).qbo_state == 'todo')

        with self.patcher(BILL):
            bill.with_context(**self._ctx).export_invoice_to_qbo()

        # Map-invoice after export
        qbo_invoice_ids = bill.qbo_invoice_ids.filtered(
            lambda r: r.qbo_lib_type == BILL
        )
        self.assertTrue(len(qbo_invoice_ids) == 1)
        self.assertEqual(bill.with_company(self.company).qbo_state, 'proxy')
        self.assertEqual(bill.with_company(self.company).qbo_transaction_info, '')

    @patch(request_client)
    def test_constraints_export_vendor_bill(self, *args):
        vendor = self.env['res.partner'].create({
            'name': 'Test Bill Vendor',
        })
        product = self.env['product.product'].create({
            'name': 'Test Bill Product',
        })
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': date.today(),
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.expenses_journal').id,
        })
        self.assertTrue(bill.with_company(self.company).qbo_state == 'todo')

        # 2.
        try:
            bill.with_context(**self._ctx).export_invoice_to_qbo()
        except ValidationError as ex:
            self.assertIn('You need to assign partner', ex.args[0])

        # 3.
        map_vendor = self.env['qbo.map.partner'].search([
            ('qbo_lib_type', '=', VENDOR),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.assertTrue(map_vendor)
        map_vendor.write({'partner_id': vendor.id})

        bill.write({'partner_id': vendor.id})

        # 4.
        try:
            bill.with_context(**self._ctx).export_invoice_to_qbo()
        except ValidationError as ex:
            self.assertIn('You need add products', ex.args[0])

        # 5.
        map_product = self.env['qbo.map.product'].search([
            ('qbo_lib_type', '=', PRODUCT),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.assertTrue(map_product)
        map_product.write({'product_id': product.id})

        bill.write({
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 10.0,
                'quantity': 1,
                'product_id': product.id,
            })],
        })

        # 6.
        try:
            bill.with_context(**self._ctx).export_invoice_to_qbo()
        except ValidationError as ex:
            self.assertIn('Confirm invoice', ex.args[0])

        bill.action_post()

        # 7.
        try:
            bill.with_context(**self._ctx).export_invoice_to_qbo()
        except ValidationError as ex:
            self.assertIn('Accounts Payable', ex.args[0])

        self.map_account_payable()

        # 8.
        with self.patcher(BILL):
            bill.with_context(**self._ctx).export_invoice_to_qbo()

        # Map-invoice after export
        qbo_invoice_ids = bill.qbo_invoice_ids.filtered(
            lambda r: r.qbo_lib_type == BILL
        )
        self.assertTrue(len(qbo_invoice_ids) == 1)
        self.assertEqual(bill.with_company(self.company).qbo_state, 'proxy')
        self.assertEqual(bill.with_company(self.company).qbo_transaction_info, '')

    def test_invoice_collect_qbo_export_dict(self):
        self.map_all_accounts()
        customer = self.env['res.partner'].create({
            'name': 'Test Invoice Customer',
        })
        product = self.env['product.product'].create({
            'name': 'Test Invoice Product',
        })

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': customer.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 10.0,
                'quantity': 1,
                'product_id': product.id,
            })],
        })

        invoice.action_post()

        export_dict, allowed_ids = invoice._collect_qbo_export_dict(self.company)

        self.assertEqual(export_dict['product.product'][PRODUCT].pop(), product)
        self.assertEqual(export_dict['res.partner'][CUSTOMER].pop(), customer)
        self.assertEqual(export_dict['account.move'][INVOICE].pop(), invoice)
        self.assertIn(invoice.id, allowed_ids)

    def test_invoice_collect_qbo_export_dict_mapped(self):
        self.map_all_accounts()

        map_product = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '2'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '1'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        map_product.with_context(**self._ctx).create_instance_in_odoo()
        map_customer.with_context(**self._ctx).create_instance_in_odoo()

        product = map_product.product_id
        customer = map_customer.partner_id

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': customer.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 10.0,
                'quantity': 1,
                'product_id': product.id,
            })],
        })

        invoice.action_post()

        export_dict, allowed_ids = invoice._collect_qbo_export_dict(self.company)

        self.assertFalse(export_dict['product.product'][PRODUCT])
        self.assertFalse(export_dict['res.partner'][CUSTOMER])
        self.assertEqual(export_dict['account.move'][INVOICE].pop(), invoice)
        self.assertIn(invoice.id, allowed_ids)

    @patch(request_client)
    def test_pay_customer_invoice(self, *args):
        # 1.
        self.map_all_accounts()

        map_product = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '1'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '2'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        map_product.with_context(**self._ctx).create_instance_in_odoo()
        map_customer.with_context(**self._ctx).create_instance_in_odoo()

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': map_customer.partner_id.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 1000.0,
                'quantity': 1,
                'product_id': map_product.product_id.id,
            })],
        })

        invoice.action_post()

        with self.patcher(INVOICE):
            invoice.with_context(**self._ctx).export_invoice_to_qbo()

        map_invoice = invoice.qbo_invoice_ids
        self.assertTrue(len(map_invoice) == 1)

        # 2. Make a partially payment amount by cash ('1')
        self.patcher.make_intuit_payment(map_invoice.qbo_id, 'Invoice', 900.0, '1')

        payments = self.env['qbo.map.payment'].search([
            ('txn_id', '=', map_invoice.id),
            ('company_id', '=', self.company.id),
        ])
        self.assertFalse(payments)

        self.company.write({'qbo_payment_sync_out': True})

        with self.patcher(PAYMENT):
            ctx = {'not_register_payment': True}
            self.env['qbo.map.payment'].with_context(**ctx)\
                .get_intuit_payments('payment', self.company)

        pay = self.env['qbo.map.payment'].search([
            ('txn_id', '=', map_invoice.id),
            ('company_id', '=', self.company.id),
        ])
        self.assertTrue(len(pay) == 1)
        self.assertEqual(pay.pay_method, '1')
        self.assertEqual(pay.payment_id.id, False)
        self.assertEqual(pay.txn_type, 'invoice')
        self.assertEqual(pay.currency_ref, 'USD')
        self.assertEqual(pay.txn_amount, '900.0')
        self.assertEqual(pay.invoice_id, invoice)
        self.assertEqual(pay.txn_date, datetime.today().strftime('%Y-%m-%d'))

        # 3. Register payment
        with self.patcher(INVOICE):
            # 3.1
            try:
                pay.register_payment()
            except ValidationError as ex:
                self.assertIn('It is not possible to register payment in Odoo', ex.args[0])

            # 3.2
            self.map_default_payment()
            pay.register_payment()

        self.assertIsNotNone(pay.payment_id)
        self.assertEqual(
            invoice.with_company(self.company).qbo_transaction_info, False
        )
        self.assertEqual(int(invoice.amount_residual), 100)

    @patch(request_client)
    def test_pay_creditnote(self, *args):
        # 1.
        self.map_all_accounts()

        map_product = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '1'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '2'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        map_product.with_context(**self._ctx).create_instance_in_odoo()
        map_customer.with_context(**self._ctx).create_instance_in_odoo()

        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': map_customer.partner_id.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 1000.0,
                'quantity': 1,
                'product_id': map_product.product_id.id,
            })],
        })

        credit_note.action_post()

        with self.patcher(CREDIT_NOTE):
            credit_note.with_context(**self._ctx).export_invoice_to_qbo()

        map_credit_note = credit_note.qbo_invoice_ids
        self.assertTrue(len(map_credit_note) == 1)

        # 2. Make a full payment amount without method
        self.patcher.make_intuit_payment(map_credit_note.qbo_id, 'CreditMemo', 1000.0, '')

        payments = self.env['qbo.map.payment'].search([
            ('txn_id', '=', map_credit_note.id),
            ('company_id', '=', self.company.id),
        ])
        self.assertFalse(payments)

        self.company.write({'qbo_payment_sync_out': True})

        with self.patcher(PAYMENT):
            ctx = {'not_register_payment': True}
            self.env['qbo.map.payment'].with_context(**ctx)\
                .get_intuit_payments('payment', self.company)

        pay = self.env['qbo.map.payment'].search([
            ('txn_id', '=', map_credit_note.id),
            ('company_id', '=', self.company.id),
        ])
        self.assertTrue(len(pay) == 1)
        self.assertEqual(pay.pay_method, False)
        self.assertEqual(pay.payment_id.id, False)
        self.assertEqual(pay.txn_type, 'creditmemo')
        self.assertEqual(pay.currency_ref, 'USD')
        self.assertEqual(pay.txn_amount, '1000.0')
        self.assertEqual(pay.invoice_id, credit_note)
        self.assertEqual(pay.txn_date, datetime.today().strftime('%Y-%m-%d'))

        # 3. Register payment
        with self.patcher(CREDIT_NOTE):
            # 3.1
            try:
                pay.register_payment()
            except ValidationError as ex:
                self.assertIn('It is not possible to register payment in Odoo', ex.args[0])

            # 3.2
            self.map_default_payment()
            pay.register_payment()

        self.assertIsNotNone(pay.payment_id)
        self.assertEqual(
            credit_note.with_company(self.company).qbo_transaction_info, False
        )
        self.assertEqual(int(credit_note.amount_residual), 0)
        self.assertTrue(credit_note.payment_state == 'paid')

    @patch(request_client)
    def test_pay_customer_invoice_in_odoo(self, *args):
        self.map_all_accounts()
        self.map_default_payment()

        map_product = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '1'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '2'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        map_product.with_context(**self._ctx).create_instance_in_odoo()
        map_customer.with_context(**self._ctx)._create_odoo_instance()

        # A.
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': map_customer.partner_id.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 1000.0,
                'quantity': 1,
                'product_id': map_product.product_id.id,
            })],
        })

        invoice.action_post()

        with self.patcher(INVOICE):
            invoice.with_context(**self._ctx).export_invoice_to_qbo()

        map_invoice = invoice.qbo_invoice_ids
        self.assertTrue(len(map_invoice) == 1)

        ctx = {
            'active_model': 'account.move',
            'active_ids': invoice.ids,
        }
        ac_pay_reg1 = self.env['account.payment.register'].with_context(**ctx).create({
            'amount': 400.0,
            'journal_id': self.env.ref('quickbooks_sync_online.bank_journal').id,
            'partner_type': 'customer',
            'payment_date': date.today(),
            'payment_method_line_id':
                self.env.ref('quickbooks_sync_online.line_check_in').id,
            'currency_id': invoice.currency_id.id,
            'payment_type': 'inbound',
        })
        payment_1 = ac_pay_reg1._create_payments()

        ac_pay_reg2 = self.env['account.payment.register'].with_context(**ctx).create({
            'amount': invoice.amount_total - 400.0,
            'journal_id': self.env.ref('quickbooks_sync_online.bank_journal').id,
            'partner_type': 'customer',
            'payment_date': date.today(),
            'payment_method_line_id':
                self.env.ref('quickbooks_sync_online.line_check_in').id,
            'currency_id': invoice.currency_id.id,
            'payment_type': 'inbound',
        })
        payment_2 = ac_pay_reg2._create_payments()

        # B.
        invoice_no_export = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': map_customer.partner_id.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 1000.0,
                'quantity': 1,
                'product_id': map_product.product_id.id,
            })],
        })
        invoice_no_export.action_post()

        ctx['active_ids'] = invoice_no_export.id
        ac_pay_reg3 = self.env['account.payment.register'].with_context(**ctx).create({
            'amount': 400.0,
            'journal_id': self.env.ref('quickbooks_sync_online.bank_journal').id,
            'partner_type': 'customer',
            'payment_date': date.today(),
            'payment_method_line_id':
                self.env.ref('quickbooks_sync_online.line_check_in').id,
            'currency_id': invoice.currency_id.id,
            'payment_type': 'inbound',
        })
        payment_3 = ac_pay_reg3._create_payments()

        payments = payment_1 + payment_2 + payment_3
        company_payments = self.company._search_to_qbo_payments()

        for pay in payments:
            self.assertIn(pay.id, company_payments.ids)

        self.assertTrue(len(payment_1.qbo_payment_ids) == 0)
        self.assertTrue(len(payment_2.qbo_payment_ids) == 0)
        self.assertTrue(len(payment_3.qbo_payment_ids) == 0)

        # Map `payment.joutnal_id` to any `qbo.map.payment.method` before export.
        map_pay_met = self.env['qbo.map.payment.method'].search([
            ('company_id', '=', self.company.id),
        ], limit=1)
        journal = payments.mapped('journal_id')
        self.assertTrue(len(journal) == 1)
        map_pay_met.journal_id = journal.id

        export_dict, allowed_ids = payments._collect_qbo_export_dict(
            ['payment'], self.company
        )

        self.assertFalse(export_dict['product.product'][PRODUCT])
        self.assertFalse(export_dict['res.partner'][CUSTOMER])
        self.assertIn(invoice_no_export, export_dict['account.move'][INVOICE])
        self.assertTrue(len(export_dict['account.move'][INVOICE]) == 1)

        for pay in payments:
            self.assertIn(pay, export_dict['account.payment'][PAYMENT])
            self.assertIn(pay.id, allowed_ids)

        # C.
        with self.patcher(INVOICE):
            invoice_no_export.with_context(**self._ctx).export_invoice_to_qbo()

        map_invoice_no_export = invoice_no_export.qbo_invoice_ids
        self.assertTrue(len(map_invoice_no_export) == 1)

        with self.patcher(PAYMENT):
            payments.with_context(**self._ctx).export_payment_to_qbo()

        self.assertTrue(len(payment_1.qbo_payment_ids) == 1)
        self.assertEqual(payment_1.with_company(self.company).qbo_state, 'proxy')

        self.assertTrue(len(payment_2.qbo_payment_ids) == 1)
        self.assertEqual(payment_2.with_company(self.company).qbo_state, 'proxy')

        self.assertEqual(map_invoice.payment_state, 'paid')
        self.assertTrue(len(map_invoice.payment_ids) == 2)

    @patch(request_client)
    def test_pay_customer_credit_in_odoo(self, *args):
        self.map_all_accounts()
        self.map_default_payment()

        map_product = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '1'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '2'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        map_product.with_context(**self._ctx).create_instance_in_odoo()
        map_customer.with_context(**self._ctx)._create_odoo_instance()

        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': map_customer.partner_id.id,
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'price_unit': 1000.0,
                'quantity': 1,
                'product_id': map_product.product_id.id,
            })],
        })
        credit_note.action_post()

        with self.patcher(CREDIT_NOTE):
            credit_note.with_context(**self._ctx).export_invoice_to_qbo()

        map_credit_note = credit_note.qbo_invoice_ids
        self.assertTrue(len(map_credit_note) == 1)

        ctx = {
            'active_model': 'account.move',
            'active_ids': credit_note.ids,
        }
        ac_pay_reg1 = self.env['account.payment.register'].with_context(**ctx).create({
            'amount': 400.0,
            'journal_id': self.env.ref('quickbooks_sync_online.bank_journal').id,
            'partner_type': 'customer',
            'payment_date': date.today(),
            'payment_method_line_id':
                self.env.ref('quickbooks_sync_online.line_check_in').id,
            'currency_id': credit_note.currency_id.id,
            'payment_type': 'inbound',
        })
        payment_1 = ac_pay_reg1._create_payments()

        ac_pay_reg2 = self.env['account.payment.register'].with_context(**ctx).create({
            'amount': credit_note.amount_total - 400.0,
            'journal_id': self.env.ref('quickbooks_sync_online.bank_journal').id,
            'partner_type': 'customer',
            'payment_date': date.today(),
            'payment_method_line_id':
                self.env.ref('quickbooks_sync_online.line_check_in').id,
            'currency_id': credit_note.currency_id.id,
            'payment_type': 'inbound',
        })
        payment_2 = ac_pay_reg2._create_payments()

        payments = payment_1 + payment_2
        company_payment_ids = self.company._search_to_qbo_payments()

        self.assertTrue(bool(payments))
        self.assertFalse(bool(company_payment_ids))

        # Due to filtering any refunds - make next code inactive: TODO

        # for pay in payments:
        #     self.assertIn(pay.id, company_payment_ids.ids)

        # self.assertTrue(len(payment_1.qbo_payment_ids) == 0)
        # self.assertTrue(len(payment_2.qbo_payment_ids) == 0)

        # export_dict, allowed_ids = payments._collect_qbo_export_dict(
        #     payments.map_types, self.company
        # )

        # self.assertFalse(export_dict['product.product'][PRODUCT])
        # self.assertFalse(export_dict['res.partner'][CUSTOMER])
        # self.assertFalse(export_dict['account.move'][INVOICE])

        # for pay in payments:
        #     self.assertIn(pay, export_dict['account.payment'][PAYMENT])
        #     self.assertIn(pay.id, allowed_ids)

        # # C.
        # with self.patcher(PAYMENT):
        #     payments.with_context(**self._ctx).export_payment_to_qbo()

        # self.assertTrue(len(payment_1.qbo_payment_ids) == 1)
        # self.assertEqual(payment_1.with_company(self.company).qbo_state, 'proxy')

        # self.assertTrue(len(payment_2.qbo_payment_ids) == 1)
        # self.assertEqual(payment_2.with_company(self.company).qbo_state, 'proxy')

        # self.assertEqual(map_credit_note.payment_state, 'paid')
        # self.assertTrue(len(map_credit_note.payment_ids) == 2)

    @patch(request_client)
    def test_requires_update_partner_to_qbo(self, *args):
        # A. Create and export new partner
        ctx = {
            'qbo_partner_type': VENDOR,
            'skip_qbo_partner_wizard': True,
        }
        ctx.update(self._ctx)

        country_id = self.env.ref('base.us', False) and self.env.ref('base.us').id
        state_id = self.env.ref('base.state_us_1', False) and self.env.ref('base.state_us_1').id

        parent_partner = self.env['res.partner'].create({
            'name': 'John Wayne Vendor Parent',
        })
        partner = self.env['res.partner'].create({
            'name': 'John Wayne Vendor',
            'parent_id': parent_partner.id,
            'email': 'mail@mail.info',
            'phone': '8029-555555',
            'mobile': '8029-777777',
            'country_id': country_id,
            'city': 'Minsk',
            'state_id': state_id,
            'street': 'Lenina',
            'street2': 'Stalina',
            'zip': '666',
        })

        self.assertFalse(partner.qbo_update_required)
        partner.write({'name': 'John Wayne Vendor-2'})
        self.assertFalse(partner.qbo_update_required)

        # Perform export
        with self.patcher(VENDOR):
            partner.with_context(**ctx).export_partner_to_qbo()

        # Map-partner exist
        map_partner = partner.qbo_partner_ids.filtered(
            lambda r: r.company_id == self.company
        )
        self.assertTrue(len(map_partner) == 1)
        self.assertTrue(map_partner.qbo_lib_type == VENDOR)
        self.assertTrue(partner.with_company(self.company).qbo_state == 'proxy')

        # B. Change 'track-fields' in partner after export

        self.assertFalse(partner.qbo_update_required)
        partner.with_context(no_check_intuit_update=True).write({
            'name': 'John Wayne Vendor-3',
        })
        self.assertFalse(partner.qbo_update_required)

        # 1. name
        self.assertFalse(partner.qbo_update_required)
        partner.write({'name': 'John Wayne Vendor-4'})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 2. parent_id
        self.assertFalse(partner.qbo_update_required)
        partner.write({'parent_id': False})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 3. phone
        self.assertFalse(partner.qbo_update_required)
        partner.write({'phone': '8044-555555'})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 4. mobile
        self.assertFalse(partner.qbo_update_required)
        partner.write({'mobile': '8044-777777'})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 5. state_id
        self.assertFalse(partner.qbo_update_required)
        partner.write({'state_id': False})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 6. country_id
        self.assertFalse(partner.qbo_update_required)
        partner.write({'country_id': False})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 7. city
        self.assertFalse(partner.qbo_update_required)
        partner.write({'city': 'Kiev'})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 8. street
        self.assertFalse(partner.qbo_update_required)
        partner.write({'street': 'Peremen'})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 9. street2
        self.assertFalse(partner.qbo_update_required)
        partner.write({'street2': 'Pr. Peremen'})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 10. zip
        self.assertFalse(partner.qbo_update_required)
        partner.write({'zip': '999'})
        self.assertTrue(partner.qbo_update_required)
        partner.write({'qbo_update_required': False})

        # 11. email
        self.assertFalse(partner.qbo_update_required)
        partner.write({'email': 'mail@mail.com'})
        self.assertTrue(partner.qbo_update_required)

        records_to_update = self.company._search_to_qbo_update('res.partner')
        self.assertIn(partner.id, records_to_update.ids)

        # Perform update
        with self.patcher(VENDOR):
            partner.with_context(**self._ctx)._update_records_to_qbo(self.company)

        self.assertFalse(partner.qbo_update_required)

        # 11. change non-track field --> website
        partner.write({'website': 'https://tut.by'})
        self.assertFalse(partner.qbo_update_required)

        records_to_update = self.company._search_to_qbo_update('res.partner')
        self.assertNotIn(partner.id, records_to_update.ids)

    @patch(request_client)
    def test_get_taxes_from_qbo_taxable_customer(self, *args):
        self.map_all_accounts()
        tax = self.create_tax()
        MAP_PARTNER = self.env['qbo.map.partner']

        def _refresh_qbo_mapping_body(*args, **kw):
            return MAP_PARTNER, 0

        # Patch '_refresh_qbo_mapping_body()' method for 'qbo.map.partner'
        self.patch(type(MAP_PARTNER), '_refresh_qbo_mapping_body', _refresh_qbo_mapping_body)

        map_product_1 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '4'),
            ('company_id', '=', self.company.id),
        ])
        map_product_2 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '1'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '3'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        product_1 = map_product_1.with_context(**self._ctx)._create_odoo_instance()
        product_2 = map_product_2.with_context(**self._ctx)._create_odoo_instance()
        customer = map_customer.with_context(**self._ctx)._create_odoo_instance()

        product_1.write({
            'taxes_id': [(6, 0, tax.ids)],
        })

        sale_order = self.env['sale.order'].create({
            'partner_id': customer.id,
            'company_id': self.company.id,
            'order_line': [
                (0, 0, {
                    'name': map_product_1.qbo_name,
                    'product_id': product_1.id,
                    'product_uom_qty': 2,
                    'product_uom': self.env.ref('uom.product_uom_unit').id,
                    'price_unit': 42,
                }),
                (0, 0, {
                    'name': map_product_2.qbo_name,
                    'product_id': product_2.id,
                    'product_uom_qty': 1,
                    'product_uom': self.env.ref('uom.product_uom_unit').id,
                    'price_unit': 58,
                }),
            ],
        })

        taxes_before = self.env['account.tax'].search([
            ('company_id', '=', self.company.id)
        ])
        self.assertTrue(len(taxes_before) == 1)

        with self.patcher(SALE_ORDER):
            sale_order.with_context(**self._ctx)._get_qbo_taxes_from_salereceipt()

        taxes_after = self.env['account.tax'].search([
            ('company_id', '=', self.company.id)
        ])
        self.assertTrue(len(taxes_after) == 5)

        self.assertEqual(sale_order.with_company(self.company).qbo_state, 'proxy')
        self.assertEqual(sale_order.with_company(self.company).qbo_transaction_info, '')

        salereceipt = sale_order._get_map_instance_or_raise(SALE_ORDER, self.company.id)

        self.assertTrue(str(salereceipt.total_tax), '7.77')
        self.assertTrue(len(salereceipt.qbo_tax_ids) == 4)

        line_1 = sale_order.order_line.filtered(lambda r: r.product_id == product_1)
        line_2 = sale_order.order_line.filtered(lambda r: r.product_id == product_2)
        self.assertEqual(
            sorted(line_1.tax_id.ids),
            sorted(salereceipt.qbo_tax_ids.mapped('tax_id.id')),
        )
        self.assertEqual(
            sorted(line_2.tax_id.ids),
            [],  # Because of TaxCodeRef --> NON in received json
        )
        self.assertAlmostEqual(sale_order.amount_total, 149.77, 2)

    @patch(request_client)
    def test_get_taxes_from_qbo_non_taxable_customer(self, *args):
        self.map_all_accounts()
        tax = self.create_tax()
        MAP_PARTNER = self.env['qbo.map.partner']

        def _refresh_qbo_mapping_body(*args, **kw):
            return MAP_PARTNER, 0

        # Patch '_refresh_qbo_mapping_body()' method for 'qbo.map.partner'
        self.patch(type(MAP_PARTNER), '_refresh_qbo_mapping_body', _refresh_qbo_mapping_body)

        map_product_1 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '4'),
            ('company_id', '=', self.company.id),
        ])
        map_product_2 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '1'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = self.env['qbo.map.partner'].search([
            ('qbo_id', '=', '4'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        product_1 = map_product_1.with_context(**self._ctx)._create_odoo_instance()
        product_2 = map_product_2.with_context(**self._ctx)._create_odoo_instance()
        customer = map_customer.with_context(**self._ctx)._create_odoo_instance()

        sale_order = self.env['sale.order'].create({
            'partner_id': customer.id,
            'company_id': self.company.id,
            'order_line': [
                (0, 0, {
                    'name': map_product_1.qbo_name,
                    'product_id': product_1.id,
                    'product_uom_qty': 2,
                    'product_uom': self.env.ref('uom.product_uom_unit').id,
                    'price_unit': 42,
                    'tax_id': [(6, 0, tax.ids)],
                }),
                (0, 0, {
                    'name': map_product_2.qbo_name,
                    'product_id': product_2.id,
                    'product_uom_qty': 1,
                    'product_uom': self.env.ref('uom.product_uom_unit').id,
                    'price_unit': 58,
                    'tax_id': False,
                }),
            ],
        })

        taxes_before = self.env['account.tax'].search([
            ('company_id', '=', self.company.id)
        ])
        self.assertTrue(len(taxes_before) == 1)

        with self.patcher(SALE_ORDER):
            sale_order.with_context(**self._ctx)._get_qbo_taxes_from_salereceipt()

        taxes_after = self.env['account.tax'].search([
            ('company_id', '=', self.company.id)
        ])
        self.assertTrue(len(taxes_after) == 1)

        self.assertEqual(sale_order.with_company(self.company).qbo_state, 'proxy')
        self.assertEqual(
            sale_order.with_company(self.company).qbo_transaction_info,
            'Customer %s is tax exempt.' % customer.name,
        )

        with self.assertRaises(ValidationError):
            sale_order._get_map_instance_or_raise(SALE_ORDER, self.company.id)

        line_1 = sale_order.order_line.filtered(lambda r: r.product_id == product_1)
        line_2 = sale_order.order_line.filtered(lambda r: r.product_id == product_2)

        self.assertFalse(bool(line_1.tax_id))
        self.assertFalse(bool(line_2.tax_id))

        self.assertEqual(str(sale_order.amount_total), '142.0')

    @patch(request_client)
    def test_constraints_get_taxes_from_qbo(self, *args):
        self.map_all_accounts()
        tax = self.create_tax()
        MAP_PARTNER = self.env['qbo.map.partner']

        def _refresh_qbo_mapping_body(*args, **kw):
            return MAP_PARTNER, 0

        # Patch '_refresh_qbo_mapping_body()' method for 'qbo.map.partner'
        self.patch(type(MAP_PARTNER), '_refresh_qbo_mapping_body', _refresh_qbo_mapping_body)

        map_product = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '4'),
            ('company_id', '=', self.company.id),
        ])
        map_customer = MAP_PARTNER.search([
            ('qbo_id', '=', '3'),
            ('qbo_lib_type', '=', CUSTOMER),
            ('company_id', '=', self.company.id),
        ])

        product = map_product.with_context(**self._ctx)._create_odoo_instance()
        customer = map_customer.with_context(**self._ctx)._create_odoo_instance()

        # 1. SaleOrder not in 'draft' state
        sale_order_1 = self.env['sale.order'].create({
            'partner_id': customer.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'name': map_product.qbo_name,
                'product_id': product.id,
                'product_uom_qty': 1,
                'product_uom': self.env.ref('uom.product_uom_unit').id,
                'price_unit': 50,
                'tax_id': [(6, 0, tax.ids)],
            })],
        })
        sale_order_1.action_confirm()

        with self.assertRaises(UserError):
            sale_order_1.with_context(**self._ctx).get_qbo_taxes_from_salereceipt()

        # 2. No products
        map_customer.write({'partner_id': customer.id})
        map_product.write({'product_id': product.id})
        sale_order_4 = self.env['sale.order'].create({
            'partner_id': customer.id,
            'company_id': self.company.id,
        })

        with self.assertRaises(UserError):
            sale_order_4.with_context(**self._ctx).get_qbo_taxes_from_salereceipt()

        # 3. Happy-path case
        sale_order_5 = self.env['sale.order'].create({
            'partner_id': customer.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'name': map_product.qbo_name,
                'product_id': product.id,
                'product_uom_qty': 1,
                'product_uom': self.env.ref('uom.product_uom_unit').id,
                'price_unit': 50,
                'tax_id': [(6, 0, tax.ids)],
            })],
        })

        sale_order_5._check_requirements(self.company)
        with self.patcher(SALE_ORDER):
            sale_order_5.with_context(**self._ctx)._get_qbo_taxes_from_salereceipt()

        self.assertEqual(sale_order_5.with_company(self.company).qbo_state, 'proxy')
        self.assertEqual(sale_order_5.with_company(self.company).qbo_transaction_info, '')

    def test_get_products_to_qbo_export_method(self):
        partner = self.env['res.partner'].create({
            'name': 'Test Invoice Partner',
        })
        product1 = self.env['product.product'].create({
            'name': 'Test Invoice Product1',
        })
        product2 = self.env['product.product'].create({
            'name': 'Test Invoice Product2',
        })
        product3 = self.env['product.product'].create({
            'name': 'Test Invoice Product3',
        })
        product4 = self.env['product.product'].create({
            'name': 'Test Invoice Product4',
        })
        invoice1 = self.env['account.move'].create({
            'partner_id': partner.id,
            'move_type': 'out_invoice',
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Test line',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': product1.id,
                }),
            ],
        })
        invoice2 = self.env['account.move'].create({
            'partner_id': partner.id,
            'move_type': 'out_invoice',
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Test line',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': product2.id,
                }),
            ],
        })

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': date.today(),
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.expenses_journal').id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Test line1',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': product3.id,
                }),
                (0, 0, {
                    'name': 'Test line2',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': product4.id,
                }),
            ],
        })

        all_invoices = invoice1 + invoice2 + bill

        # 1.
        self.company.write({
            'qbo_sync_product': True,
            'qbo_sync_product_category': False,
        })

        products = all_invoices._get_products_to_qbo_export(self.company)

        self.assertIn(product1.id, products.ids)
        self.assertIn(product2.id, products.ids)
        self.assertIn(product3.id, products.ids)
        self.assertIn(product4.id, products.ids)

        # 2.
        self.company.write({
            'qbo_sync_product': False,
            'qbo_sync_product_category': False,
        })

        products = all_invoices._get_products_to_qbo_export(self.company)

        self.assertNotIn(product1.id, products.ids)
        self.assertNotIn(product2.id, products.ids)
        self.assertIn(product3.id, products.ids)
        self.assertIn(product4.id, products.ids)

        # 3.
        products = (invoice1 + invoice2)._get_products_to_qbo_export(self.company)

        self.assertFalse(bool(products))
        self.assertEqual(products._name, 'product.product')

        # 4.
        products = bill._get_products_to_qbo_export(self.company)

        self.assertIn(product3.id, products.ids)
        self.assertIn(product4.id, products.ids)

        # 5.
        products = (invoice1 + invoice2)._get_products_to_qbo_export(self.company)

        self.assertFalse(bool(products))
        self.assertEqual(products._name, 'product.product')

        # 6.
        self.company.write({
            'qbo_sync_product': False,
            'qbo_sync_product_category': True,
        })

        products = all_invoices._get_products_to_qbo_export(self.company)

        self.assertEqual(products._name, 'product.category')
        self.assertEqual(products, all_invoices.mapped('invoice_line_ids.product_id.categ_id'))

    def test_create_qbo_invoice_line_method(self):
        partner = self.env['res.partner'].create({
            'name': 'Test Invoice Partner',
        })
        consum_127 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '127'),
            ('company_id', '=', self.company.id),
        ])
        consum_127._create_odoo_instance()
        product = consum_127.product_id

        consum_137 = self.env['qbo.map.product'].search([
            ('qbo_id', '=', '137'),
            ('company_id', '=', self.company.id),
        ])
        consum_137.write({
            'category_id': product.categ_id.id,
        })

        invoice = self.env['account.move'].create({
            'partner_id': partner.id,
            'move_type': 'out_invoice',
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Test line1',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': product.id,
                }),
                (0, 0, {
                    'name': 'Test line2',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': False,
                    'account_id': self.env.ref('quickbooks_sync_online.a_sale').id
                }),
            ],
        })
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': date.today(),
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.expenses_journal').id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Test line1',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': product.id,
                }),
                (0, 0, {
                    'name': 'Test line2',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': False,
                    'account_id': self.env.ref('quickbooks_sync_online.o_expense').id
                }),
            ],
        })

        inv_property = invoice._prepare_qbo_kwargs()
        inv_line1 = invoice.invoice_line_ids.filtered(lambda r: r.name == 'Test line1')
        inv_line2 = invoice.invoice_line_ids.filtered(lambda r: r.name == 'Test line2')

        bill_property = bill._prepare_qbo_kwargs()
        bill_line1 = bill.invoice_line_ids.filtered(lambda r: r.name == 'Test line1')
        bill_line2 = bill.invoice_line_ids.filtered(lambda r: r.name == 'Test line2')

        # 1.
        self.company.write({
            'qbo_sync_product': True,
            'qbo_sync_product_category': False,
        })
        exp_inv_line1 = inv_line1._create_qbo_invoice_line(inv_property)
        exp_inv_line2 = inv_line2._create_qbo_invoice_line(inv_property)

        self.assertEqual(
            exp_inv_line1[inv_property.get('taxcode_line_detail')]['ItemRef']['value'],
            consum_127.qbo_id,
        )
        self.assertEqual(
            exp_inv_line2[inv_property.get('taxcode_line_detail')].get('ItemRef', '100500'),
            '100500',
        )

        exp_bill_line1 = bill_line1._create_qbo_invoice_line(bill_property)
        exp_bill_line2 = bill_line2._create_qbo_invoice_line(bill_property)

        self.assertEqual(
            exp_bill_line1[bill_property.get('taxcode_line_detail')]['ItemRef']['value'],
            consum_127.qbo_id,
        )
        self.assertEqual(
            exp_bill_line2[bill_property.get('taxcode_line_detail')].get('ItemRef', 'NONE'),
            'NONE',
        )

        # 2.
        self.company.write({
            'qbo_sync_product': True,
            'qbo_sync_product_category': True,
        })
        exp_inv_line1 = inv_line1._create_qbo_invoice_line(inv_property)
        exp_inv_line2 = inv_line2._create_qbo_invoice_line(inv_property)

        self.assertEqual(
            exp_inv_line1[inv_property.get('taxcode_line_detail')]['ItemRef']['value'],
            consum_137.qbo_id,
        )
        self.assertEqual(
            exp_inv_line2[inv_property.get('taxcode_line_detail')].get('ItemRef', 'NONE'),
            'NONE',
        )

        exp_bill_line1 = bill_line1._create_qbo_invoice_line(bill_property)
        exp_bill_line2 = bill_line2._create_qbo_invoice_line(bill_property)

        self.assertEqual(
            exp_bill_line1[bill_property.get('taxcode_line_detail')]['ItemRef']['value'],
            consum_137.qbo_id,
        )
        self.assertEqual(
            exp_bill_line2[bill_property.get('taxcode_line_detail')].get('ItemRef', 'NONE'),
            'NONE',
        )

        # 3.
        self.company.write({
            'qbo_sync_product': False,
            'qbo_sync_product_category': False,
        })
        exp_inv_line1 = inv_line1._create_qbo_invoice_line(inv_property)
        exp_inv_line2 = inv_line2._create_qbo_invoice_line(inv_property)

        self.assertEqual(
            exp_inv_line1[inv_property.get('taxcode_line_detail')].get('ItemRef', 'NONE'),
            'NONE',
        )
        self.assertEqual(
            exp_inv_line2[inv_property.get('taxcode_line_detail')].get('ItemRef', 'NONE'),
            'NONE',
        )

        exp_bill_line1 = bill_line1._create_qbo_invoice_line(bill_property)
        exp_bill_line2 = bill_line2._create_qbo_invoice_line(bill_property)

        self.assertEqual(
            exp_bill_line1[bill_property.get('taxcode_line_detail')]['ItemRef']['value'],
            consum_127.qbo_id,
        )
        self.assertEqual(
            exp_bill_line2[bill_property.get('taxcode_line_detail')].get('ItemRef', 'NONE'),
            'NONE',
        )

    def test_get_tax_from_invoice_line(self):
        self.map_all_accounts()
        tax = self.create_tax()

        partner = self.env['res.partner'].create({
            'name': 'Test Invoice Partner',
        })
        product1 = self.env['product.product'].create({
            'name': 'Test Invoice Product1',
            'taxes_id': [(6, 0, tax.ids)],
        })
        product2 = self.env['product.product'].create({
            'name': 'Test Invoice Product2',
            'taxes_id': [(6, 0, tax.ids)],
        })
        product3 = self.env['product.product'].create({
            'name': 'Test Invoice Product3',
            'taxes_id': False,
        })
        product4 = self.env['product.product'].create({
            'name': 'Test Invoice Product4',
            'taxes_id': False,
        })
        invoice = self.env['account.move'].create({
            'partner_id': partner.id,
            'move_type': 'out_invoice',
            'invoice_user_id': self.user.id,
            'company_id': self.company.id,
            'journal_id': self.env.ref('quickbooks_sync_online.sales_journal').id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Test line 1',
                    'price_unit': 10.0,
                    'quantity': 1,
                    'product_id': product1.id,
                    'tax_ids': [(6, 0, tax.ids)],
                }),
                (0, 0, {
                    'name': 'Test line 2',
                    'price_unit': 11.0,
                    'quantity': 1,
                    'product_id': product2.id,
                    'tax_ids': False,
                }),
                (0, 0, {
                    'name': 'Test line 3',
                    'price_unit': 12.0,
                    'quantity': 1,
                    'product_id': product3.id,
                    'tax_ids': False,
                }),
                (0, 0, {
                    'name': 'Test line 4',
                    'price_unit': 12.0,
                    'quantity': 1,
                    'product_id': product4.id,
                    'tax_ids': [(6, 0, tax.ids)],
                }),
            ],
        })

        line1, line2, line3, line4 = invoice.invoice_line_ids
        inv_property = invoice._prepare_qbo_kwargs()
        taxcode_line_detail = inv_property.get('taxcode_line_detail')

        # 1. Line tax + product tax
        self.assertEqual(line1.name, 'Test line 1')
        export_line1 = line1._create_qbo_invoice_line(inv_property)
        value = export_line1[taxcode_line_detail]['TaxCodeRef']['value']
        self.assertEqual(value, TAXABLE)

        # 2. Not line tax + product tax
        self.assertEqual(line2.name, 'Test line 2')
        export_line2 = line2._create_qbo_invoice_line(inv_property)
        value = export_line2[taxcode_line_detail]['TaxCodeRef']['value']
        self.assertEqual(value, TAXABLE)

        # 3. Not line tax + not product tax
        self.assertEqual(line3.name, 'Test line 3')
        export_line3 = line3._create_qbo_invoice_line(inv_property)
        value = export_line3[taxcode_line_detail]['TaxCodeRef']['value']
        self.assertEqual(value, NON_TAXABLE)

        # 4. Line tax + not product tax
        self.assertEqual(line4.name, 'Test line 4')
        export_line4 = line4._create_qbo_invoice_line(inv_property)
        value = export_line4[taxcode_line_detail]['TaxCodeRef']['value']
        self.assertEqual(value, TAXABLE)
