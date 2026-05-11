from odoo.fields import Command

from .common import TestRevenueRecognitionCommon


class TestInvoiceRouting(TestRevenueRecognitionCommon):
    """FR1, FR2, FR9.9 — invoice account redirection at posting time."""

    def test_storable_product_routes_to_deferral(self):
        """On-delivery storable: invoice line account_id = deferral account."""
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        invoice = self._confirm_and_invoice(so)
        product_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        self.assertEqual(len(product_line), 1)
        self.assertEqual(product_line.account_id, self.deferral_account)
        self.assertEqual(product_line.x_target_revenue_account_id, self.income_account)

    def test_invoice_credits_deferral_not_sales(self):
        """Invoice posting credits the deferral account, not the sales account."""
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        invoice = self._confirm_and_invoice(so)
        deferral_lines = invoice.line_ids.filtered(
            lambda l: l.account_id == self.deferral_account
        )
        income_lines = invoice.line_ids.filtered(
            lambda l: l.account_id == self.income_account
        )
        self.assertEqual(sum(deferral_lines.mapped("credit")), 1000.0)
        self.assertFalse(income_lines)

    def test_fallback_chain_resolves_via_category(self):
        """Category override wins over company default."""
        # Different category-level account.
        other_account = self.env["account.account"].create({
            "name": "Other Unearned",
            "code": self._next_account_code("211"),
            "account_type": "liability_current",
            "company_ids": [Command.link(self.company.id)],
        })
        self.test_category.x_unearned_revenue_account_id = other_account
        so = self._create_so(self.product_storable, quantity=1, price=50.0)
        invoice = self._confirm_and_invoice(so)
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        self.assertEqual(line.account_id, other_account)

    def test_fallback_chain_resolves_via_company_default(self):
        """Company default is used when category override is empty."""
        self.test_category.x_unearned_revenue_account_id = False
        so = self._create_so(self.product_storable, quantity=1, price=50.0)
        invoice = self._confirm_and_invoice(so)
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        self.assertEqual(line.account_id, self.deferral_account)

    def test_no_redirect_when_no_deferral_account_resolves(self):
        """If neither category nor company-default exists, fall back to standard income."""
        self.test_category.x_unearned_revenue_account_id = False
        self.company.x_default_unearned_revenue_account_id = False
        # Also clear Enterprise field if present.
        if hasattr(self.company, "deferred_revenue_account_id"):
            self.company.deferred_revenue_account_id = False
        so = self._create_so(self.product_storable, quantity=1, price=50.0)
        invoice = self._confirm_and_invoice(so)
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        self.assertEqual(line.account_id, self.income_account)
        self.assertEqual(line.x_target_revenue_account_id, self.income_account)

    def test_manual_invoice_uses_standard_income(self):
        """Manual invoice (no SO) is not redirected even for on-delivery products."""
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.test_partner.id,
            "invoice_line_ids": [Command.create({
                "product_id": self.product_storable.id,
                "quantity": 5,
                "price_unit": 100.0,
                "tax_ids": [Command.clear()],
            })],
        })
        invoice.action_post()
        product_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        # No SO link => no redirect => account is the standard income account.
        self.assertFalse(product_line.sale_line_ids)
        self.assertEqual(product_line.account_id, self.income_account)
