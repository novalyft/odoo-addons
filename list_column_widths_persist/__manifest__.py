{
    "name": "Persistent List Column Widths — Remember Resized Columns",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": (
        "Remember manually resized list view column widths across navigation, "
        "view switches, and sessions — per view, for every user. Zero config. "
        "Works on all list views including embedded one2many/many2many lists. "
        "Odoo 19 Community and Enterprise."
    ),
    "description": """
Persistent List Column Widths — Remember Resized Columns
========================================================

Make manually-resized list (tree) view column widths persist across navigation,
view switches, and browser sessions — per view, for every user, with no
configuration required.

Why this module
---------------
* Standard Odoo 19 forgets a column's resized width the moment the list renderer
  unmounts (you navigate away, switch to kanban and back, or reload). Users who
  carefully size columns to their data lose that work constantly.
* This module remembers each view's column widths in the browser and restores
  them automatically the next time the view is shown.

How it works
------------
* The entire column-width behavior in Odoo lives in one hook
  (``useMagicColumnWidths``). This module ships a small, clearly-marked vendored
  fork of that hook (``usePersistentColumnWidths``) that seeds the first width
  computation from storage and saves the final widths when a resize ends.
* A single prototype patch on ``ListRenderer`` swaps the fork in, so standard
  list views and x2many embedded lists are all covered by one patch.
* Widths are keyed off Odoo's own ``createViewKey()`` (model + view id + x2many
  sub-view path + sorted field set), the same identifier Odoo already uses for
  the optional-columns memory — so persistence is per view and x2many-aware for
  free, and a change to the column set automatically invalidates stale widths.
* Persistence backend is ``localStorage`` (per browser profile, so effectively
  per user on a machine), behind a thin storage abstraction. No server model, no
  database writes, no configuration.

Highlights
----------
* Zero configuration — always on, for every user.
* Works on every list view, including embedded one2many / many2many lists.
* Survives navigation, view switches, and full browser-session reloads.
* Per-view "Reset column widths" entry in the optional-columns dropdown.
* Window resize keeps your widths (re-seeded and refit), instead of discarding
  them as stock Odoo does.
* Private/incognito mode and storage quota errors degrade silently to stock
  behavior — never a console error.
* Tiny, mechanically re-syncable vendored fork (every change tagged
  ``// NOVALYFT``) so it stays a ~5-minute diff on each Odoo upgrade.

Limitations
-----------
* Widths are stored per browser profile (``localStorage``); they do not sync
  across devices or browsers. A server-sync backend is possible in a future
  version and the storage layer is already abstracted for it.
* No admin-defined org-wide default widths, and no per-user on/off toggle
  (always on).

Keywords
--------
list view, tree view, column width, resize columns, persist, remember column
widths, sticky columns, localStorage, UX, productivity, Odoo 19.
    """,
    "author": "Novalyft Solutions",
    "maintainer": "Novalyft Solutions",
    "website": "https://novalyftsolutions.com",
    "support": "m.hassan@novalyftsolutions.com",
    "license": "LGPL-3",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "list_column_widths_persist/static/src/**/*.js",
            "list_column_widths_persist/static/src/**/*.xml",
        ],
        "web.assets_unit_tests": [
            "list_column_widths_persist/static/tests/**/*.test.js",
        ],
        "web.assets_tests": [
            "list_column_widths_persist/static/tests/tours/**/*.js",
        ],
    },
    "images": [
        # First entry doubles as the detail-page banner AND the card-cover
        # thumbnail. The _screenshot suffix is what the Apps Store cover slot
        # filters by — without it the cover falls through to the next image.
        # (Optional: add more feature *_screenshot.png entries here to enrich the listing.)
        "static/description/cover_screenshot.png",
        "static/description/reset_column_widths_screenshot.png",
    ],
    "price": 0.00,
    "currency": "USD",
    "installable": True,
    "application": False,
    "auto_install": False,
}
