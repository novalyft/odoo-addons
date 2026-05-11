from .common import TestRevenueRecognitionCommon


class TestReturns(TestRevenueRecognitionCommon):
    """Test 3 — returned goods reverse the corresponding recognition."""

    def test_return_creates_reversal_entry(self):
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        self._confirm_and_invoice(so)
        picking = so.picking_ids
        self._validate_picking(picking)

        # Customer returns 3 units.
        return_picking = self._create_return(picking, quantity=3)

        reversal_lines = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", return_picking.id),
            ("is_reversal", "=", True),
        ])
        self.assertEqual(len(reversal_lines), 1, "One reversal line per returned SO line.")
        self.assertEqual(reversal_lines.quantity, 3.0)
        self.assertEqual(reversal_lines.amount_company_currency, 300.0)

        # The reversal journal entry: debit sales $300, credit deferral $300.
        reversal_move = reversal_lines.account_move_id
        self.assertEqual(reversal_move.state, "posted")
        debit_income = reversal_move.line_ids.filtered(
            lambda l: l.account_id == self.income_account
        )
        credit_deferral = reversal_move.line_ids.filtered(
            lambda l: l.account_id == self.deferral_account
        )
        self.assertEqual(sum(debit_income.mapped("debit")), 300.0)
        self.assertEqual(sum(credit_deferral.mapped("credit")), 300.0)
