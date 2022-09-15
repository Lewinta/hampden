# -*- coding: utf-8 -*-
# Copyright (c) 2021, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class OrderedItemsToBeManufactured(Document):
	def fetch_order_items(self, from_date=False, to_date=False, with_manu_items=0):
		cds = []
		if from_date: cds.append(' DATEDIFF(so.transaction_date, "{}") > -1 '.format(from_date))
		if to_date: cds.append(' DATEDIFF("{}", so.transaction_date) > -1 '.format(to_date))
		conds = ""
		if len(cds) > 0: conds = ' AND ' + ' AND '.join(cds)
		else: conds = ""
		# frappe.msgprint(conds)
		if with_manu_items:
			result = frappe.db.sql("""
				SELECT so.name, so.transaction_date as td, so.transaction_date, soi.item_code, soi.item_name, soi.qty, soi.name as soi, po.name as production_order
				FROM `tabSales Order` so
				LEFT JOIN `tabSales Order Item` soi ON soi.parent=so.name
				LEFT JOIN `tabItem` i ON soi.item_code=i.item_code
				LEFT JOIN `tabProduction Order` po ON po.sales_order=so.name AND po.production_item=i.item_code AND po.docstatus=1
				WHERE so.docstatus=1  AND IFNULL(i.default_bom, '') <> '' {} """.format(conds), as_dict=True)
		else:
			result = frappe.db.sql("""
				SELECT so.name, so.transaction_date as td, so.transaction_date, soi.item_code, soi.item_name, soi.qty, soi.name as soi, '' as production_order
				FROM `tabSales Order` so
				LEFT JOIN `tabSales Order Item` soi ON soi.parent=so.name
				LEFT JOIN `tabItem` i ON soi.item_code=i.item_code
				WHERE so.docstatus=1 AND IFNULL(i.default_bom, '') <> ''
									AND so.name NOT IN (SELECT DISTINCT(sales_order) FROM `tabProduction Order` WHERE docstatus=1) {}""".format(conds), as_dict=True)
		return result

	def create_production_orders(self, items=[]):
		for item in items:
			item = frappe.db.exists('Sales Order Item', item)
			if not item: continue
			item = frappe.get_doc('Sales Order Item', item)
			master_item = frappe.get_doc('Item', item.item_code)
			if not master_item.default_bom: continue
			po = frappe.new_doc('Production Order')
			# for i in range(item.qty):
			po.sales_order = item.parent
			po.production_item = item.item_code
			po.bom_no = master_item.default_bom
			po.stock_uom = item.uom
			po.production_route = master_item.production_route
			po.total_labor = master_item.total_labor
			po.total_overhead = master_item.total_overhead
			po.intrinsic_material_cost = master_item.intrinsic_material_cost
			po.fabrication_cost = master_item.fabrication_cost
			po.cutting_loss_cost = master_item.cutting_loss_cost
			po.total_production_route = master_item.total_labor + master_item.total_overhead
			po.raw_material_cost = master_item.intrinsic_material_cost + master_item.fabrication_cost + master_item.cutting_loss_cost
			po.total_cost = master_item.total_cost

			po.set_production_steps()
			po.save()
			po.submit()
			frappe.db.commit()
