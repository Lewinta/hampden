# -*- coding: utf-8 -*-
# Copyright (c) 2021, ahmadragheb and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from six import string_types
import frappe
import json
import math
from frappe import _
from frappe.utils import flt, get_datetime, getdate, date_diff, cint, nowdate, get_link_to_form
from frappe.model.document import Document
from erpnext.manufacturing.doctype.bom.bom import validate_bom_no
from dateutil.relativedelta import relativedelta
from erpnext.stock.doctype.item.item import validate_end_of_life
from erpnext.manufacturing.doctype.workstation.workstation import WorkstationHolidayError
from erpnext.projects.doctype.timesheet.timesheet import OverlapError
from erpnext.manufacturing.doctype.manufacturing_settings.manufacturing_settings import get_mins_between_operations
from erpnext.stock.stock_balance import get_planned_qty, update_bin_qty
from frappe.utils.csvutils import getlink
from erpnext.stock.utils import get_bin, validate_warehouse_company, get_latest_stock_qty
from erpnext.utilities.transaction_base import validate_uom_is_integer
from frappe.model.mapper import get_mapped_doc


class OverProductionError(frappe.ValidationError):
    pass


class StockOverProductionError(frappe.ValidationError):
    pass


class OperationTooLongError(frappe.ValidationError):
    pass


class ItemHasVariantError(frappe.ValidationError):
    pass


form_grid_templates = {
    "operations": "templates/form_grid/work_order_grid.html"
}


