# Copyright (c) 2022, ahmadragheb and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CustomerPO(Document):

	@frappe.whitelist()
	def create_sales_order(self):
		so_doc = frappe.new_doc("Sales Order")
		so_doc.customer = self.customer
		so_doc.transaction_date = self.date
		so_doc.delivery_date = self.delivery_date
		for item in self.items:
			so_doc.append("items", {
				"item_code": item.item_code,
				"item_name": frappe.db.get_value("Item", item.item_code, "item_name"),
				"description": item.description,
				"qty": item.qty,
				"uom": item.uom,
				"rate": item.rate,
				"amount": item.amount
			})
			
		so_doc.save()
		so_doc.against_customer_po = self.name
		so_doc.submit()

		sales_order = frappe.db.set_value(self.doctype, self.name, "sales_order", so_doc.name)

		return {"doc_name":so_doc.name}