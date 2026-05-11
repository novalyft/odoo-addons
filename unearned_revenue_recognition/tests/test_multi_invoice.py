from odoo.fields import Command

from .common import TestRevenueRecognitionCommon


class TestMultiInvoice(TestRevenueRecognitionCommon):
    """FR9.2 / FR9.3 — recognition correctly spans multiple invoices for one SO line.

    Scenario (matches FR9.3 - order qty increased after first invoice):
      1. SO for 6 units; confirm + invoice (invoice_1, 6 units to deferral).
      2. Increase SO line qty to 10.
      3. Invoice again (invoice_2, remaining 4 units to deferral).
      4. Deliver all 10 units; recognition splits across both invoice lines.
    """

    def test_recognition_allocates_across_multiple_invoices(self):
        so = self._create_so(self.product_storable, quantity=6, price=100.0)
        invoice_1 = self._confirm_and_invoice(so)
        # Sanity: first invoice line goes to deferral.
        inv_line_1 = invoice_1.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        self.assertEqual(inv_line_1.account_id, self.deferral_account)
        self.assertEqual(inv_line_1.quantity, 6)

        # Increase qty to 10 and re-invoice the additional 4 units.
        so.order_line.product_uom_qty = 10
        invoice_2 = so._create_invoices()
        invoice_2.action_post()
        inv_line_2 = invoice_2.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        self.assertEqual(inv_line_2.account_id, self.deferral_account)
        self.assertEqual(inv_line_2.quantity, 4)

        # Deliver everything.
        picking = so.picking_ids[0]
        self._validate_picking(picking)

        rec_lines = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
        ])
        # Allocations across both invoice lines.
        self.assertEqual(len(rec_lines), 2)
        total = sum(rec_lines.mapped("amount_company_currency"))
        self.assertAlmostEqual(total, 1000.0, places=2)

        # FIFO: the OLDER invoice line should have been fully consumed (6 units),
        # then the newer one (4 units).
        alloc_by_invoice = {
            rec.invoice_line_id.move_id.id: rec.quantity for rec in rec_lines
        }
        self.assertEqual(alloc_by_invoice.get(invoice_1.id), 6.0)
        self.assertEqual(alloc_by_invoice.get(invoice_2.id), 4.0)
