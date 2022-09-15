# -*- coding: utf-8 -*-
# Copyright (c) 2021, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class CustomerMarking(Document):
	def validate(self):
		if self.default == 1:
			self.customer = ''
			self.customer_name = ''
			cms = frappe.get_list('Customer Marking', filters={'default': 1})
			if len(cms) > 0:
				cms = cms[0]
				frappe.throw(_(f"default Customer Marking is setup in <a href='/desk#Form/Customer Marking/{cms.name}'>{cms.name}</a>!"))
		else:
			if not self.customer:
				frappe.throw(_("Please Select Customer!"))
