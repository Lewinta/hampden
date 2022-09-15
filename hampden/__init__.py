# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__version__ = '0.0.1'


import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from frappe import _
from frappe.utils import cstr, cint, flt, comma_or, getdate, nowdate, formatdate, format_time, get_link_to_form
from six import string_types, itervalues, iteritems
from erpnext.stock.get_item_details import get_bin_details, get_default_cost_center, get_reserved_qty_for_so

#Overwrite Method in Stock Entry
class DuplicateEntryForProductionOrderError(frappe.ValidationError): pass
# NO need to validate BOM !
# self.validate_bom() 

def validate_production_order(self):
	if not self.production_order:
		return
	
	# self.fg_completed_qty = 1
	if self.purpose in ("Manufacture", "Material Transfer for Manufacture", "Material Consumption for Manufacture"):
		# check if Production order is entered
		if (self.purpose=="Manufacture" or self.purpose=="Material Consumption for Manufacture") and self.production_order:
			po = frappe.get_doc('Production Order', self.production_order)
			self.fg_completed_qty = po.qty
			if not self.fg_completed_qty:
				frappe.throw(_("For Quantity (Manufactured Qty) is mandatory"))

			self.check_if_production_operations_completed()

			self.check_duplicate_entry_for_production_order()
	elif self.purpose != "Material Transfer":
		self.production_order = None

def check_if_production_operations_completed(self):
	if not self.production_order:
		return
	"""Check if Time Sheets are completed against before manufacturing to capture operating costs."""
	prod_order = frappe.get_doc("Production Order", self.production_order)
	allowance_percentage = flt(frappe.db.get_single_value("Manufacturing Settings", "overproduction_percentage_for_work_order"))

	for d in prod_order.get("operations"):
		total_completed_qty = flt(self.fg_completed_qty) + flt(prod_order.produced_qty)
		completed_qty = d.completed_qty + (allowance_percentage/100 * d.completed_qty)
		if total_completed_qty > flt(completed_qty):
			job_card = frappe.db.get_value('Job Card', {'operation_id': d.name}, 'name')
			if not job_card:
				frappe.throw(_("Production Order {0}: Job Card not found for the operation {1}").format(self.production_order, d.operation))

			production_order_link = frappe.utils.get_link_to_form('Production Order', self.production_order)
			job_card_link = frappe.utils.get_link_to_form('Job Card', job_card)
			frappe.throw(_("Row #{0}: Operation {1} is not completed for {2} qty of finished goods in Production Order {3}. Please update operation status via Job Card {4}.").format(d.idx, frappe.bold(d.operation), frappe.bold(total_completed_qty), production_order_link, job_card_link), OperationsNotCompleteError)

def check_duplicate_entry_for_production_order(self):
	if not self.production_order:
		return
	other_ste = [t[0] for t in frappe.db.get_values("Stock Entry",  {
		"production_order": self.production_order,
		"purpose": self.purpose,
		"docstatus": ["!=", 2],
		"name": ["!=", self.name]
	}, "name")]

	if other_ste:
		production_item, qty = frappe.db.get_value("Production Order",
			self.production_order, ["production_item", "qty"])
		args = other_ste + [production_item]
		fg_qty_already_entered = frappe.db.sql("""select sum(transfer_qty)
			from `tabStock Entry Detail`
			where parent in (%s)
				and item_code = %s
				and ifnull(s_warehouse,'')='' """ % (", ".join(["%s" * len(other_ste)]), "%s"), args)[0][0]
		if fg_qty_already_entered and fg_qty_already_entered >= qty:
			frappe.throw(_("Stock Entries already created for Production Order ")
				+ self.production_order + ":" + ", ".join(other_ste), DuplicateEntryForProductionOrderError)

# self.validate_finished_goods()
def validate_finished_goods_in_production_order(self):
	if not self.production_order:
		return
	"""validation: finished good quantity should be same as manufacturing quantity"""
	if not self.production_order: return

	items_with_target_warehouse = []
	allowance_percentage = flt(frappe.db.get_single_value("Manufacturing Settings",
		"overproduction_percentage_for_work_order"))

	production_item, wo_qty = frappe.db.get_value("Production Order",
		self.production_order, ["production_item", "qty"])

	for d in self.get('items'):
		if (self.purpose != "Send to Subcontractor" and d.bom_no
			and flt(d.transfer_qty) > flt(self.fg_completed_qty) and d.item_code == production_item):
			frappe.throw(_("Quantity in row {0} ({1}) must be same as manufactured quantity {2}"). \
				format(d.idx, d.transfer_qty, self.fg_completed_qty))

		if self.production_order and self.purpose == "Manufacture" and d.t_warehouse:
			items_with_target_warehouse.append(d.item_code)

	if self.production_order and self.purpose == "Manufacture":
		allowed_qty = wo_qty + (allowance_percentage/100 * wo_qty)
		if self.fg_completed_qty > allowed_qty:
			frappe.throw(_("For quantity {0} should not be grater than production order quantity {1}")
				.format(flt(self.fg_completed_qty), wo_qty))

		if production_item not in items_with_target_warehouse:
			frappe.throw(_("Finished Item {0} must be entered for Manufacture type entry")
				.format(production_item))