class ProductionOrder(Document):
    def onload(self):
        ms = frappe.get_doc("Manufacturing Settings")
        self.set_onload("material_consumption", ms.material_consumption)
        self.set_onload("backflush_raw_materials_based_on",
                        ms.backflush_raw_materials_based_on)
        self.set_onload("overproduction_percentage",
                        ms.overproduction_percentage_for_work_order)

    def validate(self):
        self.validate_production_item()
        if self.bom_no:
            validate_bom_no(self.production_item, self.bom_no)

        self.validate_sales_order()
        self.set_default_warehouse()
        self.validate_warehouse_belongs_to_company()
        self.calculate_operating_cost()
        self.validate_qty()
        self.validate_operation_time()
        self.status = self.get_status()

        validate_uom_is_integer(self, "stock_uom", ["qty", "produced_qty"])

        self.set_required_items(reset_only_qty=len(self.get("required_items")))
        self.set_scrap_items(reset_only_qty=len(self.get("required_items")))
    
    def set_production_steps(self):
        self.production_steps = []
        if self.production_item:
            item = frappe.get_doc('Item', self.production_item)
            for step in item.production_item_table:
                self.append('production_steps',{
                    'production_step': step.production_step,
                    # 'labor': step.labor,
                    'issue_step': step.issue_step,
                    # 'overhead': step.overhead
                })


    def validate_sales_order(self):
        if self.sales_order:
            self.check_sales_order_on_hold_or_close()
            so = frappe.db.sql("""
                select so.name, so_item.delivery_date, so.project
                from `tabSales Order` so
                inner join `tabSales Order Item` so_item on so_item.parent = so.name
                left join `tabProduct Bundle Item` pk_item on so_item.item_code = pk_item.parent
                where so.name=%s and so.docstatus = 1
                	and so.skip_delivery_note  = 0 and (
                	so_item.item_code=%s or
                	pk_item.item_code=%s )
        	""", (self.sales_order, self.production_item, self.production_item), as_dict=1)

            if not so:
                so = frappe.db.sql("""
                	select
                        so.name, so_item.delivery_date, so.project
                	from
                        `tabSales Order` so, `tabSales Order Item` so_item, `tabPacked Item` packed_item
                	where so.name=%s
                        and so.name=so_item.parent
                        and so.name=packed_item.parent
                        and so.skip_delivery_note = 0
                        and so_item.item_code = packed_item.parent_item
                        and so.docstatus = 1 and packed_item.item_code=%s
                """, (self.sales_order, self.production_item), as_dict=1)

            if len(so):
                if not self.expected_delivery_date:
                    self.expected_delivery_date = so[0].delivery_date

                if so[0].project:
                    self.project = so[0].project

                if not self.material_request:
                    self.validate_production_order_against_so()
            else:
                frappe.throw(
                    _("Sales Order {0} is not valid").format(self.sales_order))

    def check_sales_order_on_hold_or_close(self):
        status = frappe.db.get_value("Sales Order", self.sales_order, "status")
        if status in ("Closed", "On Hold"):
            frappe.throw(_("Sales Order {0} is {1}").format(
                self.sales_order, status))
    def update_last_step(self):
        row = -1
        for r in self.production_steps:
            if r.date:
                row += 1
        self.db_set('last_step', row)
    
    def validate_updated_row(self, row):
        pass
    
    @frappe.whitelist()
    def reset_production_step(self, row):
        if self.docstatus != 1:
            frappe.throw('Please Submit Order before Update the Step!')

        # if last updated step idx is eqaul current updated row
        # if row <= int(self.last_step): return 'RELOAD'
        
        # check row idx
        
        if row > len(self.production_steps):
            frappe.throw('Invlaid Step to update')
        
        has_issue_stock = False
        for i in range(row-1, len(self.production_steps)):
            print(i)
            step_row = self.production_steps[i]
            if not step_row.date:
                continue
            if step_row.issue_step:
                stocks = frappe.get_list('Stock Entry', filters={'stock_entry_type': 'Material Transfer for Manufacture', 'production_order': self.name, 'issue_step': step_row.issue_step, 'docstatus':1})
                for stock in stocks:
                    has_issue_stock = True
                    frappe.get_doc('Stock Entry', stock.name).cancel()
                

            step_row.db_set('date', None, update_modified=False)
            step_row.db_set('completed_by', '', update_modified=False)
        if has_issue_stock:
            stocks = frappe.get_list('Stock Entry', filters={'stock_entry_type': 'Manufacture', 'production_order': self.name, 'docstatus':1})
            for stock in stocks:
                frappe.get_doc('Stock Entry', stock.name).cancel()
        
        frappe.db.commit()

    @frappe.whitelist()
    def update_production_step(self, row, from_batch=False):
        # Check Order Status
         
        if self.docstatus != 1:
            frappe.throw('Please Submit Order before Update the Step!')
        
        date = frappe.utils.nowdate()

        # if last updated step idx is eqaul current updated row
        if row <= int(self.last_step): return 'RELOAD'
        
        # check row idx
        
        if row > len(self.production_steps):
            frappe.throw('Invlaid Step to update')
        
        # if last step just finish the order
        finish_order = row == len(self.production_steps)

        # Get All Steps to create stock entries
        stock_entries_steps = set()
        for i in range(0, cint(row)):
            step = self.production_steps[i]
            if not step.date and step.issue_step:
                stock_entries_steps.add(step.issue_step)
        
        if stock_entries_steps:
            for step in stock_entries_steps:
                stock_dict = self.transfer_items(step)
                if len(stock_dict.get('items', [])) == 0: return 'RELOAD'
                stock = frappe.new_doc('Stock Entry')
                stock.update(stock_dict)
                stock.save()
                stock.submit()
        
        if finish_order:
            stock_dict = self.finish_order()
            if len(stock_dict.get('items', [])) == 0: return 'RELOAD'
            stock = frappe.new_doc('Stock Entry')
            stock.update(stock_dict)

            for idx, item in enumerate(stock.items):
                if item.item_code == self.production_item:
                    item.is_finished_item = 1
                if item.is_scrap == 1:
                    del stock.items[idx]
            stock.save()
            stock.submit()
            
            self.db_set('produced_qty', '100')
            self.create_jv()
            self.update_last_step()
        
        for i in range(0, cint(row)):
            step = self.production_steps[i]
            if not step.date:
                step.db_set('date', nowdate())
                pl = frappe.new_doc('Production Ledger')
                pl.production_order = self.name
                pl.customer_order = self.sales_order
                # pl.production_status = self.status
                pl.item_to_manufacture = self.production_item
                
                current_step = self.production_steps[i].production_step
                if i+1 >= len(self.production_steps):
                    next_step = ''
                else:
                    next_step = self.production_steps[i+1].production_step
                
                pl.last_finished_step = current_step
                pl.step_idx = self.production_steps[i].idx
                pl.finished_at = nowdate()
                pl.finished_by = frappe.session.user
                pl.next_production_step = next_step
                
                pl.save()
            if not step.completed_by:
                step.db_set('completed_by', frappe.session.user)
        
            
        return 'RELOAD'

    def finish_order(self):
        if self.get_status() == "Completed":
            return
        return make_stock_entry(self.name, "Manufacture", qty=(self.qty or 1))

    def finish_order_by_user(self):
        settings = frappe.get_doc('Hampden Settings', 'Hampden Settings')
        stock_dict = self.finish_order()
        if len(stock_dict.get('items', [])) == 0: return 'RELOAD'
        stock = frappe.new_doc('Stock Entry')
        stock.update(stock_dict)
        for idx, item in enumerate(stock.items):
            if item.is_scrap == 1:
                del stock.items[idx]
        if settings.auto_finsh:
            stock.save()
            stock.submit()
            self.update_last_step()
            return 'RELOAD'
        else:
            return stock

    def transfer_items(self, issue_step):

        if self.get_status() == "Completed":
            return
        return make_stock_entry(self.name, "Material Transfer for Manufacture", issue=issue_step, qty=(self.qty or 1))
        # for item in stock_entry.items:
        # 	if item.

    def set_default_warehouse(self):
        if not self.wip_warehouse:
            self.wip_warehouse = frappe.db.get_single_value(
                "Hampden Settings", "wip_warehouse")
        if not self.fg_warehouse:
            self.fg_warehouse = frappe.db.get_single_value(
                "Hampden Settings", "target_warehouse")
        if not self.scrap_warehouse:
            self.scrap_warehouse = frappe.db.get_single_value(
                "Hampden Settings", "scrap_warehouse")

    def validate_warehouse_belongs_to_company(self):
        warehouses = [self.fg_warehouse, self.wip_warehouse]
        for d in self.get("required_items"):
            if d.source_warehouse not in warehouses:
                warehouses.append(d.source_warehouse)

        for d in self.get("scrap_items"):
            if d.source_warehouse not in warehouses:
                warehouses.append(d.source_warehouse)

        for wh in warehouses:
            validate_warehouse_company(wh, self.company)

    def calculate_operating_cost(self):
        self.planned_operating_cost, self.actual_operating_cost = 0.0, 0.0
        for d in self.get("operations"):
            d.planned_operating_cost = flt(
                d.hour_rate) * (flt(d.time_in_mins) / 60.0)
            d.actual_operating_cost = flt(
                d.hour_rate) * (flt(d.actual_operation_time) / 60.0)

            self.planned_operating_cost += flt(d.planned_operating_cost)
            self.actual_operating_cost += flt(d.actual_operating_cost)

        variable_cost = self.actual_operating_cost if self.actual_operating_cost \
            else self.planned_operating_cost
        self.total_operating_cost = flt(
            self.additional_operating_cost) + flt(variable_cost)

    def validate_production_order_against_so(self):
        # already ordered qty
        ordered_qty_against_so = frappe.db.sql("""select sum(qty) from `tabProduction Order`
        	where production_item = %s and sales_order = %s and docstatus < 2 and name != %s""",
                                               (self.production_item, self.sales_order, self.name))[0][0]

        total_qty = flt(ordered_qty_against_so) + flt(self.qty)

        # get qty from Sales Order Item table
        so_item_qty = frappe.db.sql("""select sum(stock_qty) from `tabSales Order Item`
        	where parent = %s and item_code = %s""",
                                    (self.sales_order, self.production_item))[0][0]
        # get qty from Packing Item table
        dnpi_qty = frappe.db.sql("""select sum(qty) from `tabPacked Item`
        	where parent = %s and parenttype = 'Sales Order' and item_code = %s""",
                                 (self.sales_order, self.production_item))[0][0]
        # total qty in SO
        so_qty = flt(so_item_qty) + flt(dnpi_qty)

        allowance_percentage = flt(frappe.db.get_single_value("Manufacturing Settings",
                                                              "overproduction_percentage_for_sales_order"))

        settings = frappe.get_doc('Hampden Settings', 'Hampden Settings')
        if settings.multi_prod_order == 0:
            if total_qty > so_qty + (allowance_percentage/100 * so_qty):
                frappe.throw(_("Cannot produce more Item {0} than Sales Order quantity {1}")
                            .format(self.production_item, so_qty), OverProductionError)

    def update_status(self, status=None):
        '''Update status of Production Order if unknown'''
        if status != "Stopped":
            status = self.get_status(status)

        if status != self.status:
            self.db_set("status", status)

        self.update_required_items()

        return status

    def get_status(self, status=None):
        '''Return the status based on stock entries against this Production Order'''
        if not status:
            status = self.status

        if self.docstatus == 0:
            status = 'Draft'
        elif self.docstatus == 1:
            if status != 'Stopped':
                stock_entries = frappe._dict(frappe.db.sql("""select purpose, sum(fg_completed_qty)
                	from `tabStock Entry` where production_order=%s and docstatus=1
                	group by purpose""", self.name))

                status = "Not Started"
                if stock_entries:
                    status = "In Process"
                    produced_qty = stock_entries.get("Manufacture")
                    if flt(produced_qty) >= flt(self.qty):
                        status = "Completed"
        else:
            status = 'Cancelled'

        return status

    def update_production_order_trans_qty(self):
        total_reqd = 0
        
        total_trns = 0
        total_cons = 0
        
        for item in self.required_items:
            total_reqd += item.required_qty
            total_trns += item.transferred_qty
            total_cons += item.consumed_qty

        for item in self.scrap_items:
            total_reqd += item.required_qty
            total_trns += item.transferred_qty
            # total_cons += item.consumed_qty
        if total_reqd == 0:
            trans_qty_percent = 0
            consu_qty_percent = 0
        else:
            trans_qty_percent = total_trns * 100 / total_reqd
            consu_qty_percent = total_cons * 100 / total_reqd
        self.db_set('material_transferred_for_manufacturing', trans_qty_percent)
        self.db_set('produced_qty', consu_qty_percent)

    def update_production_order_qty(self):
        """Update **Manufactured Qty** and **Material Transferred for Qty** in Production Order
                based on Stock Entry"""
        self.update_production_order_trans_qty()
        self.update_required_items()

    def update_production_plan_status(self):
        production_plan = frappe.get_doc(
            'Production Plan', self.production_plan)
        produced_qty = 0
        if self.production_plan_item:
            total_qty = frappe.get_all("Production Order", fields="sum(produced_qty) as produced_qty",
                                       filters={'docstatus': 1, 'production_plan': self.production_plan,
                                                'production_plan_item': self.production_plan_item}, as_list=1)

            produced_qty = total_qty[0][0] if total_qty else 0

        production_plan.run_method(
            "update_produced_qty", produced_qty, self.production_plan_item)

    def on_submit(self):
        if not self.wip_warehouse:
            frappe.throw(
                _("Work-in-Progress Warehouse is required before Submit"))
        if not self.fg_warehouse:
            frappe.throw(_("For Warehouse is required before Submit"))

        self.update_production_order_qty_in_so()
        self.update_reserved_qty_for_production()
        self.update_completed_qty_in_material_request()
        self.update_planned_qty()
        self.update_ordered_qty()
        self.create_job_card()

    def on_cancel(self):
        self.validate_cancel()

        frappe.db.set(self, 'status', 'Cancelled')
        self.update_production_order_qty_in_so()
        self.delete_job_card()
        self.update_completed_qty_in_material_request()
        self.update_planned_qty()
        self.update_ordered_qty()
        self.update_reserved_qty_for_production()

    def create_job_card(self):
        for row in self.operations:
            if not row.workstation:
                frappe.throw(_("Row {0}: select the workstation against the operation {1}")
                             .format(row.idx, row.operation))

            create_job_card(self, row, auto_create=True)

    def validate_cancel(self):
        if self.status == "Stopped":
            frappe.throw(
                _("Stopped Production Order cannot be cancelled, Unstop it first to cancel"))

        # Check whether any stock entry exists against this Production Order
        stock_entry = frappe.db.sql("""select name from `tabStock Entry`
        	where production_order = %s and docstatus = 1""", self.name)
        if stock_entry:
            frappe.throw(_("Cannot cancel because submitted Stock Entry {0} exists").format(
                frappe.utils.get_link_to_form('Stock Entry', stock_entry[0][0])))

    def update_planned_qty(self):
        update_bin_qty(self.production_item, self.fg_warehouse, {
            "planned_qty": get_planned_qty(self.production_item, self.fg_warehouse)
        })

        if self.material_request:
            mr_obj = frappe.get_doc("Material Request", self.material_request)
            mr_obj.update_requested_qty([self.material_request_item])

    def update_ordered_qty(self):
        if self.production_plan and self.production_plan_item:
            qty = self.qty if self.docstatus == 1 else 0
            frappe.db.set_value('Production Plan Item',
                                self.production_plan_item, 'ordered_qty', qty)

            doc = frappe.get_doc('Production Plan', self.production_plan)
            doc.set_status()
            doc.db_set('status', doc.status)

    def update_production_order_qty_in_so(self):
        if not self.sales_order and not self.sales_order_item:
            return

        total_bundle_qty = 1
        if self.product_bundle_item:
            total_bundle_qty = frappe.db.sql(""" select sum(qty) from
                `tabProduct Bundle Item` where parent = %s""", (frappe.db.escape(self.product_bundle_item)))[0][0]

            if not total_bundle_qty:
                # product bundle is 0 (product bundle allows 0 qty for items)
                total_bundle_qty = 1

        cond = "product_bundle_item = %s" if self.product_bundle_item else "production_item = %s"

        qty = frappe.db.sql(""" select sum(qty) from
        	`tabProduction Order` where sales_order = %s and docstatus = 1 and {0}
        	""".format(cond), (self.sales_order, (self.product_bundle_item or self.production_item)), as_list=1)

        work_order_qty = qty[0][0] if qty and qty[0][0] else 0
        frappe.db.set_value('Sales Order Item',
                            self.sales_order_item, 'work_order_qty', flt(work_order_qty/total_bundle_qty, 2))

    def update_completed_qty_in_material_request(self):
        if self.material_request:
            frappe.get_doc("Material Request", self.material_request).update_completed_qty(
                [self.material_request_item])

    def set_work_order_operations(self):
        """Fetch operations from BOM and set in 'Production Order'"""
        self.set('operations', [])

        if not self.bom_no \
                or cint(frappe.db.get_single_value("Manufacturing Settings", "disable_capacity_planning")):
            return

        if self.use_multi_level_bom:
            bom_list = frappe.get_doc("BOM", self.bom_no).traverse_tree()
        else:
            bom_list = [self.bom_no]

        operations = frappe.db.sql("""
        	select
                operation, description, workstation, idx,
                base_hour_rate as hour_rate, time_in_mins,
                "Pending" as status, parent as bom, batch_size
        	from
                `tabBOM Operation`
        	where
                 parent in (%s) order by idx
        """ % ", ".join(["%s"]*len(bom_list)), tuple(bom_list), as_dict=1)

        self.set('operations', operations)

        if self.use_multi_level_bom and self.get('operations') and self.get('items'):
            raw_material_operations = [d.operation for d in self.get('items')]
            operations = [d.operation for d in self.get('operations')]

            for operation in raw_material_operations:
                if operation not in operations:
                    self.append('operations', {
                        'operation': operation
                    })

        self.calculate_time()

    def calculate_time(self):
        bom_qty = frappe.db.get_value("BOM", self.bom_no, "quantity")

        for d in self.get("operations"):
            d.time_in_mins = flt(d.time_in_mins) / flt(bom_qty) * \
                (flt(self.qty) / flt(d.batch_size))

        self.calculate_operating_cost()

    def get_holidays(self, workstation):
        holiday_list = frappe.db.get_value(
            "Workstation", workstation, "holiday_list")

        holidays = {}

        if holiday_list not in holidays:
            holiday_list_days = [getdate(d[0]) for d in frappe.get_all("Holiday", fields=["holiday_date"],
                                                                       filters={"parent": holiday_list}, order_by="holiday_date", limit_page_length=0, as_list=1)]

            holidays[holiday_list] = holiday_list_days

        return holidays[holiday_list]

    def update_operation_status(self):
        allowance_percentage = flt(frappe.db.get_single_value(
            "Manufacturing Settings", "overproduction_percentage_for_work_order"))
        max_allowed_qty_for_wo = flt(
            self.qty) + (allowance_percentage/100 * flt(self.qty))

        for d in self.get("operations"):
            if not d.completed_qty:
                d.status = "Pending"
            elif flt(d.completed_qty) < flt(self.qty):
                d.status = "Work in Progress"
            elif flt(d.completed_qty) == flt(self.qty):
                d.status = "Completed"
            elif flt(d.completed_qty) <= max_allowed_qty_for_wo:
                d.status = "Completed"
            else:
                frappe.throw(
                    _("Completed Qty can not be greater than 'Qty to Manufacture'"))

    def set_actual_dates(self):
        self.actual_start_date = None
        self.actual_end_date = None
        if self.get("operations"):
            actual_start_dates = [d.actual_start_time for d in self.get(
                "operations") if d.actual_start_time]
            if actual_start_dates:
                self.actual_start_date = min(actual_start_dates)

            actual_end_dates = [d.actual_end_time for d in self.get(
                "operations") if d.actual_end_time]
            if actual_end_dates:
                self.actual_end_date = max(actual_end_dates)

    def delete_job_card(self):
        for d in frappe.get_all("Job Card", ["name"], {"work_order": self.name}):
            frappe.delete_doc("Job Card", d.name)

    def validate_production_item(self):
        if frappe.db.get_value("Item", self.production_item, "has_variants"):
            frappe.throw(
                _("Production Order cannot be raised against a Item Template"), ItemHasVariantError)

        if self.production_item:
            validate_end_of_life(self.production_item)

    def validate_qty(self):
        if not self.qty > 0:
            frappe.throw(_("Quantity to Manufacture must be greater than 0."))

    def validate_operation_time(self):
        for d in self.operations:
            if not d.time_in_mins > 0:
                frappe.throw(
                    _("Operation Time must be greater than 0 for Operation {0}".format(d.operation)))

    def update_required_items(self):
        '''
        update bin reserved_qty_for_production
        called from Stock Entry for production, after submit, cancel
        '''
        # calculate consumed qty based on submitted stock entries
        # self.update_consumed_qty_for_required_items()

        if self.docstatus == 1:
            # calculate transferred qty based on submitted stock entries
            self.update_transaferred_qty_for_required_items()
            self.update_consumed_qty_for_required_items()

            # update in bin
            self.update_reserved_qty_for_production()

    def create_jv_by_user(self):
        jv = self.create_jv()
        return "RELOAD"

    def create_sales_invoice(self):
        if not self.sales_order:
            frappe.throw('Sales Order is requierd to make sales invoice')
        sales_order = frappe.get_doc('Sales Order', self.sales_order)
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
        
        if sales_order.docstatus != 1:
            frappe.throw('Sales Order must be submitted')

        sinv = frappe.new_doc('Sales Invoice')
        order_as_dict = sales_order.as_dict()
        del order_as_dict['doctype']
        del order_as_dict['name']
        del order_as_dict['owner']
        del order_as_dict['modified']
        del order_as_dict['docstatus']
        del order_as_dict['status']
        del order_as_dict['creation']
        del order_as_dict['items']
        del order_as_dict['payment_schedule']

        sinv.update(order_as_dict)
        sinv.update({'due_date': sinv.posting_date})

        sinv.production_invoice = 1
        sinv.production_order = self.name
        cost_center = frappe.get_value('Company', sinv.company, 'cost_center')
        account = frappe.get_value(
            'Company', sinv.company, 'default_income_account')
        from erpnext.stock.get_item_details import get_item_details
        # out = get_item_details(args, doc=doc, for_validate=False, overwrite_warehouse=True)
        row = sinv.append('items', {
            'item_code': self.production_item,
            'qty': self.qty,
            'item_name': self.item_name,
            'description': self.description,
            'uom': self.stock_uom,
            'cost_center': cost_center,
            'income_account': account,
			'rate': self.raw_material_cost,
            'base_rate': self.raw_material_cost,
            'price_list_rate': self.raw_material_cost,
            'base_price_list_rate': self.raw_material_cost,
        })

        sinv.save()
        
        return sinv

    def create_sales_invoice_with_customer(self, customer):
        sinv = frappe.new_doc('Sales Invoice')
        sinv.update({'due_date': sinv.posting_date})

        sinv.production_invoice = 1
        sinv.production_order = self.name
        sinv.customer = customer
        cost_center = frappe.get_value('Company', sinv.company, 'cost_center')
        account = frappe.get_value(
            'Company', sinv.company, 'default_income_account')
        row = sinv.append('items', {
            'item_code': self.production_item,
            'qty': self.qty,
            'item_name': self.item_name,
            'description': self.description,
            'uom': self.stock_uom,
            'cost_center': cost_center,
            'income_account': account,
			'rate': self.raw_material_cost,
			'base_rate': self.raw_material_cost,
			'price_list_rate': self.raw_material_cost,
			'base_price_list_rate': self.raw_material_cost,
        })
        sinv.save()

        return sinv.name

    def create_jv(self):
        if self.docstatus == 1:
            from frappe.utils import nowdate
            settings = frappe.get_doc('Hampden Settings', 'Hampden Settings')

            if not settings.auto_jv:
                return

            journal_entry = frappe.new_doc('Journal Entry')
            journal_entry.voucher_type = 'Journal Entry'
            journal_entry.user_remark = _(
                'Accrual Journal Entry for production order {0}') .format(self.name)
            journal_entry.company = self.company
            journal_entry.posting_date = nowdate()

            journal_entry.append('accounts', {
                'account': settings.labor_account,
                'debit_in_account_currency': flt(self.total_labor),
                'reference_type': 'Production Order',
                'reference_name': self.name,
            })
            journal_entry.append('accounts', {
                'account': settings.overhead_account,
                'debit_in_account_currency': flt(self.total_overhead),
                'reference_type': 'Production Order',
                'reference_name': self.name,
            })

            journal_entry.append('accounts', {
                'account': settings.creditor_account,
                'credit_in_account_currency': flt(self.total_overhead)+flt(self.total_labor),
            })

            journal_entry.save()
            journal_entry.submit()

            # Update Price List For the item
            self.insert_item_price()
            return journal_entry

        return False

    def insert_item_price(self):
        settings = frappe.get_doc('Hampden Settings', 'Hampden Settings')
        if not settings.auto_item_price:
            return

        """Insert Item Price if Price List and Price List Rate are specified and currency is the same"""
        if frappe.db.get_value("Price List", settings.default_price_list, "currency", cache=True) == settings.default_currency:
            if frappe.has_permission("Item Price", "write"):
                price_list_rate = flt(self.raw_material_cost) or 0

                item_price = frappe.db.get_value('Item Price',
                                                 {'item_code': self.production_item, 'price_list': settings.default_price_list,
                                                     'currency': settings.default_currency},
                                                 ['name', 'price_list_rate'], as_dict=1)
                if item_price and item_price.name and price_list_rate:
                    if item_price.price_list_rate != price_list_rate:
                        frappe.db.set_value(
                            'Item Price', item_price.name, "price_list_rate", price_list_rate)
                else:
                    item_price = frappe.get_doc({
                        "doctype": "Item Price",
                        "price_list": settings.default_price_list,
                        "item_code": self.production_item,
                        "currency": settings.default_currency,
                        "price_list_rate": price_list_rate
                    })
                    item_price.insert()

    def update_reserved_qty_for_production(self, items=None):
        '''update reserved_qty_for_production in bins'''
        for d in self.required_items:
            if d.source_warehouse:
                stock_bin = get_bin(d.item_code, d.source_warehouse)
                stock_bin.update_reserved_qty_for_production()

    def get_items_and_operations_from_bom(self):
        self.set_required_items()
        self.set_scrap_items()
        self.set_work_order_operations()

        return check_if_scrap_warehouse_mandatory(self.bom_no)

    def set_available_qty(self):
        for d in self.get("required_items"):
            if d.source_warehouse:
                d.available_qty_at_source_warehouse = get_latest_stock_qty(
                    d.item_code, d.source_warehouse)

            if self.wip_warehouse:
                d.available_qty_at_wip_warehouse = get_latest_stock_qty(
                    d.item_code, self.wip_warehouse)

        for d in self.get("scrap_items"):
            if d.source_warehouse:
                d.available_qty_at_source_warehouse = get_latest_stock_qty(
                    d.item_code, d.source_warehouse)

            if self.wip_warehouse:
                d.available_qty_at_wip_warehouse = get_latest_stock_qty(
                    d.item_code, self.wip_warehouse)

    def set_required_items(self, reset_only_qty=False):
        '''set required_items for production to keep track of reserved qty'''
        if not reset_only_qty:
            self.required_items = []

        if self.bom_no and self.qty:
            item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=self.qty, fetch_exploded=False,
                                              fetch_scrap_items=False)
            if reset_only_qty:
                for d in self.get("required_items"):
                    if item_dict.get(d.item_code):
                        d.required_qty = item_dict.get(d.item_code).get("qty")
            else:
                # Attribute a big number (999) to idx for sorting putpose in case idx is NULL
                # For instance in BOM Explosion Item child table, the items coming from sub assembly items
                for item in sorted(item_dict.values(), key=lambda d: d['idx'] or 9999):
                    self.append('required_items', {
                        'operation': item.operation,
                        'item_code': item.item_code,
                        'issue_step': item.issue_step,
                        'item_name': item.item_name,
                        'stock_uom': item.stock_uom or item.uom,
                        'uom': item.uom or item.stock_uom,
                        'conversion_factor': item.conversion_factor or 1,
                        'description': item.description,
                        'allow_alternative_item': item.allow_alternative_item,
                        'required_qty': item.qty,
                        'source_warehouse': item.source_warehouse or item.default_warehouse,
                        'include_item_in_manufacturing': item.include_item_in_manufacturing
                    })

                    if not self.project:
                        self.project = item.get("project")

            self.set_available_qty()

    def set_scrap_items(self, reset_only_qty=False):
        '''set required_items for production to keep track of reserved qty'''
        if not reset_only_qty:
            self.scrap_items = []

        if self.bom_no and self.qty:
            item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=self.qty,
                                              fetch_exploded=self.use_multi_level_bom, fetch_scrap_items=True)

            if reset_only_qty:
                for d in self.get("scrap_items"):
                    if item_dict.get(d.item_code):
                        d.required_qty = item_dict.get(d.item_code).get("qty")
            else:
                # Attribute a big number (999) to idx for sorting putpose in case idx is NULL
                # For instance in BOM Explosion Item child table, the items coming from sub assembly items
                for item in sorted(item_dict.values(), key=lambda d: d['idx'] or 9999):
                    self.append('scrap_items', {
                        'operation': item.operation,
                        'item_code': item.item_code,
                        'issue_step': item.issue_step,
                        'item_name': item.item_name,
                        'stock_uom': item.stock_uom or item.uom,
                        'uom': item.uom or item.stock_uom,
                        'conversion_factor': item.conversion_factor or 1,
                        'description': item.description,
                        'allow_alternative_item': item.allow_alternative_item,
                        'required_qty': item.qty,
                        'source_warehouse': item.source_warehouse or item.default_warehouse,
                        'include_item_in_manufacturing': 1
                    })

                    if not self.project:
                        self.project = item.get("project")

            self.set_available_qty()

    def update_transaferred_qty_for_required_items(self):
        '''update transferred qty from submitted stock entries for that item against
                the Production Order'''

        for d in self.required_items:
            transferred_qty = frappe.db.sql('''
                SELECT sum(detail.qty)
                FROM `tabStock Entry` entry
                LEFT JOIN `tabStock Entry Detail` detail ON detail.parent=entry.name
                where
                	entry.production_order = %(name)s
                	and entry.purpose = "Material Transfer for Manufacture"
                	and entry.docstatus = 1
                	and detail.production_detail = %(item)s ''', {
                'name': self.name,
                'item': d.name
            })[0][0]

            d.db_set('transferred_qty', flt(
                transferred_qty), update_modified=False)

        for d in self.scrap_items:
            transferred_qty = frappe.db.sql('''
                SELECT sum(detail.qty)
                FROM `tabStock Entry` entry
                LEFT JOIN `tabStock Entry Detail` detail ON detail.parent=entry.name
                where
                	entry.production_order = %(name)s
                	and entry.purpose = "Material Transfer for Manufacture"
                	and entry.docstatus = 1
                	and detail.production_detail = %(item)s ''', {
                'name': self.name,
                'item': d.name
            })[0][0]

            d.db_set('transferred_qty', flt(
                transferred_qty), update_modified=False)

    def update_consumed_qty_for_required_items(self):
        '''update consumed qty from submitted stock entries for that item against
                the Production Order'''

        for d in self.required_items:
            consumed_qty = frappe.db.sql('''
                SELECT sum(detail.qty)
                FROM `tabStock Entry` entry
                LEFT JOIN `tabStock Entry Detail` detail ON detail.parent=entry.name
                where
                	entry.production_order = %(name)s
                	and (entry.purpose = "Material Consumption for Manufacture" or entry.purpose = "Manufacture")
                	and entry.docstatus = 1 and IFNULL(t_warehouse, "") = "" 
                	and detail.production_detail = %(item)s ''', {
                'name': self.name,
                'item': d.name
            })[0][0]
            d.db_set('consumed_qty', flt(consumed_qty), update_modified=False)

        for d in self.scrap_items:
            consumed_qty = frappe.db.sql('''
                SELECT sum(detail.qty)
                FROM `tabStock Entry` entry
                LEFT JOIN `tabStock Entry Detail` detail ON detail.parent=entry.name
                where
                	entry.production_order = %(name)s
                	and (entry.purpose = "Material Consumption for Manufacture"
                	or entry.purpose = "Manufacture")
                	and entry.docstatus = 1
                	and detail.production_detail = %(item)s ''', {
                'name': self.name,
                'item': d.name
            })[0][0]

            d.db_set('consumed_qty', flt(consumed_qty), update_modified=False)

    def make_bom(self):
        data = frappe.db.sql(""" select sed.item_code, sed.qty, sed.s_warehouse
        	from `tabStock Entry Detail` sed, `tabStock Entry` se
        	where se.name = sed.parent and se.purpose = 'Manufacture'
        	and (sed.t_warehouse is null or sed.t_warehouse = '') and se.docstatus = 1
        	and se.production_order = %s""", (self.name), as_dict=1)

        bom = frappe.new_doc("BOM")
        bom.item = self.production_item
        bom.conversion_rate = 1

        for d in data:
            bom.append('items', {
                'item_code': d.item_code,
                'qty': d.qty,
                'source_warehouse': d.s_warehouse
            })

        if self.operations:
            bom.set('operations', self.operations)
            bom.with_operations = 1

        bom.set_bom_material_details()
        return bom


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
                             select_columns=""", bom_item.source_warehouse, bom_item.issue_step, bom_item.operation,
                bom_item.include_item_in_manufacturing, bom_item.description, bom_item.rate,
                (Select idx from `tabBOM Item` where item_code = bom_item.item_code and parent = %(parent)s limit 1) as idx""")

        items = frappe.db.sql(
            query, {"parent": bom, "qty": qty, "bom": bom, "company": company}, as_dict=True)
    elif fetch_scrap_items:
        query = query.format(table="BOM Scrap Item", where_conditions="",
                             select_columns=", bom_item.idx, bom_item.stock_uom, item.description", is_stock_item=is_stock_item, qty_field="stock_qty")

        items = frappe.db.sql(
            query, {"qty": qty, "bom": bom, "company": company}, as_dict=True)
    else:
        query = query.format(table="BOM Item", where_conditions="", is_stock_item=is_stock_item,
                             qty_field="stock_qty" if fetch_qty_in_stock_uom else "qty",
                             select_columns=""", bom_item.uom, bom_item.stock_uom, bom_item.conversion_factor, bom_item.source_warehouse,
                bom_item.idx, bom_item.operation, bom_item.include_item_in_manufacturing,
                bom_item.description, bom_item.base_rate as rate """)
        items = frappe.db.sql(
            query, {"qty": qty, "bom": bom, "company": company}, as_dict=True)

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
            company_in_record = frappe.db.get_value(
                d[0], item_details.get(d[1]), "company")
            if not item_details.get(d[1]) or (company_in_record and company != company_in_record):
                item_dict[item][d[1]] = frappe.get_cached_value(
                    'Company',  company,  d[2]) if d[2] else None

    return item_dict


