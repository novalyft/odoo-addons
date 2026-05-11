from odoo import fields, models


class RevenueRecognitionLine(models.Model):
    _name = "x.revenue.recognition.line"
    _description = "Revenue Recognition Audit Trail"
    _order = "recognition_date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name")

    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Stock Picking",
        required=True,
        ondelete="restrict",
        index=True,
    )
    move_id = fields.Many2one(
        comodel_name="stock.move",
        string="Stock Move",
        required=True,
        ondelete="restrict",
        index=True,
    )
    sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Sales Order Line",
        ondelete="restrict",
        index=True,
    )
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales Order",
        related="sale_line_id.order_id",
        store=True,
        index=True,
    )
    invoice_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Invoice Line",
        ondelete="restrict",
        index=True,
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        related="invoice_line_id.move_id",
        store=True,
        index=True,
    )
    account_move_id = fields.Many2one(
        comodel_name="account.move",
        string="Recognition Journal Entry",
        required=True,
        ondelete="restrict",
        index=True,
    )
    quantity = fields.Float(
        string="Recognized Quantity",
        required=True,
        digits="Product Unit",
    )
    amount_company_currency = fields.Monetary(
        string="Amount (Company Currency)",
        required=True,
        currency_field="company_currency_id",
    )
    amount_invoice_currency = fields.Monetary(
        string="Amount (Invoice Currency)",
        currency_field="invoice_currency_id",
    )
    recognition_date = fields.Date(
        string="Recognition Date",
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    is_reversal = fields.Boolean(
        string="Is Reversal",
        default=False,
        index=True,
        help="True when this row records a reversal of a prior recognition "
             "(triggered by a return picking, picking cancellation, or invoice cancellation).",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )
    invoice_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Invoice Currency",
    )

    _quantity_positive = models.Constraint(
        "CHECK (quantity > 0)",
        "Recognized quantity must be strictly positive.",
    )

    def _compute_display_name(self):
        for line in self:
            prefix = "Reversal" if line.is_reversal else "Recognition"
            line.display_name = f"{prefix} {line.picking_id.name or ''} - {line.quantity}"
