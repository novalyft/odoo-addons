import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    x_recognition_line_count = fields.Integer(
        compute="_compute_x_recognition_line_count",
    )

    def _compute_x_recognition_line_count(self):
        Recognition = self.env["x.revenue.recognition.line"]
        for picking in self:
            picking.x_recognition_line_count = Recognition.search_count([
                ("picking_id", "=", picking.id),
            ])

    # TYPE: behavioral_change
    def _action_done(self):
        """Trigger automatic revenue recognition after super completes.

        Background (stock/models/stock_picking.py:1256): super sets date_done, marks moves
        as done, triggers downstream assigns, and sends the confirmation email. We hook
        post-super so the picking is fully validated when recognition logic runs.

        Routing:
          - outgoing non-return -> _recognize_revenue (Dr Unearned, Cr Sales).
          - incoming return     -> _reverse_revenue_recognition (Dr Sales, Cr Unearned).

        Each picking's recognition runs inside a savepoint with try/except so that a
        recognition failure never blocks the underlying picking validation.
        """
        res = super()._action_done()
        outgoing = self.filtered(
            lambda p: p.picking_type_id.code == "outgoing" and not p.return_id
        )
        incoming_returns = self.filtered(
            lambda p: p.picking_type_id.code == "incoming" and p.return_id
        )
        for picking in outgoing:
            picking._recognize_revenue()
        for picking in incoming_returns:
            picking._reverse_revenue_recognition()
        return res

    # Note on FR7 (picking cancellation): Odoo 19's stock.move._action_cancel raises
    # UserError when any move in the picking is in 'done' state. Because revenue
    # recognition fires from _action_done (post-super), every recognized picking is
    # already 'done' by the time it could be cancelled — so action_cancel can never
    # reach our reversal code. To undo a delivery, users must create a return picking;
    # _reverse_revenue_recognition handles that path. Invoice-side cancellation
    # (button_draft / button_cancel) is handled by account_move._reverse_linked_revenue_recognition.

    def action_view_revenue_recognition_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Revenue Recognition"),
            "res_model": "x.revenue.recognition.line",
            "view_mode": "list,form,pivot",
            "domain": [("picking_id", "=", self.id)],
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _recognize_revenue(self):
        """Build and post one consolidated journal entry per picking that moves the
        delivered portion of each SO line's revenue from Unearned to Sales.

        - TYPE: addition
        Algorithm:
          1. For each done stock.move with sale_line_id and method == 'on_delivery':
             compute delta_qty = delivered (in SO-line UoM) - already_recognized.
          2. FIFO-allocate delta_qty across the SO line's posted invoice lines
             (oldest first), proportionally splitting amount via the invoice's frozen
             balance / amount_currency (preserves the invoice-date FX rate).
          3. Build ONE account.move per picking with one Dr/Cr pair per allocation
             (Dr deferral, Cr standard income), post it, and write audit-trail rows.
        Wrapped in a per-picking savepoint + try/except so failure never blocks the
        underlying picking validation.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                allocations = self._collect_recognition_allocations(is_reversal=False)
                if allocations:
                    self._post_recognition_entry(allocations, is_reversal=False)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Revenue recognition failed for picking %s", self.name)
            self.message_post(body=_("Revenue recognition failed: %s", exc))
            self.activity_schedule(
                "mail.mail_activity_data_warning",
                summary=_("Revenue recognition error"),
                note=_(
                    "The automatic Unearned-Revenue → Sales journal entry could not be "
                    "posted: %s",
                    exc,
                ),
            )

    def _reverse_revenue_recognition(self):
        """Mirror of _recognize_revenue for return pickings.

        - TYPE: addition
        For each returned stock.move (move.origin_returned_move_id set), allocate
        returned qty LIFO against non-reversed recognition lines on the original
        move, build ONE fresh account.move with inverted Dr/Cr (no _reverse_moves
        because we need partial-qty control), post it, and write is_reversal=True
        audit rows.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                allocations = self._collect_recognition_allocations(is_reversal=True)
                if allocations:
                    self._post_recognition_entry(allocations, is_reversal=True)
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                "Revenue recognition reversal failed for return picking %s",
                self.name,
            )
            self.message_post(body=_("Revenue recognition reversal failed: %s", exc))
            self.activity_schedule(
                "mail.mail_activity_data_warning",
                summary=_("Revenue recognition reversal error"),
                note=str(exc),
            )

    def _collect_recognition_allocations(self, is_reversal):
        """Walk this picking's moves and produce a list of allocation dicts.

        Each allocation dict has keys: move, sale_line, inv_line, qty_to_recognize,
        amount_company, amount_doc.
        """
        self.ensure_one()
        allocations = []

        for move in self.move_ids.filtered(lambda m: m.state == "done" and m.sale_line_id):
            sale_line = move.sale_line_id
            product = sale_line.product_id
            if not product:
                continue

            method = product.product_tmpl_id._get_effective_revenue_method()
            if method != "on_delivery":
                continue

            so_line_uom = sale_line.product_uom_id
            move_qty_in_so_uom = move.product_uom._compute_quantity(
                move.quantity, so_line_uom
            ) if move.product_uom and so_line_uom else move.quantity

            if is_reversal:
                # For a return move, the "ancestor" stock.move that was recognized
                # lives in origin_returned_move_id.
                source_move = move.origin_returned_move_id
                if not source_move:
                    continue
                source_recognized = source_move._get_recognized_quantity()
                if float_is_zero(source_recognized, precision_rounding=so_line_uom.rounding):
                    continue
                # LIFO: cap returned qty at what's currently recognized on the source.
                qty_to_process = min(move_qty_in_so_uom, source_recognized)
                if float_is_zero(qty_to_process, precision_rounding=so_line_uom.rounding):
                    continue
                allocation_target_move = source_move
            else:
                already = move._get_recognized_quantity()
                qty_to_process = move_qty_in_so_uom - already
                if float_compare(qty_to_process, 0.0, precision_rounding=so_line_uom.rounding) <= 0:
                    continue
                allocation_target_move = move

            allocations.extend(
                self._allocate_qty_across_invoices(
                    move=move,
                    target_move=allocation_target_move,
                    sale_line=sale_line,
                    qty_to_process=qty_to_process,
                    is_reversal=is_reversal,
                )
            )
        return allocations

    def _allocate_qty_across_invoices(self, move, target_move, sale_line, qty_to_process, is_reversal):
        """Distribute qty_to_process across the SO line's posted invoice lines.

        On forward recognition: FIFO (oldest invoice first).
        On reversal: LIFO (newest first), so the most recent recognition is unwound first.
        """
        so_line_uom = sale_line.product_uom_id
        rounding = so_line_uom.rounding if so_line_uom else 0.0
        Recognition = self.env["x.revenue.recognition.line"]

        invoice_lines = sale_line.invoice_lines.filtered(
            lambda l: l.parent_state == "posted"
            and l.move_id.move_type == "out_invoice"
            and l.x_target_revenue_account_id
        )
        if not invoice_lines:
            return []

        order_key = "date"
        invoice_lines = invoice_lines.sorted(order_key, reverse=is_reversal)

        results = []
        remaining = qty_to_process
        for inv_line in invoice_lines:
            if float_is_zero(remaining, precision_rounding=rounding):
                break
            if float_is_zero(inv_line.quantity, precision_rounding=rounding):
                continue

            if is_reversal:
                # Available to reverse = currently recognized via this inv_line for target_move
                recognized_for_pair = sum(
                    Recognition.search([
                        ("move_id", "=", target_move.id),
                        ("invoice_line_id", "=", inv_line.id),
                        ("is_reversal", "=", False),
                    ]).mapped("quantity")
                ) - sum(
                    Recognition.search([
                        ("move_id", "=", target_move.id),
                        ("invoice_line_id", "=", inv_line.id),
                        ("is_reversal", "=", True),
                    ]).mapped("quantity")
                )
                available = recognized_for_pair
            else:
                # Available to recognize on this invoice line = inv_line.quantity - already_recognized
                recognized = sum(
                    Recognition.search([
                        ("invoice_line_id", "=", inv_line.id),
                        ("is_reversal", "=", False),
                    ]).mapped("quantity")
                ) - sum(
                    Recognition.search([
                        ("invoice_line_id", "=", inv_line.id),
                        ("is_reversal", "=", True),
                    ]).mapped("quantity")
                )
                available = inv_line.quantity - recognized

            if float_compare(available, 0.0, precision_rounding=rounding) <= 0:
                continue
            take = min(remaining, available)
            if float_is_zero(take, precision_rounding=rounding):
                continue

            amount_company = (take / inv_line.quantity) * abs(inv_line.balance)
            amount_doc = (take / inv_line.quantity) * abs(inv_line.amount_currency)
            results.append({
                "move": target_move if is_reversal else move,
                "sale_line": sale_line,
                "inv_line": inv_line,
                "qty_to_recognize": take,
                "amount_company": amount_company,
                "amount_doc": amount_doc,
            })
            remaining -= take

        return results

    def _post_recognition_entry(self, allocations, is_reversal):
        """Build, post, and audit one consolidated account.move from `allocations`."""
        self.ensure_one()
        company = self.company_id
        journal = company.x_recognition_journal_id or self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", company.id)],
            limit=1,
        )
        if not journal:
            raise UserError(
                _(
                    "No miscellaneous journal configured for company %s. Set one in "
                    "Accounting Settings or create a general-type journal.",
                    company.display_name,
                )
            )

        line_vals = []
        for alloc in allocations:
            inv_line = alloc["inv_line"]
            deferral_account = inv_line.account_id
            income_account = inv_line.x_target_revenue_account_id
            if not deferral_account or not income_account:
                # Cannot recognize if either side is missing; skip silently.
                continue
            amount = alloc["amount_company"]
            sale_line = alloc["sale_line"]
            label = _(
                "%(action)s: %(name)s (qty %(qty)s)",
                action=_("Reversal") if is_reversal else _("Recognition"),
                name=sale_line.name or sale_line.product_id.display_name,
                qty=alloc["qty_to_recognize"],
            )
            if is_reversal:
                debit_account, credit_account = income_account, deferral_account
            else:
                debit_account, credit_account = deferral_account, income_account
            line_vals.append((0, 0, {
                "account_id": debit_account.id,
                "name": label,
                "debit": amount,
                "credit": 0.0,
                "partner_id": self.partner_id.commercial_partner_id.id,
            }))
            line_vals.append((0, 0, {
                "account_id": credit_account.id,
                "name": label,
                "debit": 0.0,
                "credit": amount,
                "partner_id": self.partner_id.commercial_partner_id.id,
            }))

        if not line_vals:
            return self.env["account.move"]

        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": fields.Date.context_today(self),
            "ref": _(
                "%(prefix)s for picking %(name)s",
                prefix=_("Revenue reversal") if is_reversal else _("Revenue recognition"),
                name=self.name,
            ),
            "line_ids": line_vals,
            "company_id": company.id,
        })
        move._post(soft=False)

        for alloc in allocations:
            if not alloc["inv_line"].x_target_revenue_account_id:
                continue
            self.env["x.revenue.recognition.line"].create({
                "picking_id": self.id,
                "move_id": alloc["move"].id,
                "sale_line_id": alloc["sale_line"].id,
                "invoice_line_id": alloc["inv_line"].id,
                "account_move_id": move.id,
                "quantity": alloc["qty_to_recognize"],
                "amount_company_currency": alloc["amount_company"],
                "amount_invoice_currency": alloc["amount_doc"],
                "recognition_date": fields.Date.context_today(self),
                "is_reversal": is_reversal,
                "company_id": company.id,
                "invoice_currency_id": alloc["inv_line"].currency_id.id,
            })

        verb = _("reversal") if is_reversal else _("recognition")
        self.message_post(body=_("Revenue %(verb)s entry %(name)s posted.", verb=verb, name=move.name))
        move.message_post(body=_("Generated from picking %s", self.name))
        return move
