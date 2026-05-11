from odoo.fields import Command

from .common import TestRevenueRecognitionCommon


class TestMultiInvoice(TestRevenueRecognitionCommon):
    """FR9.2 / FR9.3 — recognition correctly spans multiple invoices for one SO line."""

    def test_recognition_allocates_across_multiple_invoices(self):
        # Place an SO for 10 units; invoice 6 first, then the remaining 4 in a second invoice.
        so = self._create_so(self.product_storable, quantity=10, price=100.0)
        so.action_confirm()

        # First partial invoice for 6 units.
        so.order_line.qty_to_invoice = 6
        invoice_1 = so._create_invoices()
        invoice_1.action_post()

        # Second invoice for the remaining 4 units.
        invoice_2 = so._create_invoices()
        invoice_2.action_post()

        # Sanity: both invoice lines redirected to deferral.
        for inv in (invoice_1, invoice_2):
            line = inv.invoice_line_ids.filtered(lambda l: l.product_id == self.product_storable)
            self.assertEqual(line.account_id, self.deferral_account)

        # Deliver everything.
        picking = so.picking_ids[0]
        self._validate_picking(picking)

        rec_lines = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
        ])
        # Allocations across two invoice lines.
        self.assertEqual(len(rec_lines), 2)
        total = sum(rec_lines.mapped("amount_company_currency"))
        self.assertAlmostEqual(total, 1000.0, places=2)
        # First (older) invoice consumed first (FIFO).
        oldest = rec_lines.sorted("recognition_date")[0]
        self.assertEqual(oldest.invoice_line_id.move_id, invoice_1)
