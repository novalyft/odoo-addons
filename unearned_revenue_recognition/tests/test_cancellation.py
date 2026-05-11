from .common import TestRevenueRecognitionCommon


class TestCancellation(TestRevenueRecognitionCommon):
    """Test 6 — invoice draft / cancel reverses the recognition entry.

    Note: Odoo 19 disallows cancelling a stock.picking once its moves are 'done'
    (stock.move._action_cancel raises). Because revenue recognition only fires
    AFTER the picking is fully done, the FR7 case of 'cancel a recognized
    picking' is physically unreachable in Odoo 19 — to undo a delivery, users
    must create a return, which is exercised by tests/test_returns.py.
    """

    def test_invoice_reset_reverses_recognition(self):
        """Resetting a posted invoice to draft must unwind the recognition."""
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        invoice = self._confirm_and_invoice(so)
        picking = so.picking_ids
        self._validate_picking(picking)

        rec_before = self.env["x.revenue.recognition.line"].search([
            ("invoice_line_id", "in", invoice.invoice_line_ids.ids),
            ("is_reversal", "=", False),
        ])
        self.assertTrue(rec_before)

        invoice.button_draft()
        reversal = self.env["x.revenue.recognition.line"].search([
            ("invoice_line_id", "in", invoice.invoice_line_ids.ids),
            ("is_reversal", "=", True),
        ])
        self.assertEqual(
            len(reversal),
            len(rec_before),
            "Each non-reversal recognition line must be mirrored by a reversal row.",
        )
        # Net sales credit on income account should be zero after reversal.
        sales_lines = self.env["account.move.line"].search([
            ("account_id", "=", self.income_account.id),
            ("parent_state", "=", "posted"),
        ])
        net = sum(sales_lines.mapped("credit")) - sum(sales_lines.mapped("debit"))
        self.assertAlmostEqual(net, 0.0, places=2)