def update_production_order(self):
	if not self.production_order:
		return
	def _validate_production_order(pro_doc):
		if flt(pro_doc.docstatus) != 1:
			frappe.throw(_("Production Order {0} must be submitted").format(self.production_order))

		if pro_doc.status == 'Stopped':
			frappe.throw(_("Transaction not allowed against stopped Production Order {0}").format(self.production_order))

	if self.job_card:
		job_doc = frappe.get_doc('Job Card', self.job_card)
		job_doc.set_transferred_qty(update_status=True)

	if self.production_order:
		pro_doc = frappe.get_doc("Production Order", self.production_order)
		_validate_production_order(pro_doc)

		if self.purpose == "Manufacture":
			if self.docstatus == 1:
				for item in self.items:
					if item.is_scrap == 1 and item.production_detail:
						scrap_item = frappe.get_doc('Production Order Scrap', item.production_detail)
						if (item.qty + scrap_item.consumed_qty) > scrap_item.required_qty:
							frappe.throw("Consumed Qty > Required Qty for scrap item {}".format(item.item_code))
					elif item.is_scrap == 0 and item.production_detail:
						reqd_item = frappe.get_doc('Production Order Item', item.production_detail)
						if (item.qty + reqd_item.consumed_qty) > reqd_item.required_qty:
							frappe.throw("Consumed Qty > Required Qty for item {}".format(item.item_code))
			if self.docstatus == 2:
				for item in self.items:
					if item.is_scrap == 1 and item.production_detail:
						scrap_item = frappe.get_doc('Production Order Scrap', item.production_detail)
						if (scrap_item.consumed_qty - item.qty) < 0:
							frappe.throw("Consumed qty can not be less than zero for scrap item {}".format(item.item_code))
						
					elif item.is_scrap == 0 and item.production_detail:
						reqd_item = frappe.get_doc('Production Order Item', item.production_detail)
						if (reqd_item.consumed_qty - item.qty) < 0:
							frappe.throw("Consumed qty can not be less than zero for scrap item {}".format(item.item_code))
		else:
			if self.docstatus == 1:
				for item in self.items:
					if item.is_scrap == 1 and item.production_detail:
						scrap_item = frappe.get_doc('Production Order Scrap', item.production_detail)
						if (item.qty + scrap_item.transferred_qty) > scrap_item.required_qty:
							frappe.throw("Transferred qty > Required Qty for scrap item {}".format(item.item_code))
					elif item.is_scrap == 0 and item.production_detail:
						reqd_item = frappe.get_doc('Production Order Item', item.production_detail)
						if (item.qty + reqd_item.transferred_qty) > reqd_item.required_qty:
							frappe.throw("Transferred qty > Required Qty for item {}".format(item.item_code))
			if self.docstatus == 2:
				for item in self.items:
					if item.is_scrap == 1 and item.production_detail:
						scrap_item = frappe.get_doc('Production Order Scrap', item.production_detail)
						if (scrap_item.transferred_qty - item.qty) < 0:
							frappe.throw("Transferred qty can not be less than zero for scrap item {}".format(item.item_code))
						
					elif item.is_scrap == 0 and item.production_detail:
						reqd_item = frappe.get_doc('Production Order Item', item.production_detail)
						if (reqd_item.transferred_qty - item.qty) < 0:
							frappe.throw("Transferred qty can not be less than zero for scrap item {}".format(item.item_code))
						
		pro_doc.run_method("update_status")
		# if self.fg_completed_qty:
		pro_doc.run_method("update_production_order_qty")
		if self.purpose == "Manufacture":
			pro_doc.run_method("update_planned_qty")

# update_so_in_serial_number(self):
def update_so_in_serial_number_for_production(self):
	if not self.production_order:
		return
	so_name, item_code = frappe.db.get_value("Production Order", self.production_order, ["sales_order", "production_item"])
	if so_name and item_code:
		qty_to_reserve = get_reserved_qty_for_so(so_name, item_code)
		if qty_to_reserve:
			reserved_qty = frappe.db.sql("""select count(name) from `tabSerial No` where item_code=%s and
				sales_order=%s""", (item_code, so_name))
			if reserved_qty and reserved_qty[0][0]:
				qty_to_reserve -= reserved_qty[0][0]
			if qty_to_reserve > 0:
				for item in self.items:
					if item.item_code == item_code:
						serial_nos = (item.serial_no).split("\n")
						for serial_no in serial_nos:
							if qty_to_reserve > 0:
								frappe.db.set_value("Serial No", serial_no, "sales_order", so_name)
								qty_to_reserve -=1

