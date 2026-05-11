from odoo.fields import Command

from .common import TestRevenueRecognitionCommon


class TestTaxHandling(TestRevenueRecognitionCommon):
    """Test 9 — VAT recognition stays on invoice; recognition entry does not touch tax account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Dedicated tax-payable account so the tax line does NOT inherit the
        # product line's account (which would be the deferral account after our redirect).
        cls.tax_account = cls.env["account.account"].create({
            "name": "Test Tax Payable",
            "code": cls._next_account_code("251"),
            "account_type": "liability_current",
            "company_ids": [Command.link(cls.company.id)],
        })
        # 15% sales tax with an explicit account on its tax-repartition line.
        cls.tax_15 = cls.env["account.tax"].create({
            "name": "Test Sales Tax 15%",
            "amount": 15.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company.id,
            "invoice_repartition_line_ids": [
                Command.create({"document_type": "invoice", "repartition_type": "base"}),
                Command.create({"document_type": "invoice", "repartition_type": "tax", "account_id": cls.tax_account.id}),
            ],
            "refund_repartition_line_ids": [
                Command.create({"document_type": "refund", "repartition_type": "base"}),
                Command.create({"document_type": "refund", "repartition_type": "tax", "account_id": cls.tax_account.id}),
            ],
        })

    def test_invoice_taxes_separate_from_deferral(self):
        so = self._create_so(self.product_storable, quantity=10, price=100.0, taxes=self.tax_15)
        invoice = self._confirm_and_invoice(so)

        inv_product_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        # Net amount on the deferral account = 10 * 100 = 1000.
        self.assertEqual(inv_product_line.account_id, self.deferral_account)
        self.assertEqual(sum(inv_product_line.mapped("credit")), 1000.0)

        # Tax line lands on the tax account, NOT the deferral account.
        tax_lines = invoice.line_ids.filtered(
            lambda l: l.tax_line_id == self.tax_15
        )
        self.assertTrue(tax_lines, "A tax line must be generated.")
        self.assertNotEqual(tax_lines.account_id, self.deferral_account)
        self.assertAlmostEqual(sum(tax_lines.mapped("credit")), 150.0, places=2)

        # Deliver; recognition entry must NOT touch the tax account.
        picking = so.picking_ids
        self._validate_picking(picking)
        rec_lines = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
        ])
        rec_move = rec_lines.account_move_id
        tax_accounts_in_rec = rec_move.line_ids.filtered(
            lambda l: l.account_id == tax_lines.account_id
        )
        self.assertFalse(
            tax_accounts_in_rec,
            "Recognition entry must not touch the tax account.",
        )
        self.assertEqual(
            sum(rec_move.line_ids.filtered(lambda l: l.account_id == self.deferral_account).mapped("debit")),
            1000.0,
        )
        self.assertEqual(
            sum(rec_move.line_ids.filtered(lambda l: l.account_id == self.income_account).mapped("credit")),
            1000.0,
        )
