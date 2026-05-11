import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    x_recognition_line_count = fields.Integer(
        compute="_compute_x_recognition_line_count",
    )

    def _compute_x_recognition_line_count(self):
        Recognition = self.env["x.revenue.recognition.line"]
        for move in self:
            move.x_recognition_line_count = Recognition.search_count([
                ("invoice_line_id", "in", move.invoice_line_ids.ids),
            ])

    def action_view_revenue_recognition_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Revenue Recognition"),
            "res_model": "x.revenue.recognition.line",
            "view_mode": "list,form,pivot",
            "domain": [("invoice_line_id", "in", self.invoice_line_ids.ids)],
        }

    # TYPE: behavioral_change
    def _post(self, soft=True):
        """Emit chatter warnings when posting customer invoices that need user attention:

        - Service product forced to 'on_delivery' but with no automatic delivery driver:
          balance will sit in the deferral account indefinitely without manual action.
        - Fallback chain failed (no deferral account configured anywhere): the line
          falls back to the standard income account but the user wanted deferral.
        """
        res = super()._post(soft=soft)
        for move in self.filtered(lambda m: m.move_type == "out_invoice" and m.state == "posted"):
            warnings = []
            for line in move.invoice_line_ids:
                if not line.product_id or line.display_type:
                    continue
                tmpl = line.product_id.product_tmpl_id
                method = tmpl._get_effective_revenue_method()
                if method != "on_delivery":
                    continue
                # Was a deferral account found?
                sale_line = line.sale_line_ids[:1]
                deferral = sale_line._get_unearned_revenue_account(line.product_id) if sale_line else False
                if not deferral:
                    warnings.append(_(
                        "Line %(name)s should defer revenue but no Unearned Revenue account is "
                        "configured (product category, company default, or Odoo's native "
                        "Deferred Revenue Account). Revenue will recognize immediately. Configure "
                        "the deferral account to enable on-delivery recognition.",
                        name=line.name or tmpl.display_name,
                    ))
                    continue
                # Service-on-delivery: warn about manual recognition.
                if tmpl.type != "consu":
                    warnings.append(_(
                        "Line %(name)s is a service set to recognize on delivery. No stock picking "
                        "will be generated, so revenue stays parked in the Unearned Revenue account "
                        "until it is manually moved. Consider Odoo's native time-based Deferred "
                        "Revenue feature instead.",
                        name=line.name or tmpl.display_name,
                    ))
            if warnings:
                move.message_post(body="<br/>".join(warnings))
        return res

    # TYPE: behavioral_change
    def button_draft(self):
        """When a posted invoice is reset to draft, reverse any revenue-recognition
        entries that originated from its lines so books remain balanced.
        """
        self._reverse_linked_revenue_recognition()
        return super().button_draft()

    # TYPE: behavioral_change
    def button_cancel(self):
        """When an invoice is cancelled, reverse any revenue-recognition entries
        that originated from its lines.
        """
        self._reverse_linked_revenue_recognition()
        return super().button_cancel()

    def _reverse_linked_revenue_recognition(self):
        """Find non-reversal recognition lines whose invoice_line_id belongs to self,
        group by their account_move_id, reverse the recognition moves, and mirror
        is_reversal=True audit rows.
        """
        Recognition = self.env["x.revenue.recognition.line"]
        for invoice in self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund")):
            recognition_lines = Recognition.search([
                ("invoice_line_id", "in", invoice.invoice_line_ids.ids),
                ("is_reversal", "=", False),
            ])
            if not recognition_lines:
                continue
            posted_moves = recognition_lines.account_move_id.filtered(
                lambda m: m.state == "posted"
            )
            if not posted_moves:
                continue
            try:
                with self.env.cr.savepoint():
                    reverse_moves = posted_moves._reverse_moves(
                        default_values_list=[
                            {"date": fields.Date.context_today(invoice)} for _m in posted_moves
                        ]
                    )
                    # _reverse_moves(cancel=False) creates draft moves; post so name is sequenced.
                    reverse_moves._post(soft=False)
                    move_to_reverse = dict(zip(posted_moves.ids, reverse_moves.ids))
                    for line in recognition_lines:
                        if line.account_move_id.id not in move_to_reverse:
                            continue
                        Recognition.create({
                            "picking_id": line.picking_id.id,
                            "move_id": line.move_id.id,
                            "sale_line_id": line.sale_line_id.id,
                            "invoice_line_id": line.invoice_line_id.id,
                            "account_move_id": move_to_reverse[line.account_move_id.id],
                            "quantity": line.quantity,
                            "amount_company_currency": line.amount_company_currency,
                            "amount_invoice_currency": line.amount_invoice_currency,
                            "recognition_date": fields.Date.context_today(invoice),
                            "is_reversal": True,
                            "company_id": line.company_id.id,
                            "invoice_currency_id": line.invoice_currency_id.id,
                        })
                    invoice.message_post(
                        body=_(
                            "Revenue recognition reversed on invoice change: %s",
                            ", ".join(reverse_moves.mapped("name")),
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                _logger.exception(
                    "Failed to reverse revenue recognition on invoice %s state change",
                    invoice.name,
                )
                invoice.message_post(
                    body=_("Failed to reverse revenue recognition: %s", exc)
                )