@frappe.whitelist()
def get_item_details(item, project=None):
    res = frappe.db.sql("""
        select stock_uom, description, production_route, total_labor, total_overhead, scrap_material_cost,
        intrinsic_material_cost, fabrication_cost, cutting_loss_cost, total_production_route, raw_material_cost,
        total_cost
        from `tabItem`
        where disabled=0
        	and (end_of_life is null or end_of_life='0000-00-00' or end_of_life > %s)
        	and name=%s
	""", (nowdate(), item), as_dict=1)

    if not res:
        return {}

    res = res[0]
    res['production_steps'] = []
    if res['production_route']:
        res['production_steps'] = frappe.db.sql("""SELECT production_step, issue_step, labor, overhead
                                                   FROM `tabProduction Route Table`
                                                   WHERE parent='{}' Order By idx""".format(res['production_route']), as_dict=1)
    filters = {"item": item, "is_default": 1}

    if project:
        filters = {"item": item, "project": project}

    res["bom_no"] = frappe.db.get_value("BOM", filters=filters)

    if not res["bom_no"]:
        variant_of = frappe.db.get_value("Item", item, "variant_of")

        if variant_of:
            res["bom_no"] = frappe.db.get_value(
                "BOM", filters={"item": variant_of, "is_default": 1})

    if not res["bom_no"]:
        if project:
            res = get_item_details(item)
            frappe.msgprint(_("Default BOM not found for Item {0} and Project {1}").format(
                item, project), alert=1)
        else:
            frappe.throw(_("Default BOM for {0} not found").format(item))

    bom_data = frappe.db.get_value('BOM', res['bom_no'],
                                   ['project', 'allow_alternative_item', 'transfer_material_against', 'item_name'], as_dict=1)

    settings = frappe.get_doc('Hampden Settings', 'Hampden Settings')
    res['wip_warehouse'] = settings.wip_warehouse or ''
    res['scrap_warehouse'] = settings.scrap_warehouse or ''
    res['target_warehouse'] = settings.target_warehouse or ''

    res['project'] = project or bom_data.pop("project")
    res.update(bom_data)
    res.update(check_if_scrap_warehouse_mandatory(res["bom_no"]))

    return res


