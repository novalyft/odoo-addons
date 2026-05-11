from .common import TestRevenueRecognitionCommon


class TestAuditTrail(TestRevenueRecognitionCommon):
    """Test 5 — idempotency: re-triggering recognition on the same picking is a no-op."""

    def test_idempotency_no_duplicate_entries(self):
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        self._confirm_and_invoice(so)
        picking = so.picking_ids
        self._validate_picking(picking)

        rec_before = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
        ])
        income_balance_before = sum(self.env["account.move.line"].search([
            ("account_id", "=", self.income_account.id),
            ("parent_state", "=", "posted"),
        ]).mapped("credit"))

        # Re-invoke recognition directly; nothing new should happen.
        picking._recognize_revenue()

        rec_after = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
        ])
        income_balance_after = sum(self.env["account.move.line"].search([
            ("account_id", "=", self.income_account.id),
            ("parent_state", "=", "posted"),
        ]).mapped("credit"))

        self.assertEqual(rec_before.ids, rec_after.ids)
        self.assertEqual(income_balance_before, income_balance_after)
