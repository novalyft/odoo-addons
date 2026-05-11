from odoo.exceptions import AccessError
from odoo.fields import Command

from .common import TestRevenueRecognitionCommon


class TestSecurity(TestRevenueRecognitionCommon):
    """Validates ACLs and the parallel mirrored record rule on x.revenue.recognition.line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesman_a = cls.env["res.users"].create({
            "name": "Salesman A",
            "login": "sm_a@test",
            "email": "sm_a@test",
            "group_ids": [Command.set([cls.env.ref("sales_team.group_sale_salesman").id])],
        })
        cls.salesman_b = cls.env["res.users"].create({
            "name": "Salesman B",
            "login": "sm_b@test",
            "email": "sm_b@test",
            "group_ids": [Command.set([cls.env.ref("sales_team.group_sale_salesman").id])],
        })
        cls.salesman_all = cls.env["res.users"].create({
            "name": "Salesman All",
            "login": "sm_all@test",
            "email": "sm_all@test",
            "group_ids": [Command.set([
                cls.env.ref("sales_team.group_sale_salesman_all_leads").id,
            ])],
        })

    def _make_so_owned_by(self, user):
        so = self.env["sale.order"].with_user(user).create({
            "partner_id": self.test_partner.id,
            "warehouse_id": self.warehouse.id,
            "user_id": user.id,
            "order_line": [Command.create({
                "product_id": self.product_storable.id,
                "product_uom_qty": 5,
                "price_unit": 100.0,
                "tax_ids": [Command.clear()],
                "salesman_id": user.id,
            })],
        })
        so.sudo().action_confirm()
        invoice = so.sudo()._create_invoices()
        invoice.action_post()
        picking = so.picking_ids
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.sudo().with_context(skip_backorder=True).button_validate()
        return so

    def test_own_documents_only_isolates_recognition_lines(self):
        so_a = self._make_so_owned_by(self.salesman_a)
        so_b = self._make_so_owned_by(self.salesman_b)

        # Salesman A should see only A's recognition lines, not B's.
        recognition_a = self.env["x.revenue.recognition.line"].with_user(
            self.salesman_a
        ).search([])
        self.assertTrue(all(r.sale_order_id == so_a for r in recognition_a))

        recognition_b = self.env["x.revenue.recognition.line"].with_user(
            self.salesman_b
        ).search([])
        self.assertTrue(all(r.sale_order_id == so_b for r in recognition_b))

    def test_see_all_sees_everything(self):
        self._make_so_owned_by(self.salesman_a)
        self._make_so_owned_by(self.salesman_b)
        all_user_records = self.env["x.revenue.recognition.line"].with_user(
            self.salesman_all
        ).search([])
        sale_orders = all_user_records.mapped("sale_order_id")
        self.assertGreaterEqual(len(sale_orders), 2)

    def test_salesman_cannot_unlink(self):
        so_a = self._make_so_owned_by(self.salesman_a)
        rec = self.env["x.revenue.recognition.line"].search([
            ("sale_order_id", "=", so_a.id),
        ])
        with self.assertRaises(AccessError):
            rec.with_user(self.salesman_a).unlink()
