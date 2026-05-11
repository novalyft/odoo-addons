from odoo.fields import Command
from odoo.tests.common import tagged
from odoo.addons.sale_stock.tests.common import TestSaleStockCommon


@tagged("post_install", "-at_install", "unearned_revenue_recognition")
class TestRevenueRecognitionCommon(TestSaleStockCommon):
    """Base test fixture for the unearned_revenue_recognition module.

    Provides:
      - cls.deferral_account: a liability_current account configured as the deferral target.
      - cls.recognition_journal: a general-type journal for recognition entries.
      - cls.test_partner: a customer with the default receivable account.
      - cls.test_category: product.category with x_unearned_revenue_account_id set.
      - cls.product_storable / product_service / product_service_deferred /
        product_storable_immediate: products covering FR9.8 cases.

    All accounts are resolved via Odoo APIs (no hardcoded codes), so tests
    are portable across COA localizations.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.stock_location = cls.warehouse.lot_stock_id

        # Deferral account: clone the receivable account's chart slot but mark it as
        # liability_current. Using a fresh code reservation avoids clashes with COA seeds.
        cls.deferral_account = cls.env["account.account"].create({
            "name": "Test Unearned Revenue",
            "code": cls._next_account_code("210"),
            "account_type": "liability_current",
            "reconcile": True,
            "company_ids": [Command.link(cls.company.id)],
        })

        # Recognition journal: a general-type misc journal.
        cls.recognition_journal = cls.env["account.journal"].search([
            ("type", "=", "general"),
            ("company_id", "=", cls.company.id),
        ], limit=1)
        if not cls.recognition_journal:
            cls.recognition_journal = cls.env["account.journal"].create({
                "name": "Test Misc Journal",
                "code": "MISC",
                "type": "general",
                "company_id": cls.company.id,
            })

        cls.company.x_default_unearned_revenue_account_id = cls.deferral_account
        cls.company.x_recognition_journal_id = cls.recognition_journal

        # Reuse partner_a (configured with default receivable by AccountTestInvoicingCommon).
        cls.test_partner = cls.partner_a

        # Test category: deferral override at category level.
        cls.test_category = cls.env["product.category"].create({
            "name": "Test Storable Category",
            "x_unearned_revenue_account_id": cls.deferral_account.id,
        })

        # Resolve the standard income account through the same chain Odoo uses.
        cls.income_account = cls.company.income_account_id

        # Test products covering FR9.8 cases.
        cls.product_storable = cls.env["product.product"].create({
            "name": "ProductStorable",
            "type": "consu",
            "is_storable": True,
            "categ_id": cls.test_category.id,
            "list_price": 100.0,
            "standard_price": 60.0,
            "taxes_id": [Command.clear()],
            "x_revenue_recognition_method": "auto",
        })
        cls.product_service = cls.env["product.product"].create({
            "name": "ProductService",
            "type": "service",
            "categ_id": cls.test_category.id,
            "list_price": 100.0,
            "taxes_id": [Command.clear()],
            "x_revenue_recognition_method": "auto",
        })
        cls.product_service_deferred = cls.env["product.product"].create({
            "name": "ProductServiceDeferred",
            "type": "service",
            "categ_id": cls.test_category.id,
            "list_price": 100.0,
            "taxes_id": [Command.clear()],
            "x_revenue_recognition_method": "on_delivery",
        })
        cls.product_storable_immediate = cls.env["product.product"].create({
            "name": "ProductStorableImmediate",
            "type": "consu",
            "is_storable": True,
            "categ_id": cls.test_category.id,
            "list_price": 100.0,
            "standard_price": 60.0,
            "taxes_id": [Command.clear()],
            "x_revenue_recognition_method": "on_invoice",
        })

    @classmethod
    def _next_account_code(cls, prefix):
        """Return a code starting with `prefix` that does not yet exist for the company."""
        existing = set(cls.env["account.account"].search([
            ("code", "=like", f"{prefix}%"),
        ]).mapped("code"))
        for i in range(900, 1000):
            candidate = f"{prefix}{i}"
            if candidate not in existing:
                return candidate
        return f"{prefix}999"

    # ------------------------------------------------------------------
    # Helpers used across tests
    # ------------------------------------------------------------------
    def _create_so(self, product, quantity=10, price=100.0, partner=None, taxes=None):
        partner = partner or self.test_partner
        return self.env["sale.order"].create({
            "partner_id": partner.id,
            "warehouse_id": self.warehouse.id,
            "order_line": [Command.create({
                "product_id": product.id,
                "product_uom_qty": quantity,
                "price_unit": price,
                "tax_ids": [Command.set(taxes.ids)] if taxes else [Command.clear()],
            })],
        })

    def _confirm_and_invoice(self, so):
        so.action_confirm()
        invoice = so._create_invoices()
        invoice.action_post()
        return invoice

    def _validate_picking(self, picking, quantity=None):
        """Validate the picking, optionally adjusting quantity on the first move.

        Uses skip_backorder=True so partial-qty validations bypass the
        'Create Backorder?' confirmation wizard. Without it, button_validate
        returns the wizard action and _action_done never fires.
        """
        if quantity is not None:
            picking.move_ids[0].quantity = quantity
            picking.move_ids[0].picked = True
        else:
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
        return picking.with_context(skip_backorder=True).button_validate()

    def _create_return(self, picking, quantity):
        """Build a return picking for `picking` and validate it for `quantity`."""
        return_wizard = self.env["stock.return.picking"].with_context(
            active_id=picking.id, active_model="stock.picking"
        ).create({"picking_id": picking.id})
        return_wizard.product_return_moves.quantity = quantity
        action = return_wizard.action_create_returns()
        return_picking = self.env["stock.picking"].browse(action["res_id"])
        self._validate_picking(return_picking, quantity=quantity)
        return return_picking

    def _recognition_lines_for(self, **domain):
        """Helper: search x.revenue.recognition.line with extra domain filters."""
        return self.env["x.revenue.recognition.line"].search(
            [(k, "=", v) for k, v in domain.items()]
        )
