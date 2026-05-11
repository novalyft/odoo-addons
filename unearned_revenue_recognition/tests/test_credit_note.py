from odoo.fields import Command

from .common import TestRevenueRecognitionCommon


class TestCreditNote(TestRevenueRecognitionCommon):
    """Test 4 — credit note for order reduction protects the Sales account.

    Customer reduces order from 10 to 8 units before delivery. Issuing a credit
    note for 2 units must debit the deferral account (not the Sales account),
    leaving Sales untouched. After delivering 8 units, Sales should end at $800.
    """

    def test_credit_note_debits_deferral_not_sales(self):
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        invoice = self._confirm_and_invoice(so)
        inv_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        self.assertEqual(inv_line.account_id, self.deferral_account)

        # Issue a credit note for 2 units (= $200).
        move_reversal = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({
            "reason": "Reduce qty by 2",
            "journal_id": invoice.journal_id.id,
        })
        action = move_reversal.refund_moves()
        credit_note = self.env["account.move"].browse(action["res_id"])
        # Adjust the credit note to 2 units.
        cn_line = credit_note.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        cn_line.quantity = 2
        credit_note.action_post()

        # The credit note line inherits the deferral account (FR6).
        self.assertEqual(cn_line.account_id, self.deferral_account)

        # Sales account untouched by the credit note.
        sales_lines_on_cn = credit_note.line_ids.filtered(
            lambda l: l.account_id == self.income_account
        )
        self.assertFalse(
            sales_lines_on_cn,
            "Credit note must not post to the sales/income account.",
        )

        # Deliver 8 units; Sales should ultimately stand at $800.
        picking = so.picking_ids
        self._validate_picking(picking, quantity=8)
        sales_lines = self.env["account.move.line"].search([
            ("account_id", "=", self.income_account.id),
            ("parent_state", "=", "posted"),
        ])
        self.assertEqual(sum(sales_lines.mapped("credit")), 800.0)
