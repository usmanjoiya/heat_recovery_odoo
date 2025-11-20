# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import fields, models, api, SUPERUSER_ID, _
from odoo.exceptions import ValidationError, UserError

from .utils import register_api_transaction, TAXABLE, NON_TAXABLE


_logger = logging.getLogger(__name__)

QBO_DIFF_TOTAL_WARNING = _(
    'Difference in total invoice amounts in Quickbooks and Odoo. You cannot apply received taxes '
    'because your administrator turned off products synchronisation in Quickbooks Settings.'
)
QBO_APPLY_TAXES_WARNING = _(
    'Difference in total invoice amounts in Quickbooks and Odoo. '
    'Invoice amount in Quickbooks is %s. Invoice amount in Odoo is %s. '
    'Usually that happens because of Quickbooks calculate taxes itself. '
    'Click "Apply QBO Taxes" button to synchronise taxes between Quickbooks and Odoo. '
    'Note that "Apply QBO Taxes" button is visible only in Draft status.'
)
TAX_INCLUDED = 'TaxInclusive'
TAX_EXCLUDED = 'TaxExcluded'


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def remove_move_reconcile(self):
        # ToDo: Synchronous work of confirmations and cancellations for payments in Odoo / Intuit.
        super(AccountMoveLine, self).remove_move_reconcile()

    def _create_qbo_invoice_line(self, inv_property):
        self.ensure_one()
        taxcode_value = str()
        company = self.move_id.company_id
        move_type = inv_property['map_type']
        customer_move_type = move_type in ('invoice', 'creditmemo')
        taxcode_line_detail = inv_property['taxcode_line_detail']

        if self.tax_ids:
            product_tax = self.tax_ids[:1]
        else:
            tax_field = 'taxes_id' if customer_move_type else 'supplier_taxes_id'
            product_tax = getattr(self.product_id, tax_field)[:1]

        if product_tax and product_tax.price_include:
            price_unit = self.price_subtotal / (self.quantity or 1)
        else:
            price_unit = self.price_unit * (1 - self.discount / 100)

        if company.intuit_is_us_company():
            taxcode_value = TAXABLE if product_tax else NON_TAXABLE
        elif product_tax:
            qbo_rel_tax = product_tax.get_qbo_related_tax(company.id)
            search_field = inv_property.get('taxcode_search_field')
            taxcode_value = qbo_rel_tax.get_qbo_related_taxcode(search_field, company.id).qbo_id

        export_line = {
            'Description': self.name,
            'Amount': self.price_subtotal,
            'DetailType': taxcode_line_detail,
            taxcode_line_detail: {
                'Qty': self.quantity,
                'UnitPrice': price_unit,
                'TaxCodeRef': {
                    'value': taxcode_value,
                },
            },
        }

        if not customer_move_type:
            customer = self.purchase_line_id.sale_line_id.order_id.partner_id
            if customer:
                customer = customer._ensure_qbo_currency(self.move_id)
                qbo_partner = customer._get_qbo_mapping('customer', company.id)

                export_line[taxcode_line_detail]['CustomerRef'] = {
                    'value': qbo_partner.qbo_id,
                }

        if not self.product_id:
            return export_line

        if not company.qbo_sync_product and customer_move_type:
            return export_line

        if company.qbo_sync_product_category:
            qbo_product = self.product_id.categ_id.qbo_product_categ_ids
        else:
            qbo_product = self.product_id.qbo_product_ids

        qbo_product = qbo_product.filtered(lambda r: r.company_id == company)

        export_line[taxcode_line_detail]['ItemRef'] = {
            'name': qbo_product.qbo_name,
            'value': qbo_product.qbo_id,
        }
        return export_line


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'qbo.transaction.mixin', 'job.transaction.mixin']

    _qbo_map = 'qbo.map.account.move'

    qbo_invoice_ids = fields.One2many(
        comodel_name=_qbo_map,
        inverse_name='invoice_id',
        string='QBO Account Move',
        readonly=True,
    )
    qbo_warning_txt = fields.Char(
        string='QBO Attention',
        compute='_compute_qbo_warning',
    )
    qbo_invoice_link = fields.Char(
        string='QBO Invoice Link',
        compute='_compute_qbo_invoice_link',
    )

    @api.depends('qbo_invoice_ids', 'state', 'qbo_state')
    def _compute_qbo_warning(self):
        move_types = ('out_invoice', 'out_refund')
        for rec in self:
            info = False

            if rec.move_type in move_types:
                inv_amt = rec.amount_residual
                map_amt = rec.qbo_invoice_ids[:1].total_amt

                if inv_amt and map_amt and (abs(inv_amt - map_amt) > 0.05):
                    if not self.company_id.qbo_sync_product:
                        info = QBO_DIFF_TOTAL_WARNING
                    else:
                        info = QBO_APPLY_TAXES_WARNING % (map_amt, inv_amt)

            rec.qbo_warning_txt = info

    @api.depends('qbo_invoice_ids', 'qbo_state')
    def _compute_qbo_invoice_link(self):
        for rec in self:
            rec.qbo_invoice_link = rec.qbo_invoice_ids[:1].invoice_link

    @api.model
    # @api.returns('self')
    def search_fetch(self, *args, **kw):
        if self.env.context.get('qbo_todo_list_action'):
            self = self.with_context(qbo_todo_list_action=False)
            ids = self.env.context.get('allowed_company_ids', [])

            records = self.browse()
            for company in self.env['res.company'].qbo_company_ids.filtered(lambda x: x.id in ids):
                records |= company._search_to_qbo_invoices()

            return records

        return super(AccountMove, self).search_fetch(*args, **kw)

    @property
    def map_type(self):
        invoice_type = self.move_type

        if invoice_type == 'out_invoice':
            return 'invoice'
        elif invoice_type == 'out_refund':
            return 'creditmemo'
        elif invoice_type == 'in_invoice':
            return 'bill'
        elif invoice_type == 'in_refund':
            return 'vendorcredit'

        raise ValidationError(_('Unsupported invoice type: %s.') % invoice_type)

    def export_invoice_to_qbo(self):
        """Export invoice to the Intuit company."""
        company = self.define_transaction_company()
        company._check_qbo_auth()
        move_types = company.get_qbo_invoice_allowed_types()

        invoices = self.filtered(
            lambda x: x.qbo_state != 'proxy'
            and (x.move_type in move_types)
            and (x.company_id == company)
        )

        if not invoices:
            _logger.info('There are no invoices for export.')
            return

        export_dict, __ = invoices.with_context(raise_exception=True)\
            ._collect_qbo_export_dict(company)

        return company._process_qbo_export_dict(export_dict)

    @register_api_transaction
    def _export_qbo_one(self, inv_property, company, check_external=False):
        self.ensure_one()

        self = self.with_context(qbo_check_external=check_external)

        qbo_lib_model = self._init_qbo_lib_class(inv_property.get('map_type'))
        self._set_qbo_values(qbo_lib_model, inv_property, company)

        result = self._perform_export_qbo_one(qbo_lib_model, company)
        self._mark_failed_jobs_as_cancel()

        return result

    def _export_qbo_batch(self, map_type, company, ctx_params):
        _logger.info('Export to QBO "%s". Create jobs.' % str(self))

        for rec in self.with_context(company_id=company.id):
            rec._write_info('pending', '', company.id)

            inv_property = rec._prepare_qbo_kwargs()
            job_kwargs = rec._get_transaction_job_kwargs(map_type)

            rec._mark_failed_jobs_as_cancel(identity_key=job_kwargs['identity_key'])

            rec.with_delay(**job_kwargs)._export_qbo_one(inv_property, company)

        return True

    def to_qbo_json(self):
        self.ensure_one()

        inv_property = self._prepare_qbo_kwargs()
        qbo_lib_model = self._init_qbo_lib_class(inv_property['map_type'])
        self._set_qbo_values(qbo_lib_model, inv_property, self.company_id)

        return self._display_qbo_json(
            f'DEBUG: {self.name} [{qbo_lib_model.qbo_object_name}]',
            qbo_lib_model.to_dict(),
        )

    def apply_qbo_taxes(self):
        self.ensure_one()
        company = self.company_id

        assert self.move_type in ('out_invoice', 'out_refund')

        company.ensure_qbo_us_company()
        company._check_qbo_tax_settings()

        if self.state != 'draft':
            raise UserError(_('The Invoice must be in the "Draft" state.'))

        return self._apply_taxes_from_intuit()

    def send_qbo_link(self):
        self.ensure_one()

        template = self.env.ref(
            'quickbooks_sync_online.email_template_qbo_invoice_link',
            raise_if_not_found=False,
        )

        if not (template and self.qbo_invoice_link):
            raise ValidationError(_(
                'There is no QuickBooks link in the current invoice. '
                'You should specify customer email address and send it to QuickBooks.'
            ))

        action = self.action_invoice_sent()

        action['context'].update({
            'default_is_print': False,
            'default_template_id': template.id
        })

        return action

    def _set_qbo_values(self, qbo_lib_model, inv_property, company, **kw):
        self.ensure_one()

        map_type = inv_property.get('map_type')
        partner_type = inv_property.get('partner_type')

        partner = self.partner_id._ensure_qbo_currency(self)
        qbo_partner = partner._get_qbo_mapping(partner_type, company.id)

        if company.intuit_is_us_company():
            tax_calculation = TAX_EXCLUDED
        else:
            tax_calculation = TAX_INCLUDED if company.qbo_invoice_tax_included else TAX_EXCLUDED

        qbo_lib_model.GlobalTaxCalculation = tax_calculation

        if self.ref:
            qbo_lib_model.PrivateNote = self.ref

        if map_type in ('invoice', 'creditmemo'):
            qbo_lib_model.CustomerRef = {
                'value': qbo_partner.qbo_id,
            }
            qbo_lib_model.DepartmentRef = {
                'value': self._get_qbo_department(),
            }
            if map_type == 'invoice':
                qbo_lib_model.BillEmail = {'Address': self.partner_id.email or ''}
                qbo_lib_model.AllowOnlineACHPayment = True
                qbo_lib_model.AllowOnlineCreditCardPayment = True

            if self.partner_shipping_id:
                qbo_lib_model.ShipAddr = self.partner_shipping_id._parse_qbo_address()

        elif map_type in ('bill', 'vendorcredit'):
            partner = self.partner_id.with_company(company)
            pay_account = partner.property_account_payable_id
            account_rel = pay_account.get_qbo_related_account(company.id)

            qbo_lib_model.VendorRef = {
                'value': qbo_partner.qbo_id,
            }
            qbo_lib_model.APAccountRef = {
                'name': account_rel.qbo_name,
                'value': account_rel.qbo_id,
            }

        qbo_lib_model.DocNumber = self.name
        qbo_lib_model.CurrencyRef = {
            'value': self.currency_id.name,
        }
        if self.invoice_date:
            qbo_lib_model.TxnDate = self.invoice_date.strftime('%Y-%m-%d')

        if self.invoice_date_due and not self.invoice_payment_term_id:
            if map_type in ('invoice', 'bill'):
                qbo_lib_model.DueDate = self.invoice_date_due.strftime('%Y-%m-%d')
        elif self.invoice_payment_term_id:
            if map_type in ('invoice', 'bill', 'creditmemo'):
                qbo_rel_term = self.invoice_payment_term_id.get_qbo_related_pay_term(company.id)
                qbo_lib_model.SalesTermRef = {'value': qbo_rel_term.qbo_id}

        lines = []
        for invoice_line in self.invoice_line_ids.filtered(lambda r: r.display_type == 'product'):
            export_line = invoice_line._create_qbo_invoice_line(inv_property)
            lines.append(export_line)

        qbo_lib_model.Line = lines

    def _get_condition_for_check_external(self, qbo_lib_model):
        return f"DocNumber = '{qbo_lib_model.DocNumber}'"

    def _update_one_odoo_to_qbo(self, *args, **kwargs):
        raise NotImplementedError()

    def _format_duplicate_name(self):
        return 'invoice', self.name, 'Invoices'

    def _prepare_qbo_kwargs(self):
        self.ensure_one()

        _values = tuple()
        _keys = ('map_type', 'partner_type', 'taxcode_search_field', 'taxcode_line_detail')

        if self.move_type in ('out_invoice', 'out_refund'):
            _values = (self.map_type, 'customer', 'sales_tax_rate_id', 'SalesItemLineDetail')
        elif self.move_type in ('in_invoice', 'in_refund'):
            _values = (self.map_type, 'vendor', 'purchase_tax_rate_id', 'ItemBasedExpenseLineDetail')

        return dict(zip(_keys, _values)) if _values else {}

    def _get_qbo_department(self):
        value = str()
        if not self.invoice_origin:
            return value

        warehouse = self.env['sale.order'].search([
            ('name', '=', self.invoice_origin),
            ('company_id', '=', self.company_id.id),
        ], limit=1).warehouse_id

        if not warehouse:
            return value

        department = warehouse._get_map_instance_or_raise(
            warehouse.map_type, self.company_id.id, raise_if_not_found=False,
        )
        return department.qbo_id or value

    def _check_requirements(self, company):
        self.ensure_one()

        if self.move_type in ('in_invoice', 'in_refund'):
            search_field = 'purchase_tax_rate_id'
            partner = self.partner_id.with_company(company)
            pay_account = partner.property_account_payable_id
            pay_account.get_qbo_related_account(company.id)
        else:
            search_field = 'sales_tax_rate_id'

        if self.invoice_payment_term_id:
            self.invoice_payment_term_id.get_qbo_related_pay_term(company.id)

        if company.intuit_is_us_company():
            return

        for tax in self.invoice_line_ids.mapped('tax_ids'):
            qbo_related_tax = tax.get_qbo_related_tax(company.id)
            related_taxcode = qbo_related_tax.get_qbo_related_taxcode(search_field, company.id)

            if not related_taxcode:
                raise ValidationError(_(
                    'Unable to export Invoice "%s". Cannot find related taxcode for tax '
                    '"%s". Import all existing taxcodes first please.'
                    % (self.display_name, qbo_related_tax.qbo_name)
                ))

    def _check_type(self, raise_exception=False):
        self.ensure_one()

        move_types = self.company_id.get_qbo_invoice_allowed_types()
        if self.move_type in move_types:
            return True

        info = _(
            '- Unable to export invoice "%s". Unsupported invoice type "%s".'
            % (self.display_name, self.move_type)
        )
        if raise_exception:
            raise ValidationError(info)

        self._write_info('rejected', info, self.company_id.id)

    def _check_currency(self, raise_exception=False):
        self.ensure_one()

        info = False
        company, currency_name = self.company_id, self.currency_id.name

        if not company.external_currency_belong_company(currency_name):
            qbo_company = company._fetch_qbo_company_info()

            if not qbo_company.multi_currency_enabled:
                info = _(
                    'Multi Currencies are not allowed in your Intuit company. '
                    'Change it in settings.\nAllowed cuurencie(s): %s, requested currency: %s.'
                    % (qbo_company.currency_codes_str(), currency_name)
                )
            elif not qbo_company.validate_foreign_currency(currency_name):
                info = _(
                    'Your Intuit company not support %s currency.\nAllowed currencies: %s.'
                    % (currency_name, qbo_company.currency_codes_str())
                )

        if not info:
            return True

        if raise_exception:
            raise ValidationError(info)

        self._write_info('rejected', info, company.id)
        return False

    def _check_partner(self, raise_exception=False):
        self.ensure_one()
        info = False
        if not self.partner_id:
            info = _(
                '- You need to assign partner to the invoice "%s".' % self.display_name
            )

        if not info:
            return True

        if raise_exception:
            raise ValidationError(info)

        self._write_info('rejected', info, self.company_id.id)
        return False

    def _check_products(self, raise_exception):
        self.ensure_one()
        info = None
        lines = self.invoice_line_ids.filtered(lambda r: r.display_type == 'product')

        if self.move_type in ('out_invoice', 'out_refund'):
            if not all(x.active for x in lines.mapped('product_id')):
                inactive_products = lines.mapped('product_id').filtered(lambda x: not x.active)
                info = _(
                    'Some of the products are archived. Please make them active: %s'
                    % ', '.join(inactive_products.mapped(lambda x: f'{x.display_name} ({x.id})'))
                )
        else:
            if not lines:
                info = _(
                    'You need add products to the invoice "%s".' % self.display_name
                )
            elif lines.filtered(lambda r: not r.product_id):
                info = _(
                    'Invoice line without a product not allowed for Vendors: "%s".'
                    % self.display_name
                )

        if not info:
            return True

        if raise_exception:
            raise ValidationError(info)

        self._write_info('rejected', info, self.company_id.id)

    def _check_state(self, raise_exception):
        self.ensure_one()

        if self.state == 'posted':
            return True
        info = _(
            'Confirm invoice "%s" before export please.' % self.display_name
        )
        if raise_exception:
            raise ValidationError(info)

        self._write_info('rejected', info, self.company_id.id)

    def _return_property(self, raise_exception):
        self.ensure_one()

        if not self._check_type(raise_exception):
            return False

        inv_property = self._prepare_qbo_kwargs()

        if not self._check_currency(raise_exception):
            return False

        if not self._check_partner(raise_exception):
            return False

        if not self._check_products(raise_exception):
            return False

        if not self._check_state(raise_exception):
            return False

        return inv_property

    def _get_products_to_qbo_export(self, company):
        vendor_invoice_ids = self.filtered(lambda r: r.move_type in ('in_invoice', 'in_refund'))

        if company.qbo_sync_product_category:
            products = self.mapped('invoice_line_ids.product_id.categ_id')
        elif company.qbo_sync_product or vendor_invoice_ids:
            if not company.qbo_sync_product:
                products = vendor_invoice_ids.mapped('invoice_line_ids.product_id')
            else:
                products = self.mapped('invoice_line_ids.product_id')
        else:
            products = self.env['product.product']

        return products

    def _collect_qbo_export_dict(self, company):
        _logger.info('Collect invoices export dict "%s".' % self.ids)
        allowed_ids = []
        raise_exception = self.env.context.get('raise_exception')
        ctx = {'raise_exception': raise_exception}

        products = self._get_products_to_qbo_export(company)
        export_dict, allowed_product_ids = products.with_context(**ctx)\
            ._collect_qbo_export_dict(products.map_types, company)

        for invoice in self:
            error_list = []

            inv_property = invoice._return_property(raise_exception)
            if not inv_property:
                continue

            move_type = inv_property.get('map_type')
            customer_move_type = move_type in ('invoice', 'creditmemo')

            # Check products
            invoice_products = invoice._get_products_to_qbo_export(company)
            alias = invoice_products._name.split('.')[-1]
            for product in invoice_products:
                if product.id not in allowed_product_ids:
                    error_list.append(
                        _('- The %s "%s" needs fixing.' % (alias, product.display_name))
                    )

            # Check partner
            partner = invoice.partner_id
            partner_type = inv_property.get('partner_type')

            partner = partner._ensure_qbo_currency(invoice)
            partner_types_to_export, error_message = partner.with_context(**ctx)\
                ._validate_qbo_type_export(partner_type, company)

            for map_type in partner_types_to_export:
                export_dict['res.partner'][map_type].append(partner)

            if error_message:
                error_list.append(
                    _('- The partner "%s" needs fixing:\n\t- %s' % (partner.name, error_message))
                )

            # Check partner: check source customer for vendor bill/refund
            if not customer_move_type:
                add_partners = invoice.invoice_line_ids\
                    .mapped('purchase_line_id.sale_line_id.order_id.partner_id')
                for add_partner in add_partners:
                    add_partner = add_partner._ensure_qbo_currency(invoice)
                    add_partner_types, add_error_message = add_partner.with_context(**ctx)\
                        ._validate_qbo_type_export('customer', company)

                    if add_partner_types:
                        export_dict['res.partner']['customer'].append(add_partner)

                    if add_error_message:
                        error_list.append(_(
                            '- The partner "%s" needs fixing:\n\t- %s'
                            % (add_partner.name, add_error_message)
                        ))

            # Check invoice
            invoice_types_to_export, invoice_error_message = invoice.with_context(**ctx)\
                ._validate_qbo_type_export(move_type, company)

            if invoice_error_message:
                error_list.append(
                    _('- The invoice itself needs fixing:\n\t- %s' % invoice_error_message)
                )

            if error_list:
                info = '\n\n'.join(error_list)
                invoice._write_info('rejected', info, company.id)
                continue

            # If there is no any error add this one to the export dict
            for map_type in invoice_types_to_export:
                export_dict['account.move'][map_type].append(invoice)

            allowed_ids.append(invoice.id)

        return export_dict, allowed_ids

    def _apply_taxes_from_intuit(self):
        mapping = self.qbo_invoice_ids[:1]
        mapping._recompute_map_lines()

        for tax in mapping.qbo_tax_ids.filtered(lambda r: not r.tax_id):
            tax.with_user(SUPERUSER_ID).try_to_map(summary=False)

        array = zip(
            self.invoice_line_ids.filtered(lambda r: r.display_type == 'product'),
            mapping.invoice_map_line_ids,
        )

        vals_list = list()
        for invoice_line, map_line in array:
            taxes = [(6, 0, map_line.tax_map_ids.mapped('tax_id').ids)]
            vals_list.append(
                (1, invoice_line.id, {'tax_ids': taxes}),
            )
        res = self.write({
            'invoice_line_ids': vals_list,
        })
        return res