def get_bom_items_as_dict(bom, company, qty=1, fetch_exploded=1, fetch_scrap_items=0, include_non_stock_items=False, fetch_qty_in_stock_uom=True):
	item_dict = {}

	# Did not use qty_consumed_per_unit in the query, as it leads to rounding loss
	query = """select
				bom_item.item_code,
				bom_item.idx,
				bom_item.issue_step,
				item.item_name,
				bom_item.{qty_field}/ifnull(bom.quantity, 1) * %(qty)s as qty,
				item.image,
				bom.project,
				item.stock_uom,
				item.allow_alternative_item,
				item_default.default_warehouse,
				item_default.expense_account as expense_account,
				item_default.buying_cost_center as cost_center
				{select_columns}
			from
				`tab{table}` bom_item
				JOIN `tabBOM` bom ON bom_item.parent = bom.name
				JOIN `tabItem` item ON item.name = bom_item.item_code
				LEFT JOIN `tabItem Default` item_default
					ON item_default.parent = item.name and item_default.company = %(company)s
			where
				bom_item.docstatus < 2
				and bom.name = %(bom)s
				and item.is_stock_item in (1, {is_stock_item})
				{where_conditions}
				order by idx"""

	is_stock_item = 0 if include_non_stock_items else 1
	if cint(fetch_exploded):
		query = query.format(table="BOM Explosion Item",
			where_conditions="",
			is_stock_item=is_stock_item,
			qty_field="stock_qty",
			select_columns = """, bom_item.source_warehouse, bom_item.issue_step, bom_item.operation,
				bom_item.include_item_in_manufacturing, bom_item.description, bom_item.rate, 0 as is_scrap,
				(Select idx from `tabBOM Item` where item_code = bom_item.item_code and parent = %(parent)s limit 1) as idx""")

		items = frappe.db.sql(query, { "parent": bom, "qty": qty, "bom": bom, "company": company }, as_dict=True)
	elif fetch_scrap_items:
		query = query.format(table="BOM Scrap Item", where_conditions="",
			select_columns=", bom_item.idx, bom_item.stock_uom, 1 as is_scrap, item.description", is_stock_item=is_stock_item, qty_field="stock_qty")

		items = frappe.db.sql(query, { "qty": qty, "bom": bom, "company": company }, as_dict=True)
	else:
		query = query.format(table="BOM Item", where_conditions="", is_stock_item=is_stock_item,
			qty_field="stock_qty" if fetch_qty_in_stock_uom else "qty",
			select_columns = """, bom_item.uom, bom_item.stock_uom, bom_item.conversion_factor, bom_item.source_warehouse, 0 as is_scrap,
				bom_item.idx, bom_item.operation, bom_item.include_item_in_manufacturing,
				bom_item.description, bom_item.base_rate as rate """)
		items = frappe.db.sql(query, { "qty": qty, "bom": bom, "company": company }, as_dict=True)

	c = 1
	for item in items:
		if item.item_code in item_dict:
			item_dict[item.item_code]["qty"] += flt(item.qty)
		else:
			item_dict[item.item_code+f"{c}"] = item
		c += 1

	for item, item_details in item_dict.items():
		for d in [["Account", "expense_account", "stock_adjustment_account"],
			["Cost Center", "cost_center", "cost_center"], ["Warehouse", "default_warehouse", ""]]:
				company_in_record = frappe.db.get_value(d[0], item_details.get(d[1]), "company")
				if not item_details.get(d[1]) or (company_in_record and company != company_in_record):
					item_dict[item][d[1]] = frappe.get_cached_value('Company',  company,  d[2]) if d[2] else None

	return item_dict

def set_production_order_details(self):
	if not self.production_order:
		return
	
	if not getattr(self, "pro_doc", None):
		self.pro_doc = frappe._dict()

	if self.production_order:
		# common validations
		if not self.pro_doc:
			self.pro_doc = frappe.get_doc('Production Order', self.production_order)

		if self.pro_doc:
			self.bom_no = self.pro_doc.bom_no
		else:
			# invalid production order
			self.production_order = None
	
def get_production_order_items(self, issue_step=None):
	if not self.production_order:
		return
	
	self.set('items', [])
	self.validate_production_order()

	if not self.posting_date or not self.posting_time:
		frappe.throw(_("Posting date and posting time is mandatory"))

	self.set_production_order_details()
	self.flags.backflush_based_on = frappe.db.get_single_value("Manufacturing Settings", "backflush_raw_materials_based_on")
	
	if self.bom_no:
		if self.purpose in ["Material Issue", "Material Transfer", "Manufacture", "Repack",
				"Send to Subcontractor", "Material Transfer for Manufacture", "Material Consumption for Manufacture"]:	
			if self.production_order and self.purpose == "Material Transfer for Manufacture":
				item_dict = self.get_pending_raw_materials(for_hampden=True)
				if self.to_warehouse and self.pro_doc:
					for item in itervalues(item_dict):
						item["to_warehouse"] = self.pro_doc.wip_warehouse
						if item['is_scrap'] == 1:
							item["to_warehouse"] = self.pro_doc.scrap_warehouse
				if issue_step:
					filterd_item_dict = frappe._dict()
					for k in item_dict:
						v = item_dict.get(k, None)
						if v and  v['issue_step'] == issue_step:
							filterd_item_dict.setdefault(k, item_dict[k])
					self.add_to_stock_entry_detail(filterd_item_dict)
						
				
				else: self.add_to_stock_entry_detail(item_dict)

			elif (self.production_order and (self.purpose == "Manufacture"
					or self.purpose == "Material Consumption for Manufacture") and not self.pro_doc.skip_transfer
				and self.flags.backflush_based_on == "Material Transferred for Manufacture"):
				self.get_transfered_raw_materials()

			elif (self.production_order and (self.purpose == "Manufacture" or
				self.purpose == "Material Consumption for Manufacture") and self.flags.backflush_based_on== "BOM"
				and frappe.db.get_single_value("Manufacturing Settings", "material_consumption")== 1):
				self.get_unconsumed_raw_materials()
			else:
				if not self.fg_completed_qty:
					frappe.throw(_("Manufacturing Quantity is mandatory"))

				item_dict = self.get_bom_raw_materials(self.fg_completed_qty)

				#Get PO Supplied Items Details
				if self.purchase_order and self.purpose == "Send to Subcontractor":
					#Get PO Supplied Items Details
					item_wh = frappe._dict(frappe.db.sql("""
						select rm_item_code, reserve_warehouse
						from `tabPurchase Order` po, `tabPurchase Order Item Supplied` poitemsup
						where po.name = poitemsup.parent
							and po.name = %s""",self.purchase_order))
				po = frappe.get_doc('Production Order', self.production_order)
				c = 0
				for item in itervalues(item_dict):
					if self.pro_doc and (cint(self.pro_doc.from_wip_warehouse) or not self.pro_doc.skip_transfer):
						item["from_warehouse"] = self.pro_doc.wip_warehouse
					#Get Reserve Warehouse from PO
					if self.purchase_order and self.purpose=="Send to Subcontractor":
						item["from_warehouse"] = item_wh.get(item.item_code)
					item["to_warehouse"] = self.to_warehouse if self.purpose=="Send to Subcontractor" else ""
					item["production_order"] = self.production_order
					item["production_detail"] = po.required_items[c].name or ""
					item["transferred_qty"] = po.required_items[c].transferred_qty or 0
					
					c += 1

				self.add_to_stock_entry_detail(item_dict)

		# add finished goods item
		if self.purpose in ("Manufacture", "Repack"):
			self.load_items_from_bom()

	self.set_scrap_items()
	self.set_actual_qty()
	self.calculate_rate_and_amount(raise_error_if_no_rate=False)

