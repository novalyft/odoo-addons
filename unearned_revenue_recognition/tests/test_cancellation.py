from .common import TestRevenueRecognitionCommon


class TestCancellation(TestRevenueRecognitionCommon):
    """Test 6 — cancelling a picking after recognition reverses the journal entry."""

    def test_picking_cancellation_reverses_recognition(self):
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        self._confirm_and_invoice(so)
        picking = so.picking_ids
        self._validate_picking(picking)

        rec_lines = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
            ("is_reversal", "=", False),
        ])
        self.assertEqual(len(rec_lines), 1)
        orig_move = rec_lines.account_move_id

        # Cancel the picking.
        picking.action_cancel()

        reversal_lines = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
            ("is_reversal", "=", True),
        ])
        self.assertEqual(len(reversal_lines), 1)
        # The reversal must be a separate, posted account.move that reverses the original.
        self.assertNotEqual(reversal_lines.account_move_id, orig_move)
        self.assertEqual(reversal_lines.account_move_id.state, "posted")
        # Net P&L on Sales should now be zero.
        sales_lines = self.env["account.move.line"].search([
            ("account_id", "=", self.income_account.id),
            ("parent_state", "=", "posted"),
        ])
        net = sum(sales_lines.mapped("credit")) - sum(sales_lines.mapped("debit"))
        self.assertAlmostEqual(net, 0.0, places=2)

    def test_invoice_reset_reverses_recognition(self):
        """Resetting a posted invoice to draft also unwinds the recognition."""
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
        self.assertEqual(len(reversal), len(rec_before))
