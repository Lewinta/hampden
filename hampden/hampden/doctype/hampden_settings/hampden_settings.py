# -*- coding: utf-8 -*-
# Copyright (c) 2021, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

class HampdenSettings(Document):
	def validate(self):
		if self.auto_jv:
			if not self.labor_account or not self.overhead_account or not self.creditor_account:
				frappe.throw('Please Set Accounts for entry!')
		if self.auto_item_price:
			if not self.default_currency or not self.default_price_list:
				frappe.throw('Please Set Currency and Price List!')
		
	def	get_valuation_rate(self, item_code, company=frappe.defaults.get_global_default('company')):
		""" Get weighted average of valuation rate from all warehouses """
		if not company:
			company = frappe.defaults.get_global_default('company')

		valuation_rate = 0

		total_qty, total_value, valuation_rate = 0.0, 0.0, 0.0
		item_bins = frappe.db.sql("""
			select
				bin.actual_qty, bin.stock_value
			from
				`tabBin` bin, `tabWarehouse` warehouse
			where
				bin.item_code=%(item)s
				and bin.warehouse = warehouse.name
				and warehouse.company=%(company)s""",
								{"item": item_code, "company": company}, as_dict=1)

		for d in item_bins:
			total_qty += flt(d.actual_qty)
			total_value += flt(d.stock_value)

		if total_qty:
			valuation_rate = total_value / total_qty

		if valuation_rate <= 0:
			last_valuation_rate = frappe.db.sql("""select valuation_rate
				from `tabStock Ledger Entry`
				where item_code = %s and valuation_rate > 0
				order by posting_date desc, posting_time desc, creation desc limit 1""", item_code)

			valuation_rate = flt(
				last_valuation_rate[0][0]) if last_valuation_rate else 0

		if not valuation_rate:
			valuation_rate = frappe.db.get_value(
				"Item", item_code, "valuation_rate")
		

		return flt(valuation_rate)
	
	def	get_last_purchase(self, item_code):
		rate = frappe.db.get_value(
            "Item", item_code, "last_purchase_rate")
		
		return rate if rate else 0

	def update_rates_with_valuation(self):
		self.start_update("Valuation Rate")

	def update_rates_with_last_purchase_rate(self):
		self.start_update("Last Purchase")
	
	def start_update(self, update_type):
		settings = frappe.get_doc('Hampden Settings')
		allow_zero_rate = True if settings.allow_zero_rate else False

		parents_to_update = set()
		
		for item in frappe.get_list('Item Item'):
			item = frappe.get_doc('Item Item', item.name)
			if update_type == "Valuation Rate":
				rate = self.get_valuation_rate(item.item_code)
			elif update_type == "Last Purchase":
				rate = self.get_last_purchase(item.item_code)
			else:
				rate = 0
			parents_to_update.add(item.parent)
			# total_cost += (rate*item.qty)
			if rate:
				item.db_set('rate', rate)
				item.db_set('base_rate', rate)
				item.db_set('amount', (rate*item.qty))
				item.db_set('base_amount', (rate*item.qty))
			else:
				if allow_zero_rate:
					item.db_set('rate', 0)
					item.db_set('base_rate', 0)
					item.db_set('amount', 0)
					item.db_set('base_amount', 0)
				# frappe.db.commit()
		
		for item in frappe.get_list('Production Scrap Item'):
			item = frappe.get_doc('Production Scrap Item', item.name)
			parents_to_update.add(item.parent)
			if update_type == "Valuation Rate":
				rate = self.get_valuation_rate(item.item_code)
			elif update_type == "Last Purchase":
				rate = self.get_last_purchase(item.item_code)
			else:
				rate = 0
			# total_cost += (rate*item.qty)
			# print(item.item_code, rate)
			if rate:
				item.db_set('rate', rate)
				item.db_set('base_rate', rate)
				item.db_set('amount', (rate*item.stock_qty))
				item.db_set('base_amount', (rate*item.stock_qty))
			else:
				if allow_zero_rate:
					item.db_set('rate', 0)
					item.db_set('base_rate', 0)
					item.db_set('amount', 0)
					item.db_set('base_amount', 0)
				# frappe.db.commit()
		
		for item in parents_to_update:
			item = frappe.get_doc('Item', item)
			if len(item.items) > 0:
				total_cost = 0
				total_scrap = 0
				for i in item.items:
					total_cost += flt(i.amount)
				for i in item.production_scrap_item:
					total_scrap += flt(i.amount)
				
				item.raw_material_cost = total_cost
				item.scrap_material_cost = total_scrap
				item.save()
				# frappe.db.commit()
			else:
				item.production_scrap_item = []
				item.raw_material_cost = 0
				item.scrap_material_cost = 0
				item.save()
		frappe.db.commit()