def get_transfered_raw_materials(self):
	if self.work_order:
		self.erp_get_transfered_raw_materials()
	
	if self.production_order:
		self.hampden_get_transfered_raw_materials()

def hampden_get_transfered_raw_materials(self):
	# prod_ord = frappe.get_doc('Production Order', self.production_order)
	transferred_materials = frappe.db.sql("""
		select
			item_name, original_item, item_code, qty, sed.t_warehouse as warehouse, sed.is_scrap, 
			sed.production_detail,
			description, stock_uom, expense_account, cost_center
		from `tabStock Entry` se,`tabStock Entry Detail` sed
		where
			se.name = sed.parent and se.docstatus=1 and se.purpose='Material Transfer for Manufacture'
			and se.production_order= %s and ifnull(sed.t_warehouse, '') != ''
			and sed.production_order = %s
		group by sed.production_detail, sed.t_warehouse
	""", self.production_order, self.production_order, as_dict=1)

	materials_already_backflushed = frappe.db.sql("""
		select
			item_code, sed.s_warehouse as warehouse, qty, sed.is_scrap, 
			sed.production_detail, 
		from
			`tabStock Entry` se, `tabStock Entry Detail` sed
		where
			se.name = sed.parent and se.docstatus=1
			and (se.purpose='Manufacture' or se.purpose='Material Consumption for Manufacture')
			and se.production_order= %s and ifnull(sed.s_warehouse, '') != ''
			and sed.production_order = %s
		group by sed.production_detail, sed.t_warehouse
	""", self.production_order, self.production_order, as_dict=1)

	backflushed_materials= {}
	for d in materials_already_backflushed:
		backflushed_materials.setdefault(d.production_detail,[]).append({d.warehouse: d.qty})
	
	po_qty = frappe.db.sql("""select qty, produced_qty, material_transferred_for_manufacturing from
		`tabProdction Order` where name=%s""", self.production_order, as_dict=1)[0]

	manufacturing_qty = flt(po_qty.qty)
	produced_qty = flt(po_qty.produced_qty)
	trans_qty = flt(po_qty.material_transferred_for_manufacturing)

	for item in transferred_materials:
		qty= item.qty
		is_scrap = item.is_scrap
		item_code = item.original_item or item.item_code
		req_items = frappe.get_all('Work Order Item',
			filters={'parent': self.work_order, 'item_code': item_code},
			fields=["required_qty", "consumed_qty"]
		)
		if not req_items:
			frappe.msgprint(_("Did not found transfered item {0} in Work Order {1}, the item not added in Stock Entry")
				.format(item_code, self.work_order))
			continue

		req_qty = flt(req_items[0].required_qty)
		req_qty_each = flt(req_qty / manufacturing_qty)
		consumed_qty = flt(req_items[0].consumed_qty)

		if trans_qty and manufacturing_qty > (produced_qty + flt(self.fg_completed_qty)):
			if qty >= req_qty:
				qty = (req_qty/trans_qty) * flt(self.fg_completed_qty)
			else:
				qty = qty - consumed_qty

			if self.purpose == 'Manufacture':
				# If Material Consumption is booked, must pull only remaining components to finish product
				if consumed_qty != 0:
					remaining_qty = consumed_qty - (produced_qty * req_qty_each)
					exhaust_qty = req_qty_each * produced_qty
					if remaining_qty > exhaust_qty :
						if (remaining_qty/(req_qty_each * flt(self.fg_completed_qty))) >= 1:
							qty =0
						else:
							qty = (req_qty_each * flt(self.fg_completed_qty)) - remaining_qty
				else:
					if self.flags.backflush_based_on == "Material Transferred for Manufacture":
						qty = (item.qty/trans_qty) * flt(self.fg_completed_qty)
					else:
						qty = req_qty_each * flt(self.fg_completed_qty)

		elif backflushed_materials.get(item.item_code):
			for d in backflushed_materials.get(item.item_code):
				if d.get(item.warehouse):
					if (qty > req_qty):
						qty = (qty/trans_qty) * flt(self.fg_completed_qty)

					if consumed_qty and frappe.db.get_single_value("Manufacturing Settings",
						"material_consumption"):
						qty -= consumed_qty

		if cint(frappe.get_cached_value('UOM', item.stock_uom, 'must_be_whole_number')):
			qty = frappe.utils.ceil(qty)

		if qty > 0:
			self.add_to_stock_entry_detail({
				item.item_code: {
					"from_warehouse": item.warehouse,
					"to_warehouse": "",
					"qty": qty,
					"is_scrap": item.is_scrap,
					"production_detail": item.production_detail,
					"item_name": item.item_name,
					"description": item.description,
					"stock_uom": item.stock_uom,
					"expense_account": item.expense_account,
					"cost_center": item.buying_cost_center,
					"original_item": item.original_item
				}
			})

