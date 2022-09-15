# -*- coding: utf-8 -*-
# Copyright (c) 2022, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class DesignOrder(Document):
	def validate(self):
		old_panels = set([panel.panel for panel in self.design_panels if panel.panel != ''])
		new_panels = set([panel.panel for panel in self.batch_order if panel.panel != ''])

		to_add = []
		new_to_skip = []
		# Check if new is in old
		for panel in self.design_panels:
			if panel.panel in new_panels:
				to_add.append({
					'panel': panel.panel,
					'image_url': panel.image_url or ''
				})
				new_to_skip.append(panel.panel)
		for panel in new_panels:
			if panel in new_to_skip:
				continue
			to_add.append({
					'panel': panel
				})
		self.design_panels = []
		for panel in to_add:
			self.append('design_panels', panel)
		
	def add_order(self, po_number):
		# if frappe.db.exists('Production Order', data):
		# order = frappe.get_doc('Production Order', data)
		# order_list = frappe.get_list('Production Order',
		#					 filters={'barcode':barcode, 'docstatus': 1, 'status':['!=', 'Completed']})
		if not po_number or len(po_number) == 0:
			return False

		order_list = frappe.get_list('Production Order', filters={
									 'name': po_number, 'docstatus': 1})

		if len(order_list) == 0:
			frappe.msgprint(
				_(f"There is no submitted production order with name <b>{po_number}</b>"))
			return False

		first_order = order_list[0]
		first_order = frappe.get_doc('Production Order', first_order)

		pass_check = self.check_prodution_route(first_order, as_doc=True)
		if pass_check and not pass_check.get('status', False):
			frappe.msgprint(pass_check.get('msg', ''))
			return False

		return {
			'production_order': first_order.name,
			'quantity': first_order.qty,
			'item_code': first_order.production_item,
			'personalization': first_order.personalization,
			}
	
	def check_prodution_route(self, order, as_doc=False):
		pass_doc = False
		if not as_doc:
			if frappe.db.exists('Production Order', order):
				order = frappe.get_doc('Production Order', order)
				pass_doc = True
			else:
				return {
					'msg': _(f"Production order {order} not found"),
					'status': False
				}
		else:
			pass_doc = as_doc
				
		if pass_doc:
			if order.tray:
				return {
					'msg': _(f"Production order {order.name} already in tray <b>{order.tray}</b>"),
					'status': False
				}
			if order.status not in ['Not Started']:
				return {
					'msg': _(f"Production order {order.name} is <b>{order.status}</b>"),
					'status': False
				}

			if self.production_route != order.production_route:
				return {
					'msg': _(f"Production order {order.name} and Design have different Route"),
					'status': False
				}

			# if len(self.tray_steps) != len(order.production_steps):
			# 	return {
			# 		'msg': _(f"Production order {order.name} and Tray have different Route"),
			# 		'status': False
			# 	}

			# tray_step_list = [s.production_step for s in self.tray_steps]
			# order_step_list = [s.production_step for s in order.production_steps]

			# if len(tray_step_list) != len(order_step_list):
			# 	return {
			# 		'msg': _(f"Production order {order.name} and Tray have different Route"),
			# 		'status': False
			# 	}

			# for pair_step in zip(tray_step_list, order_step_list):
			# 	if(len(pair_step) != 2):
			# 		return {
			# 			'msg': _(f"Production order {order.name} and Tray have different Route"),
			# 			'status': False
			# 		}

			# 	if pair_step[0] != pair_step[1]:
			# 		return {
			# 			'msg': _(f"Production order {order.name} and Tray have different Route"),
			# 			'status': False
			# 		}

			return {
				'msg': '',
				'status': True
			}

		else:
			return {
				'msg': _("Something went wrong"),
				'status': False
			}
