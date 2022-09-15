# -*- coding: utf-8 -*-
# Copyright (c) 2021, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ItemAssociation(Document):
	def after_insert(self):
		for row in self.item_association:
			master_item = frappe.get_doc('Item', row.independent)
			# clear Item Association