def erp_get_transfered_raw_materials(self):
	transferred_materials = frappe.db.sql("""
		select
			item_name, original_item, item_code, sum(qty) as qty, sed.t_warehouse as warehouse,
			description, stock_uom, expense_account, cost_center
		from `tabStock Entry` se,`tabStock Entry Detail` sed
		where
			se.name = sed.parent and se.docstatus=1 and se.purpose='Material Transfer for Manufacture'
			and se.work_order= %s and ifnull(sed.t_warehouse, '') != ''
		group by sed.item_code, sed.t_warehouse
	""", self.work_order, as_dict=1)

	materials_already_backflushed = frappe.db.sql("""
		select
			item_code, sed.s_warehouse as warehouse, sum(qty) as qty
		from
			`tabStock Entry` se, `tabStock Entry Detail` sed
		where
			se.name = sed.parent and se.docstatus=1
			and (se.purpose='Manufacture' or se.purpose='Material Consumption for Manufacture')
			and se.work_order= %s and ifnull(sed.s_warehouse, '') != ''
		group by sed.item_code, sed.s_warehouse
	""", self.work_order, as_dict=1)

	backflushed_materials= {}
	for d in materials_already_backflushed:
		backflushed_materials.setdefault(d.item_code,[]).append({d.warehouse: d.qty})

	po_qty = frappe.db.sql("""select qty, produced_qty, material_transferred_for_manufacturing from
		`tabWork Order` where name=%s""", self.work_order, as_dict=1)[0]

	manufacturing_qty = flt(po_qty.qty)
	produced_qty = flt(po_qty.produced_qty)
	trans_qty = flt(po_qty.material_transferred_for_manufacturing)

	for item in transferred_materials:
		qty= item.qty
		item_code = item.original_item or item.item_code
		req_items = frappe.get_all('Work Order Item',
			filters={'parent': self.work_order, 'item_code': item_code},
			fields=["required_qty", "consumed_qty"]
			)
		if not req_items:
			frappe.msgprint(_("Did not found transfered item {0} in Work Order {1}, the item not added in Stock Entry")
				.format(item_code, self.work_order))
			continue

		req_qty = flt(req_items[0].required_qty)
		req_qty_each = flt(req_qty / manufacturing_qty)
		consumed_qty = flt(req_items[0].consumed_qty)

		if trans_qty and manufacturing_qty > (produced_qty + flt(self.fg_completed_qty)):
			if qty >= req_qty:
				qty = (req_qty/trans_qty) * flt(self.fg_completed_qty)
			else:
				qty = qty - consumed_qty

			if self.purpose == 'Manufacture':
				# If Material Consumption is booked, must pull only remaining components to finish product
				if consumed_qty != 0:
					remaining_qty = consumed_qty - (produced_qty * req_qty_each)
					exhaust_qty = req_qty_each * produced_qty
					if remaining_qty > exhaust_qty :
						if (remaining_qty/(req_qty_each * flt(self.fg_completed_qty))) >= 1:
							qty =0
						else:
							qty = (req_qty_each * flt(self.fg_completed_qty)) - remaining_qty
				else:
					if self.flags.backflush_based_on == "Material Transferred for Manufacture":
						qty = (item.qty/trans_qty) * flt(self.fg_completed_qty)
					else:
						qty = req_qty_each * flt(self.fg_completed_qty)

		elif backflushed_materials.get(item.item_code):
			for d in backflushed_materials.get(item.item_code):
				if d.get(item.warehouse):
					if (qty > req_qty):
						qty = (qty/trans_qty) * flt(self.fg_completed_qty)

					if consumed_qty and frappe.db.get_single_value("Manufacturing Settings",
						"material_consumption"):
						qty -= consumed_qty

		if cint(frappe.get_cached_value('UOM', item.stock_uom, 'must_be_whole_number')):
			qty = frappe.utils.ceil(qty)

		if qty > 0:
			self.add_to_stock_entry_detail({
				item.item_code: {
					"from_warehouse": item.warehouse,
					"to_warehouse": "",
					"qty": qty,
					"item_name": item.item_name,
					"description": item.description,
					"stock_uom": item.stock_uom,
					"expense_account": item.expense_account,
					"cost_center": item.buying_cost_center,
					"original_item": item.original_item
				}
			})

