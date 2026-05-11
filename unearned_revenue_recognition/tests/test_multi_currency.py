from odoo.fields import Command

from .common import TestRevenueRecognitionCommon


class TestMultiCurrency(TestRevenueRecognitionCommon):
    """Test 7 — recognition uses the invoice-date FX rate, not the delivery-date rate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.foreign_currency = cls.env.ref("base.EUR")
        # Make sure company is in USD-equivalent.
        if cls.company.currency_id == cls.foreign_currency:
            cls.foreign_currency = cls.env.ref("base.GBP")

        # Set rates at invoice date and (different) delivery date.
        cls.env["res.currency.rate"].search([
            ("currency_id", "=", cls.foreign_currency.id),
        ]).unlink()
        cls.env["res.currency.rate"].create([
            {
                "name": "2025-01-01",
                "rate": 1.0 / 1.10,
                "currency_id": cls.foreign_currency.id,
                "company_id": cls.company.id,
            },
            {
                "name": "2025-03-01",
                "rate": 1.0 / 1.15,
                "currency_id": cls.foreign_currency.id,
                "company_id": cls.company.id,
            },
        ])

    def test_recognition_uses_invoice_date_rate(self):
        # SO in EUR at $1.10 (invoice date).
        so = self.env["sale.order"].with_context(default_currency_id=self.foreign_currency.id).create({
            "partner_id": self.test_partner.id,
            "warehouse_id": self.warehouse.id,
            "currency_id": self.foreign_currency.id,
            "date_order": "2025-01-15",
            "pricelist_id": self.env["product.pricelist"].create({
                "name": "Test EUR Pricelist",
                "currency_id": self.foreign_currency.id,
            }).id,
            "order_line": [Command.create({
                "product_id": self.product_storable.id,
                "product_uom_qty": 10,
                "price_unit": 100.0,
                "tax_ids": [Command.clear()],
            })],
        })
        so.action_confirm()

        # Invoice on 2025-01-15 (rate 1.10).
        invoice = so._create_invoices()
        invoice.invoice_date = "2025-01-15"
        invoice.action_post()

        inv_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_storable
        )
        # invoice line balance is in company currency: 1000 EUR @ 1.10 -> 1100 USD.
        self.assertAlmostEqual(abs(inv_line.balance), 1100.0, places=0)

        # Deliver on 2025-03-01 where the rate is 1.15. Recognition must still
        # use the invoice's frozen balance (1100 USD), not the delivery-date rate.
        picking = so.picking_ids
        picking.date_done = "2025-03-01"
        self._validate_picking(picking)

        rec_lines = self.env["x.revenue.recognition.line"].search([
            ("picking_id", "=", picking.id),
        ])
        self.assertEqual(len(rec_lines), 1)
        self.assertAlmostEqual(
            rec_lines.amount_company_currency,
            1100.0,
            places=0,
            msg="Recognition must use the invoice-date rate (1.10), not delivery-date (1.15).",
        )
