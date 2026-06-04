from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "list_column_widths_persist")
class TestPersistColumnWidthsTour(HttpCase):
    """Drives the JS integration tour that resizes a Contacts list column and asserts the
    width survives a list -> kanban -> list view switch (the round trip stock Odoo forgets)."""

    def test_persist_widths_tour(self):
        # Use base.action_partner_form (the res.partner "Customers" list action defined in `base`,
        # hence always installed) so the tour is self-contained and needs no `contacts` app. We
        # navigate by the action's DB id via the /odoo/action-<id> web-client URL (numeric ids are
        # always accepted by the router), then start the (url-less) tour on that page.
        action = self.env.ref("base.action_partner_form")
        self.start_tour(
            "/odoo/action-%s" % action.id,
            "list_column_widths_persist_tour",
            login="admin",
        )
