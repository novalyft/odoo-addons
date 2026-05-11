from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # TYPE: addition
    x_amount_recognized = fields.Monetary(
        string="Recognized Revenue",
        compute="_compute_x_recognition_amounts",
        currency_field="currency_id",
    )
    x_amount_pending_recognition = fields.Monetary(
        string="Pending Recognition",
        compute="_compute_x_recognition_amounts",
        currency_field="currency_id",
    )
    x_recognition_status = fields.Selection(
        selection=[
            ("not_started", "Not Started"),
            ("partial", "Partial"),
            ("complete", "Complete"),
        ],
        string="Revenue Recognition Status",
        compute="_compute_x_recognition_amounts",
    )
    x_recognition_line_count = fields.Integer(
        compute="_compute_x_recognition_line_count",
    )

    def _compute_x_recognition_amounts(self):
        """Compute recognized vs. pending revenue per SO, in the SO's currency.

        - TYPE: addition
        Pending = sum of invoice-currency amounts on lines with on_delivery method
                  whose linked invoice lines are posted but not yet fully recognized.
        Recognized = sum of x.revenue.recognition.line.amount_invoice_currency on
                     non-reversal rows minus reversal rows for this SO.
        """
        Recognition = self.env["x.revenue.recognition.line"]
        for order in self:
            non_reversal = sum(
                Recognition.search([
                    ("sale_order_id", "=", order.id),
                    ("is_reversal", "=", False),
                ]).mapped("amount_invoice_currency")
            )
            reversal = sum(
                Recognition.search([
                    ("sale_order_id", "=", order.id),
                    ("is_reversal", "=", True),
                ]).mapped("amount_invoice_currency")
            )
            recognized = non_reversal - reversal

            # Pending = posted-invoice deferred amount across all lines on this SO
            # minus what is already recognized. We don't filter by
            # x_target_revenue_account_id here because credit-note lines created via
            # _reverse_moves before x_target had copy=True would silently drop out
            # of the math and leave the status stuck at 'partial'. sale_order_line.invoice_lines
            # is already M2M-restricted to lines that came from this SO line, so
            # tax/section/AR lines never appear here.
            invoiced_deferred = 0.0
            for line in order.order_line:
                if not line.product_id:
                    continue
                if line.product_id.product_tmpl_id._get_effective_revenue_method() != "on_delivery":
                    continue
                for inv_line in line.invoice_lines.filtered(
                    lambda l: l.parent_state == "posted"
                    and l.move_id.move_type in ("out_invoice", "out_refund")
                ):
                    sign = -1 if inv_line.move_id.move_type == "out_refund" else 1
                    invoiced_deferred += sign * abs(inv_line.amount_currency)

            pending = max(invoiced_deferred - recognized, 0.0)

            order.x_amount_recognized = recognized
            order.x_amount_pending_recognition = pending

            if recognized <= 0 and pending <= 0:
                order.x_recognition_status = "not_started"
            elif pending > 0.001:
                order.x_recognition_status = "partial" if recognized > 0 else "not_started"
            else:
                order.x_recognition_status = "complete" if recognized > 0 else "not_started"

    def _compute_x_recognition_line_count(self):
        Recognition = self.env["x.revenue.recognition.line"]
        for order in self:
            order.x_recognition_line_count = Recognition.search_count([
                ("sale_order_id", "=", order.id),
            ])

    def action_view_revenue_recognition_lines(self):
        """Smart button action: open recognition lines linked to this SO."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Revenue Recognition"),
            "res_model": "x.revenue.recognition.line",
            "view_mode": "list,form,pivot",
            "domain": [("sale_order_id", "=", self.id)],
        }
