from .common import TestRevenueRecognitionCommon


class TestRecognitionTrigger(TestRevenueRecognitionCommon):
    """Test 1 (full delivery) and Test 2 (partial / backorder)."""

    def test_full_delivery_recognition(self):
        """Test 1: a single full delivery posts a recognition entry for the whole amount."""
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        invoice = self._confirm_and_invoice(so)
        # Verify invoice routing.
        inv_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        self.assertEqual(inv_line.account_id, self.deferral_account)

        # Validate the outgoing picking with full qty.
        picking = so.picking_ids
        self._validate_picking(picking)

        rec_lines = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
        ])
        self.assertEqual(len(rec_lines), 1, "Exactly one recognition line per SO line.")
        self.assertEqual(rec_lines.quantity, 10.0)
        self.assertEqual(rec_lines.amount_company_currency, 1000.0)
        self.assertFalse(rec_lines.is_reversal)

        # Verify the recognition journal entry: debit deferral, credit sales.
        rec_move = rec_lines.account_move_id
        self.assertEqual(rec_move.state, "posted")
        debit = rec_move.line_ids.filtered(lambda l: l.account_id == self.deferral_account)
        credit = rec_move.line_ids.filtered(lambda l: l.account_id == self.income_account)
        self.assertEqual(sum(debit.mapped("debit")), 1000.0)
        self.assertEqual(sum(credit.mapped("credit")), 1000.0)

        # SO status badge.
        self.assertEqual(so.x_recognition_status, "complete")
        self.assertAlmostEqual(so.x_amount_recognized, 1000.0, places=2)
        self.assertAlmostEqual(so.x_amount_pending_recognition, 0.0, places=2)

    def test_partial_delivery_and_backorder(self):
        """Test 2: deliver 6 then 4 in a backorder; each picking recognizes its share."""
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        invoice = self._confirm_and_invoice(so)

        picking_1 = so.picking_ids
        self._validate_picking(picking_1, quantity=6)
        # Validating a partial qty creates a backorder.
        backorders = so.picking_ids - picking_1
        self.assertEqual(len(backorders), 1, "A backorder picking is created for the remainder.")

        rec_lines_1 = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking_1.id),
        ])
        self.assertEqual(len(rec_lines_1), 1)
        self.assertEqual(rec_lines_1.quantity, 6.0)
        self.assertEqual(rec_lines_1.amount_company_currency, 600.0)

        # Validate the backorder for the remaining 4 units.
        backorder = backorders[0]
        self._validate_picking(backorder, quantity=4)
        rec_lines_2 = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", backorder.id),
        ])
        self.assertEqual(len(rec_lines_2), 1)
        self.assertEqual(rec_lines_2.quantity, 4.0)
        self.assertEqual(rec_lines_2.amount_company_currency, 400.0)

        self.assertEqual(so.x_recognition_status, "complete")