def get_pro_order_required_items2(self, issue=None):
	item_dict = frappe._dict()
	pro_order = frappe.get_doc("Production Order", self.production_order)
	if not frappe.db.get_value("Warehouse", pro_order.wip_warehouse, "is_group"):
		wip_warehouse = pro_order.wip_warehouse
	else:
		wip_warehouse = None

	if not frappe.db.get_value("Warehouse", pro_order.scrap_warehouse, "is_group"):
		scrap_warehouse = pro_order.scrap_warehouse
	else:
		scrap_warehouse = None
	
	c = 1
	for d in pro_order.get("required_items"):
		if (flt(d.required_qty) > flt(d.transferred_qty) and (d.include_item_in_manufacturing or self.purpose != "Material Transfer for Manufacture")):
			item_row = d.as_dict()
			if d.source_warehouse and not frappe.db.get_value("Warehouse", d.source_warehouse, "is_group"):
				item_row["from_warehouse"] = d.source_warehouse

			item_row["to_warehouse"] = wip_warehouse
			if item_row["allow_alternative_item"]:
				item_row["allow_alternative_item"] = pro_order.allow_alternative_item
			
			item_row['is_scrap'] = 0
			item_row['idx'] = c
			item_row['issue_step'] = d.issue_step or ""
			item_row['production_order'] = pro_order.name
			item_row['production_detail'] = d.name
			
			item_dict.setdefault(f"{d.item_code}{c}", item_row)
			c += 1
	
	for d in pro_order.get("scrap_items"):
		if (flt(d.required_qty) > flt(d.transferred_qty) and (d.include_item_in_manufacturing or self.purpose != "Material Transfer for Manufacture")):
			item_row = d.as_dict()
			if d.source_warehouse and not frappe.db.get_value("Warehouse", d.source_warehouse, "is_group"):
				item_row["from_warehouse"] = d.source_warehouse
			
			item_row["to_warehouse"] = scrap_warehouse
			if item_row["allow_alternative_item"]:
				item_row["allow_alternative_item"] = pro_order.allow_alternative_item
			item_row['is_scrap'] = 1
			item_row['idx'] = c
			item_row['issue_step'] = d.issue_step or ""
			item_row['production_order'] = pro_order.name
			item_row['production_detail'] = d.name

			item_dict.setdefault(f"{d.item_code}scrp{c}", item_row)
			c += 1

	return item_dict

def get_pending_raw_materials(self, for_hampden=False):
	"""
		issue (item quantity) that is pending to issue or desire to transfer,
		whichever is less
	"""
	if for_hampden:
		item_dict = self.get_pro_order_required_items2()
	else:
		item_dict = self.get_pro_order_required_items()
	max_qty = flt(self.pro_doc.qty)

	allow_overproduction = False
	overproduction_percentage = flt(frappe.db.get_single_value("Manufacturing Settings",
		"overproduction_percentage_for_work_order"))

	to_transfer_qty = flt(self.pro_doc.material_transferred_for_manufacturing) + flt(self.fg_completed_qty)
	transfer_limit_qty = max_qty + ((max_qty * overproduction_percentage) / 100)

	if transfer_limit_qty >= to_transfer_qty:
		allow_overproduction = True

	for item, item_details in iteritems(item_dict):
		pending_to_issue = flt(item_details.required_qty) - flt(item_details.transferred_qty)
		desire_to_transfer = flt(self.fg_completed_qty) * flt(item_details.required_qty) / max_qty

		# if desire_to_transfer <= pending_to_issue or allow_overproduction:
		# 	item_dict[item]["qty"] = desire_to_transfer
		if pending_to_issue > 0:
			item_dict[item]["qty"] = pending_to_issue
		else:
			item_dict[item]["qty"] = 0

	# delete items with 0 qty
	for item in item_dict.keys():
		if not item_dict[item]["qty"]:
			del item_dict[item]

	# show some message
	if not len(item_dict):
		frappe.msgprint(_("""All items have already been transferred for this Production Order."""))

	return item_dict

def get_used_alternative_items(purchase_order=None, production_order=None):
	cond = ""

	if purchase_order:
		cond = "and ste.purpose = 'Send to Subcontractor' and ste.purchase_order = '{0}'".format(purchase_order)
	elif production_order:
		cond = "and ste.purpose = 'Material Transfer for Manufacture' and ste.production_order = '{0}'".format(production_order)

	if not cond: return {}

	used_alternative_items = {}
	data = frappe.db.sql(""" select sted.original_item, sted.uom, sted.conversion_factor,
			sted.item_code, sted.item_name, sted.conversion_factor,sted.stock_uom, sted.description
		from
			`tabStock Entry` ste, `tabStock Entry Detail` sted
		where
			sted.parent = ste.name and ste.docstatus = 1 and sted.original_item !=  sted.item_code
			{0} """.format(cond), as_dict=1)

	for d in data:
		used_alternative_items[d.original_item] = d

	return used_alternative_items

def hampden_get_bom_raw_materials(self, qty):
	# from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
	# from erpnext.stock.doctype.stock_entry.stock_entry import get_used_alternative_items
	if not self.production_order:
		return
	# item dict = { item_code: {qty, description, stock_uom} }
	item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=qty,
		fetch_exploded = self.use_multi_level_bom, fetch_qty_in_stock_uom=False)

	used_alternative_items = get_used_alternative_items(production_order = self.production_order)
	for item in itervalues(item_dict):
		# if source warehouse presents in BOM set from_warehouse as bom source_warehouse
		if item["allow_alternative_item"]:
			item["allow_alternative_item"] = frappe.db.get_value('Production Order', self.production_order, "allow_alternative_item")

		item.from_warehouse = self.from_warehouse or item.source_warehouse or item.default_warehouse
		if item.item_code in used_alternative_items:
			alternative_item_data = used_alternative_items.get(item.item_code)
			item.item_code = alternative_item_data.item_code
			item.item_name = alternative_item_data.item_name
			item.stock_uom = alternative_item_data.stock_uom
			item.uom = alternative_item_data.uom
			item.conversion_factor = alternative_item_data.conversion_factor
			item.description = alternative_item_data.description

	return item_dict

