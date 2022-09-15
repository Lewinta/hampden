# Copyright (c) 2013, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    columns = [
        {
            "fieldname": "production_order",
            "label": _("Production Order"),
            "fieldtype": "Link",
            "options": "Production Order",
            "width": 200
        },
		{
            "fieldname": "item_to_manufacture",
            "label": _("Item To Manufacture"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 250
        },
        {
            "fieldname": "customer_order",
            "label": _("Customer Order"),
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 150
        },
        {
            "fieldname": "last_finished_step",
            "label": _("Last Finished Step"),
            "fieldtype": "Data",
            "width": 150
        },
		{
            "fieldname": "finished_at",
            "label": _("Finished At"),
            "fieldtype": "Data",
            "width": 100
        },
		{
            "fieldname": "finished_by",
            "label": _("Finished By"),
            "fieldtype": "Data",
            "width": 100
        },
		{
            "fieldname": "next_production_step",
            "label": _("Next Production Step "),
            "fieldtype": "Data",
            "width": 150
        },
    ]
    data = get_data(filters)
    return columns, data


def get_data(filters):
    return frappe.db.sql("""
		SELECT * 
		FROM `tabProduction Ledger`
        ORDER BY name, creation DESC
	""", as_dict=True)
