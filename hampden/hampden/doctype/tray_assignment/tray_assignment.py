# -*- coding: utf-8 -*-
# Copyright (c) 2021, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class TrayAssignment(Document):
	def update_orders_with_tray(self, cancel_event=False):
		if cancel_event:
			frappe.db.sql(""" UPDATE `tabProduction Order` SET tray = NULL WHERE tray='{}'""".format(self.name))
		else:
			for order in self.batch_order:
				order = frappe.get_doc('Production Order', order.production_order)
				order.db_set('tray', self.tray, update_modified=False)

	def update_production_step(self, row, date):
		if self.docstatus != 1:
			frappe.throw('Please Submit Order before Update the Step!')
		date = frappe.utils.nowdate()
		for order in self.batch_order:
			order_master = frappe.get_doc(
				'Production Order', order.production_order)
			if order_master.status != "Completed" and order_master.docstatus == 1:
				order_master.update_production_step(row, date)
	
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
			'status': first_order.status,
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
					'msg': _(f"Production order {order.name} and Tray have different Route"),
					'status': False
				}

			if len(self.tray_steps) != len(order.production_steps):
				return {
					'msg': _(f"Production order {order.name} and Tray have different Route"),
					'status': False
				}

			tray_step_list = [s.production_step for s in self.tray_steps]
			order_step_list = [s.production_step for s in order.production_steps]

			if len(tray_step_list) != len(order_step_list):
				return {
					'msg': _(f"Production order {order.name} and Tray have different Route"),
					'status': False
				}

			for pair_step in zip(tray_step_list, order_step_list):
				if(len(pair_step) != 2):
					return {
						'msg': _(f"Production order {order.name} and Tray have different Route"),
						'status': False
					}

				if pair_step[0] != pair_step[1]:
					return {
						'msg': _(f"Production order {order.name} and Tray have different Route"),
						'status': False
					}

			return {
				'msg': '',
				'status': True
			}

		else:
			return {
				'msg': _("Something went wrong"),
				'status': False
			}

	