@frappe.whitelist()
def check_if_scrap_warehouse_mandatory(bom_no):
    res = {"set_scrap_wh_mandatory": False}
    if bom_no:
        bom = frappe.get_doc("BOM", bom_no)

        if len(bom.scrap_items) > 0:
            res["set_scrap_wh_mandatory"] = True

    return res


@frappe.whitelist()
def make_stock_entry(production_order_id, purpose, issue=None, qty=None):
    production_order = frappe.get_doc("Production Order", production_order_id)
    if not frappe.db.get_value("Warehouse", production_order.wip_warehouse, "is_group") \
            and not production_order.skip_transfer:
        wip_warehouse = production_order.wip_warehouse
    else:
        wip_warehouse = None

    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.purpose = purpose
    stock_entry.issue_step = issue
    stock_entry.production_order = production_order_id
    stock_entry.company = production_order.company
    stock_entry.from_bom = 0
    stock_entry.bom_no = production_order.bom_no
    stock_entry.use_multi_level_bom = production_order.use_multi_level_bom
    stock_entry.fg_completed_qty = qty or (
        flt(production_order.qty) - flt(production_order.produced_qty))
    if production_order.bom_no:
        stock_entry.inspection_required = frappe.db.get_value('BOM',
                                                              production_order.bom_no, 'inspection_required')

    if purpose == "Material Transfer for Manufacture":
        stock_entry.to_warehouse = wip_warehouse
        stock_entry.scrap_warehouse = production_order.scrap_warehouse
        stock_entry.project = production_order.project
    else:
        stock_entry.from_warehouse = wip_warehouse
        stock_entry.to_warehouse = production_order.fg_warehouse
        stock_entry.project = production_order.project
        stock_entry.fg_completed_qty = production_order.qty

    stock_entry.set_stock_entry_type()
    stock_entry.get_production_order_items(issue_step=issue)
    return stock_entry.as_dict()


