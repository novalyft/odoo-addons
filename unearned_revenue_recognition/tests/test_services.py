from .common import TestRevenueRecognitionCommon


class TestServices(TestRevenueRecognitionCommon):
    """Test 8 / 8b / 8c — service-product handling under each recognition method."""

    def test_8_service_auto_uses_standard_income(self):
        """Test 8: 'auto' on a service => recognize on invoice; account_id = income."""
        so = self._create_so(self.product_service, quantity=2, price=100.0)
        invoice = self._confirm_and_invoice(so)
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_service
        )
        self.assertEqual(line.account_id, self.income_account)
        # No recognition record should exist (service auto = no deferral).
        rec = self.env["x.revenue.recognition.line"].search([
            ("invoice_line_id", "=", line.id),
        ])
        self.assertFalse(rec)

    def test_8b_storable_immediate_uses_standard_income(self):
        """Test 8b: storable forced to on_invoice => no deferral, no recognition entry."""
        so = self._create_so(self.product_storable_immediate, quantity=3, price=100.0)
        invoice = self._confirm_and_invoice(so)
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable_immediate
        )
        self.assertEqual(line.account_id, self.income_account)
        # Validate the delivery; no recognition should be created.
        picking = so.picking_ids
        self._validate_picking(picking)
        rec = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
        ])
        self.assertFalse(rec, "on_invoice products must not generate recognition.")

    def test_8c_service_forced_to_defer_no_auto_recognition(self):
        """Test 8c: service forced to on_delivery => account_id = deferral; chatter warning."""
        so = self._create_so(self.product_service_deferred, quantity=1, price=100.0)
        invoice = self._confirm_and_invoice(so)
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_service_deferred
        )
        self.assertEqual(line.account_id, self.deferral_account)
        # No picking exists for a service => no automatic recognition.
        self.assertFalse(so.picking_ids)
        # The invoice should have a chatter message warning the user.
        warnings = invoice.message_ids.filtered(
            lambda m: "service" in (m.body or "").lower()
            and "deferred revenue" in (m.body or "").lower()
        )
        self.assertTrue(
            warnings,
            "Service forced to defer must emit a chatter warning about manual recognition.",
        )
