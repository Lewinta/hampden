from __future__ import unicode_literals
from frappe import _


def get_data():
    return [
        {
            "label": _("Settings"),
            "items": [
                {
                    "type": "doctype",
                    "name": _("Hampden Settings"),
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": _("Item Association"),
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": _("Production Step"),
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": _("Issue Step"),
                    "onboard": 1,
                }
            ]
        },
        {
            "label": _("Bill of Materials"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Item",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Production Route",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Gold And Silver Purchasing",
                    "onboard": 1,
                }
            ]
        },
        {
            "label": _("Hampden Production"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Production Order",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Stock Entry",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Design Order",
                    "onboard": 1,
                }
            ]
        },
        {
            "label": _("Buying"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Supplier",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Purchase Order",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Purchase Receipt",
                    "onboard": 1,
                },
            ]
        },
        {
            "label": _("Selling"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Customer",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Sales Order",
                    "onboard": 1,
                }
            ]
        },
        {
            "label": _("Production Tools"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Productions Monitor",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Production Ledger",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Ordered Items To Be Manufactured",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Customer Marking",
                    "onboard": 1,
                }
            ]
        },
        {
            "label": _("Tray Management"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Tray",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Tray Assignment",
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Tray Assignment Ledger",
                    "onboard": 1,
                }
            ]
        },
        {
            "label": _("Production Reports"),
            "items": [
                {
                    "type": "report",
                    "name": "Production Ledger",
                    "doctype": "Production Ledger",
                    "is_query_report": True,
                }
            ]
        },
    ]