def erp_get_bom_raw_materials(self, qty):
	from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict

	# item dict = { item_code: {qty, description, stock_uom} }
	item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=qty,
		fetch_exploded = self.use_multi_level_bom, fetch_qty_in_stock_uom=False)

	used_alternative_items = get_used_alternative_items(work_order = self.work_order)
	for item in itervalues(item_dict):
		# if source warehouse presents in BOM set from_warehouse as bom source_warehouse
		if item["allow_alternative_item"]:
			item["allow_alternative_item"] = frappe.db.get_value('Work Order',
				self.work_order, "allow_alternative_item")

		item.from_warehouse = self.from_warehouse or item.source_warehouse or item.default_warehouse
		if item.item_code in used_alternative_items:
			alternative_item_data = used_alternative_items.get(item.item_code)
			item.item_code = alternative_item_data.item_code
			item.item_name = alternative_item_data.item_name
			item.stock_uom = alternative_item_data.stock_uom
			item.uom = alternative_item_data.uom
			item.conversion_factor = alternative_item_data.conversion_factor
			item.description = alternative_item_data.description

	return item_dict

def get_bom_raw_materials(self, qty):
	''' Override Stock Entry method to fetch data 
		For Production Order or use default ERP method
	'''
	if self.production_order:
		return self.hampden_get_bom_raw_materials(qty)
		
	return self.erp_get_bom_raw_materials(qty)


def hampden_get_bom_scrap_material(self, qty):
	# from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
	# item dict = { item_code: {qty, description, stock_uom} }
	item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=qty,
		fetch_exploded = 0, fetch_scrap_items = 1)

	for item in itervalues(item_dict):
		item.from_warehouse = ""
	return item_dict

def erp_get_bom_scrap_material(self, qty):
	from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict

	# item dict = { item_code: {qty, description, stock_uom} }
	item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=qty,
		fetch_exploded = 0, fetch_scrap_items = 1)

	for item in itervalues(item_dict):
		item.from_warehouse = ""
	return item_dict

def get_bom_scrap_material(self, qty):
	if self.production_order: return self.hampden_get_bom_scrap_material(qty)
	return self.erp_get_bom_scrap_material(qty)

def hampden_add_to_stock_entry_detail(self, item_dict, bom_no=None):
	for d in item_dict:
		stock_uom = item_dict[d].get("stock_uom") or frappe.db.get_value("Item", d, "stock_uom")

		se_child = self.append('items')
		se_child.s_warehouse = item_dict[d].get("from_warehouse")
		se_child.t_warehouse = item_dict[d].get("to_warehouse")
		se_child.item_code = item_dict[d].get('item_code') or cstr(d)
		se_child.issue_step = item_dict[d].get('issue_step')
		se_child.is_scrap = item_dict[d].get('is_scrap') or 0
		se_child.production_order = item_dict[d].get('production_order')
		se_child.production_detail = item_dict[d].get('production_detail')
		se_child.uom = item_dict[d]["uom"] if item_dict[d].get("uom") else stock_uom
		se_child.stock_uom = stock_uom
		se_child.qty = flt(item_dict[d]["qty"], se_child.precision("qty"))
		se_child.allow_alternative_item = item_dict[d].get("allow_alternative_item", 0)
		se_child.subcontracted_item = item_dict[d].get("main_item_code")
		se_child.cost_center = (item_dict[d].get("cost_center") or
			get_default_cost_center(item_dict[d], company = self.company))

		for field in ["idx", "po_detail", "original_item",
			"expense_account", "description", "item_name"]:
			if item_dict[d].get(field):
				se_child.set(field, item_dict[d].get(field))

		if se_child.s_warehouse==None:
			se_child.s_warehouse = self.from_warehouse
		if se_child.t_warehouse==None:
			se_child.t_warehouse = self.to_warehouse

		# in stock uom
		se_child.conversion_factor = flt(item_dict[d].get("conversion_factor")) or 1
		se_child.transfer_qty = flt(item_dict[d]["qty"]*se_child.conversion_factor, se_child.precision("qty"))


		# to be assigned for finished item
		se_child.bom_no = bom_no

def erp_add_to_stock_entry_detail(self, item_dict, bom_no=None):
	for d in item_dict:
		stock_uom = item_dict[d].get("stock_uom") or frappe.db.get_value("Item", d, "stock_uom")

		se_child = self.append('items')
		se_child.s_warehouse = item_dict[d].get("from_warehouse")
		se_child.t_warehouse = item_dict[d].get("to_warehouse")
		se_child.item_code = item_dict[d].get('item_code') or cstr(d)
		se_child.uom = item_dict[d]["uom"] if item_dict[d].get("uom") else stock_uom
		se_child.stock_uom = stock_uom
		se_child.qty = flt(item_dict[d]["qty"], se_child.precision("qty"))
		se_child.allow_alternative_item = item_dict[d].get("allow_alternative_item", 0)
		se_child.subcontracted_item = item_dict[d].get("main_item_code")
		se_child.cost_center = (item_dict[d].get("cost_center") or
			get_default_cost_center(item_dict[d], company = self.company))

		for field in ["idx", "po_detail", "original_item",
			"expense_account", "description", "item_name"]:
			if item_dict[d].get(field):
				se_child.set(field, item_dict[d].get(field))

		if se_child.s_warehouse==None:
			se_child.s_warehouse = self.from_warehouse
		if se_child.t_warehouse==None:
			se_child.t_warehouse = self.to_warehouse

		# in stock uom
		se_child.conversion_factor = flt(item_dict[d].get("conversion_factor")) or 1
		se_child.transfer_qty = flt(item_dict[d]["qty"]*se_child.conversion_factor, se_child.precision("qty"))


		# to be assigned for finished item
		se_child.bom_no = bom_no