@frappe.whitelist()
def get_default_warehouse():
    wip_warehouse = frappe.db.get_single_value("Manufacturing Settings",
                                               "default_wip_warehouse")
    fg_warehouse = frappe.db.get_single_value("Manufacturing Settings",
                                              "default_fg_warehouse")
    return {"wip_warehouse": wip_warehouse, "fg_warehouse": fg_warehouse}


@frappe.whitelist()
def stop_unstop(production_order, status):
    """ Called from client side on Stop/Unstop event"""

    if not frappe.has_permission("Production Order", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    pro_order = frappe.get_doc("Production Order", production_order)
    pro_order.update_status(status)
    pro_order.update_planned_qty()
    frappe.msgprint(_("Production Order has been {0}").format(status))
    pro_order.notify_update()

    return pro_order.status


@frappe.whitelist()
def query_sales_order(production_item):
    out = frappe.db.sql_list("""
        select distinct so.name from `tabSales Order` so, `tabSales Order Item` so_item
        where so_item.parent=so.name and so_item.item_code=%s and so.docstatus=1
	union
        select distinct so.name from `tabSales Order` so, `tabPacked Item` pi_item
        where pi_item.parent=so.name and pi_item.item_code=%s and so.docstatus=1
	""", (production_item, production_item))

    return out

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sales_order_items(doctype, txt, searchfield, start, page_len, filters):
    
	parent = filters.get('sales_order', '')
	if parent:
		parent = "WHERE parent='{}'".format(parent)
	return frappe.db.sql("""
        SELECT item_code, item_name
        FROM `tabSales Order Item`
        {}
    """.format(parent))
