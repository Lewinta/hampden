# -*- coding: utf-8 -*-
# Copyright (c) 2021, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.data import flt
from frappe.model.document import Document

class ProductionRoute(Document):
	def validate(self):
		total_labor = 0
		total_overhead = 0
		for step in self.route_steps:
			total_labor += float(step.labor)
			total_overhead += float(step.overhead)
		
		self.total_overhead = total_overhead
		self.total_labor = total_labor
	
	def on_update(self):
		items_with_route = frappe.get_list('Item', filters={'production_route': self.name})
		for item in items_with_route:
			item = frappe.get_doc('Item', item.name)
			item.production_item_table = []
			item.total_labor = self.total_labor
			item.total_overhead = self.total_overhead
			item.total_production_route = flt(self.total_labor) + flt(self.total_overhead)
			for step in self.route_steps:
				item.append('production_item_table', {
					'production_step': step.production_step,
					'labor': step.labor,
					'overhead': step.overhead,
					'qty': 1,
					'issue_step': step.issue_step,
					'total_labor': step.labor,
					'total_overhead': step.overhead,
					'total': float(step.labor) + float(step.overhead)
				})
			item.on_update()
			item.save()
		frappe.db.commit()
		
		