def add_to_stock_entry_detail(self, item_dict, bom_no=None):
	if self.production_order: self.hampden_add_to_stock_entry_detail(item_dict, bom_no=bom_no)
	else: self.erp_add_to_stock_entry_detail(item_dict, bom_no=bom_no)

# Stock Entry 
StockEntry.validate_production_order = validate_production_order
StockEntry.check_if_production_operations_completed = check_if_production_operations_completed
StockEntry.check_duplicate_entry_for_production_order = check_duplicate_entry_for_production_order
StockEntry.validate_finished_goods_in_production_order = validate_finished_goods_in_production_order
StockEntry.update_production_order = update_production_order
StockEntry.update_so_in_serial_number_for_production = update_so_in_serial_number_for_production
StockEntry.get_production_order_items = get_production_order_items
StockEntry.set_production_order_details = set_production_order_details
StockEntry.get_pro_order_required_items2 = get_pro_order_required_items2
StockEntry.get_pending_raw_materials = get_pending_raw_materials

StockEntry.erp_get_transfered_raw_materials = erp_get_transfered_raw_materials
StockEntry.hampden_get_transfered_raw_materials = hampden_get_transfered_raw_materials
StockEntry.get_transfered_raw_materials = get_transfered_raw_materials


StockEntry.erp_get_bom_raw_materials = erp_get_bom_raw_materials
StockEntry.hampden_get_bom_raw_materials = hampden_get_bom_raw_materials
StockEntry.get_bom_raw_materials = get_bom_raw_materials

StockEntry.hampden_add_to_stock_entry_detail = hampden_add_to_stock_entry_detail
StockEntry.erp_add_to_stock_entry_detail = erp_add_to_stock_entry_detail
StockEntry.add_to_stock_entry_detail = add_to_stock_entry_detail

StockEntry.erp_get_bom_scrap_material = erp_get_bom_scrap_material
StockEntry.hampden_get_bom_scrap_material = hampden_get_bom_scrap_material
StockEntry.get_bom_scrap_material = get_bom_scrap_material

# #Overwrite Method in BOM

# from erpnext.manufacturing.doctype.bom.bom import BOM

# def get_exploded_items(self):
# 	""" Get all raw materials including items from child bom"""
# 	self.cur_exploded_items = {}
# 	for d in self.get('items'):
# 		if d.bom_no:
# 			self.get_child_exploded_items(d.bom_no, d.stock_qty)
# 		else:
# 			self.add_to_cur_exploded_items(frappe._dict({
# 				'item_code'			: d.item_code,
# 				'item_name'			: d.item_name,
# 				'issue_step'		: d.issue_step,
# 				'operation'			: d.operation,
# 				'source_warehouse'  : d.source_warehouse,
# 				'description'		: d.description,
# 				'image'				: d.image,
# 				'stock_uom'			: d.stock_uom,
# 				'stock_qty'			: flt(d.stock_qty),
# 				'rate'				: flt(d.base_rate) / (flt(d.conversion_factor) or 1.0),
# 				'include_item_in_manufacturing': d.include_item_in_manufacturing
# 			}))
			

# def get_child_exploded_items(self, bom_no, stock_qty):
# 	""" Add all items from Flat BOM of child BOM"""
# 	# Did not use qty_consumed_per_unit in the query, as it leads to rounding loss
# 	child_fb_items = frappe.db.sql("""
# 		SELECT
# 			bom_item.item_code,
# 			bom_item.item_name,
# 			bom_item.issue_step,
# 			bom_item.description,
# 			bom_item.source_warehouse,
# 			bom_item.operation,
# 			bom_item.stock_uom,
# 			bom_item.stock_qty,
# 			bom_item.rate,
# 			bom_item.include_item_in_manufacturing,
# 			bom_item.stock_qty / ifnull(bom.quantity, 1) AS qty_consumed_per_unit
# 		FROM `tabBOM Explosion Item` bom_item, tabBOM bom
# 		WHERE
# 			bom_item.parent = bom.name
# 			AND bom.name = %s
# 			AND bom.docstatus = 1
# 	""", bom_no, as_dict = 1)

# 	for d in child_fb_items:
# 		self.add_to_cur_exploded_items(frappe._dict({
# 			'item_code'				: d['item_code'],
# 			'item_name'				: d['item_name'],
# 			'issue_step'			: d['issue_step'],
# 			'source_warehouse'		: d['source_warehouse'],
# 			'operation'				: d['operation'],
# 			'description'			: d['description'],
# 			'stock_uom'				: d['stock_uom'],
# 			'stock_qty'				: d['qty_consumed_per_unit'] * stock_qty,
# 			'rate'					: flt(d['rate']),
# 			'include_item_in_manufacturing': d.get('include_item_in_manufacturing', 0)
# 		}))

# def add_to_cur_exploded_items(self, args):
# 	key = '{}{}'.format(args.item_code or '', args.issue_step or '')
# 	if self.cur_exploded_items.get(key):
# 		self.cur_exploded_items[key]["stock_qty"] += args.stock_qty
# 	else:
# 		self.cur_exploded_items[key] = args

# BOM.get_exploded_items = get_exploded_items
# BOM.get_child_exploded_items = get_child_exploded_items
# BOM.add_to_cur_exploded_items = add_to_cur_exploded_items
