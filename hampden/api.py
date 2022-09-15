from __future__ import unicode_literals

import frappe
import erpnext
from frappe.utils import cint, cstr, flt
from frappe import _
from erpnext.stock.get_item_details import get_price_list_rate
import json
from frappe.desk.form.load import get_attachments


@frappe.whitelist()
def get_item_association_data(item_code):

    iat = frappe.get_list('Item Association Table',
                          filters={'independent': item_code},
                          fields=['dependent', 'scrap', 'dependent_percentage', 'scrap_percentage', 'cutting_loss_'])

    result = {}
    iat_result = []
    rate = get_valuation_rate(item_code)

    for i in iat:
        if i.get('dependent', False) and flt(i.get('dependent_percentage', 0)) > 0:
            dependent = frappe.get_doc('Item', i.get('dependent'))
            dependent_rate = get_valuation_rate(i.get('dependent'))
            qty = (1*i.get('dependent_percentage', 0)/100) + \
                (1*i.get('cutting_loss_', 0)/100) + \
                (1*i.get('scrap_percentage', 0)/100)
            iat_result.append({
                'dependent': {
                    'item_code': i.get('dependent'),
                    'dependent_percent': i.get('dependent_percentage', 0),
                    'qty': qty,
                    'amount': dependent_rate * qty,
                    # 'stock_qty': 1 + (1*i.get('dependent_percentage', 0)/100) + (1*i.get('cutting_loss_', 0)*100) + (1*i.get('scrap_percentage', 0)*100)
                    'uom': dependent.stock_uom,
                    'stock_uom': dependent.stock_uom,
                    'item_name': dependent.item_name,
                    'description': dependent.description,
                    'item_type': 'Dependent',
                    'independent': item_code,
                    'rate': dependent_rate
                }
            })

        if flt(i.get('cutting_loss_', 0)) > 0:
            item = frappe.get_doc('Item', item_code)
            item_rate = get_valuation_rate(item_code)
            qty = 1*i.get('cutting_loss_', 0)/100
            iat_result.append({
                'cutting_loss': {
                    'item_code': item_code,
                    'cutting_percent': i.get('cutting_loss_', 0),
                    'qty': qty,
                    'amount': qty * item_rate,
                    # 'stock_qty': 1 + (1*i.get('dependent_percentage', 0)/100) + (1*i.get('cutting_loss_', 0)*100) + (1*i.get('scrap_percentage', 0)*100)
                    'uom': item.stock_uom,
                    'stock_uom': item.stock_uom,
                    'item_name': item.item_name,
                    'description': item.description,
                    'item_type': 'Cutting Loss',
                    'independent': item_code,
                    'rate': item_rate
                }
            })

        if i.get('scrap', False) and flt(i.get('scrap_percentage', 0)) > 0:
            item = frappe.get_doc('Item',  i.get('scrap', False))
            item_rate = get_valuation_rate(item.item_code)
            qty = 1*i.get('scrap_percentage', 0)/100
            iat_result.append({
                'scrap_item': {
                    'item_code': item_code,
                    'scrap_percent': i.get('scrap_percentage', 0),
                    'stock_qty': qty,
                    'amount': qty * item_rate,
                    # 'stock_qty': 1 + (1*i.get('dependent_percentage', 0)/100) + (1*i.get('cutting_loss_', 0)*100) + (1*i.get('scrap_percentage', 0)*100)
                    'uom': item.stock_uom,
                    'stock_uom': item.stock_uom,
                    'item_name': item.item_name,
                    'description': item.description,
                    'item_type': 'Scrap',
                    'independent': item_code,
                    'rate': item_rate
                }
            })

    result.update({
        'rate': rate,
        'iat': iat_result
    })

    return result


@frappe.whitelist()
def update_items_with_associations(item_association=None):
    if not item_association or not frappe.db.exists('Item Association', item_association):
        frappe.throw(_('Item Association required'))

    association = frappe.get_doc('Item Association', item_association)
    for row in association.item_association:
        independent = row.independent or False
        dependent = row.dependent or False
        association_scrap = row.scrap or False
        dependent_percentage = row.dependent_percentage or 0.0
        scrap_percentage = row.scrap_percentage or 0.0
        cutting_loss = row.cutting_loss_ or 0.0

        if independent:
            items_with_independent = frappe.db.sql("SELECT DISTINCT(parent) From `tabItem Item` WHERE item_code='{}' AND item_type='Independent' ".format(independent), as_dict=True)

            for master_item in items_with_independent:
                master_item = frappe.get_doc('Item', master_item.parent)
                independent_qty_in_master = 0
                independent_rate_in_master = 0
                independent_desc_in_master = ''
                independent_name_in_master = ''
                independent_uom_in_master = ''
                for row in master_item.items:
                    if row.item_type == "Independent" and row.item_code == independent:
                        independent_qty_in_master = row.qty
                        independent_rate_in_master = row.rate
                        independent_name_in_master = row.item_name
                        independent_desc_in_master = row.description
                        independent_uom_in_master = row.uom
               
                # Check Cutting loss
                has_cutting = False
                cutting_loss_qty = independent_qty_in_master * cutting_loss / 100
                for row in master_item.items:
                    if row.item_code == independent and row.item_type == "Cutting Loss" and row.independent == independent:
                        if cutting_loss_qty == 0:
                            frappe.get_doc('Item Item', row.name).delete()
                        else:
                            row.qty = cutting_loss_qty
                            row.amount = row.rate * cutting_loss_qty
                        has_cutting = True

                if not has_cutting and cutting_loss_qty != 0:
                    master_item.append('items', {
                        'item_code': independent,
                        'item_type': "Cutting Loss",
                        'qty': cutting_loss_qty,
                        'uom': independent_uom_in_master,
                        'item_name': independent_name_in_master,
                        'description': independent_desc_in_master,
                        'rate': flt(independent_rate_in_master),
                        'amount': flt(independent_rate_in_master) * cutting_loss_qty,
                        'independent': independent,
                        'cutting_percent': cutting_loss,
                    })

                # Check Cutting loss
                if association_scrap:
                    scrap_found = False
                    scrap_qty = independent_qty_in_master * scrap_percentage / 100
                    for scrap_item in master_item.production_scrap_item:
                        if association_scrap == scrap_item.item_code and scrap_item.independent == independent:
                            if scrap_qty == 0:
                                frappe.get_doc(
                                    'Production Scrap Item', scrap_item.name).delete()
                            else:
                                scrap_item.stock_qty = scrap_qty
                                scrap_item.amount = flt(
                                    scrap_item.rate) * scrap_qty
                                scrap_item.scrap_percent = scrap_percentage
                            scrap_found = True

                    if not scrap_found and scrap_qty != 0:
                        rate = get_valuation_rate(association_scrap)
                        master_item.append('production_scrap_item', {
                            'item_code': association_scrap,
                            'stock_qty': scrap_qty,
                            'rate': rate,
                            'amount': rate * scrap_qty,
                            'independent': independent,
                            'item_type': "Scrap",
                            'scrap_percent': scrap_percentage
                        })
                
                # Check Dependent
                if dependent:
                    has_dependent = False
                    cutting_loss_qty = independent_qty_in_master * cutting_loss / 100
                    scrap_qty = independent_qty_in_master * scrap_percentage / 100
                    dependent_qty = independent_qty_in_master * dependent_percentage / 100

                    for row in master_item.items:
                        if row.item_code == dependent and row.item_type == "Dependent" and row.independent == independent:
                            if dependent_qty == 0:
                                frappe.get_doc('Item Item', row.name).delete()
                            else:
                                row.qty = (cutting_loss_qty +
                                           scrap_qty + dependent_qty)
                                row.amount = row.rate * \
                                    (cutting_loss_qty + scrap_qty + dependent_qty)
                            has_dependent = True
                    if not has_dependent and dependent_qty != 0:
                        dependent = frappe.get_doc('Item', dependent)
                        rate = get_valuation_rate(dependent.item_code)
                        master_item.append('items', {
                            'item_code': dependent.item_code,
                            'item_type': "Dependent",
                            'qty': (cutting_loss_qty + scrap_qty + dependent_qty),
                            'uom': dependent.stock_uom,
                            'item_name': dependent.item_name,
                            'description': dependent.description,
                            'rate': rate,
                            'amount': flt(rate) * (cutting_loss_qty + scrap_qty + dependent_qty),
                            'independent': independent
                        })
                
                # production_route = 0
                # raw_material_cost = 0
                # scrap_cost = 0
                # total_cost = 0

                # intrinsic_material_cost = 0
                # fabrication_cost = 0
                # cutting_loss_cost = 0
                
                master_item.save()
                # frappe.db.commit()
                # master_item = frappe.get_doc('Item', master_item.item_code)
                # for row in master_item.items:
                #     if (row.item_type == "Independent"):
                #         intrinsic_material_cost += row.amount
                    
                #     if (row.item_type == "Dependent"):
                #         fabrication_cost += row.amount
                    
                #     if (row.item_type == "Cutting Loss"):
                #         cutting_loss_cost += row.amount
                    
                #     raw_material_cost += row.amount
                
                # for row in master_item.production_scrap_item:
                #     scrap_cost += row.amount
                
                # for row in master_item.production_item_table:
                #     production_route += row.total
                
                # # total_cost = raw_material_cost - scrap_cost + production_route
                # total_cost = raw_material_cost + production_route

                # master_item.db_set('intrinsic_material_cost', intrinsic_material_cost)
                # master_item.db_set('fabrication_cost', fabrication_cost)
                # master_item.db_set('cutting_loss_cost', cutting_loss_cost)

                # master_item.db_set('total_production_route', production_route)
                # master_item.db_set('raw_material_cost', raw_material_cost)
                # master_item.db_set('scrap_material_cost', scrap_cost)
                # master_item.db_set('total_cost', total_cost)

                # # master_item.save()
                # frappe.db.commit()

    return 'Done!'


def on_update_item(doc, method):
    #Update Costs in Item
    pass


def validate_item(doc, method):
    for d in doc.get("items"):
        rate = get_valuation_rate(
            d.item_code, frappe.defaults.get_global_default('company'))
        if rate:
            d.rate = rate
        default_bom = frappe.db.get_value('Item', d.item_code, 'default_bom')
        if default_bom:
            d.bom_no = default_bom
        else:
            d.bom_no = ''
        d.amount = flt(d.rate) * flt(d.qty)
        d.base_rate = flt(d.rate)  # * flt(self.conversion_rate)
        d.base_amount = flt(d.amount)  # * flt(self.conversion_rate)
        # d.db_update()
    production_route = 0
    raw_material_cost = 0
    scrap_cost = 0
    total_cost = 0

    intrinsic_material_cost = 0
    fabrication_cost = 0
    cutting_loss_cost = 0

    for row in doc.items:
        if (row.item_type == "Independent"):
            intrinsic_material_cost += row.amount
        
        if (row.item_type == "Dependent"):
            fabrication_cost += row.amount
        
        if (row.item_type == "Cutting Loss"):
            cutting_loss_cost += row.amount
        
        raw_material_cost += row.amount
    
    for row in doc.production_scrap_item:
        scrap_cost += row.amount
    
    for row in doc.production_item_table:
        production_route += row.total
    
    # total_cost = raw_material_cost - scrap_cost + production_route
    total_cost = raw_material_cost + production_route

    doc.intrinsic_material_cost = intrinsic_material_cost
    doc.fabrication_cost = fabrication_cost
    doc.cutting_loss_cost = cutting_loss_cost

    doc.total_production_route = production_route
    doc.raw_material_cost = raw_material_cost
    doc.scrap_material_cost = scrap_cost
    doc.total_cost = total_cost
    # frappe.db.commit()


def update_bom_on_change(doc, method):
    # if len(doc.items) == 0:
    #     doc.default_bom = ''
    #     return

    if doc.default_bom and len(doc.items) != 0:
        # check if BOM and Scrap Items Changed !
        item_bom_items = {}

        for item in doc.items:
            found = item_bom_items.get('{}'.format(item.item_code), False)
            if found:
                item_bom_items['{}'.format(item.item_code)]['qty'] += item.qty
                item_bom_items['{}'.format(
                    item.item_code)]['rate'] += item.rate
            else:
                new_value = {
                    'qty': item.qty,
                    'rate': item.rate
                }
                item_bom_items['{}'.format(item.item_code)] = new_value

        bom_items = frappe.db.sql("""
            SELECT bom_item.item_code, SUM(bom_item.rate) as rate, SUM(bom_item.qty) as qty
            FROM `tabBOM` bom
            LEFT JOIN `tabBOM Item` bom_item ON bom.name=bom_item.parent
            WHERE bom_item.parent='{}'
            GROUP BY bom_item.item_code
        """.format(doc.default_bom), as_dict=True)

        if len(item_bom_items.keys()) != len(bom_items):
            create_bom(doc)
            return
        for itm in bom_items:
            rate = itm['rate']
            qty = itm['qty']
            from_doc = item_bom_items.get('{}'.format(itm['item_code']), False)

            if from_doc:
                if flt(from_doc['qty'], 2) != flt(qty, 2) or flt(from_doc['rate'], 2) != flt(rate, 2):
                    create_bom(doc)
                    return
            else:
                create_bom(doc)
                return
        if len(doc.items) == 0:
            return
        # Check if scrap is changed !
        item_bom_items = {}

        for item in doc.production_scrap_item:
            found = item_bom_items.get('{}'.format(item.item_code), False)
            if found:
                item_bom_items['{}'.format(
                    item.item_code)]['stock_qty'] += item.stock_qty
                item_bom_items['{}'.format(
                    item.item_code)]['rate'] += item.rate
            else:
                new_value = {
                    'stock_qty': item.stock_qty,
                    'rate': item.rate
                }
                item_bom_items['{}'.format(item.item_code)] = new_value

        bom_items = frappe.db.sql("""
            SELECT bom_item.item_code, SUM(bom_item.rate) as rate, SUM(bom_item.stock_qty) as qty
            FROM `tabBOM` bom
            LEFT JOIN `tabBOM Scrap Item` bom_item ON bom.name=bom_item.parent
            WHERE bom_item.parent='{}'
            GROUP BY bom_item.item_code
        """.format(doc.default_bom), as_dict=True)

        if len(item_bom_items.keys()) != len(bom_items):
            create_bom(doc)
            return

        for itm in bom_items:
            rate = itm['rate']
            qty = itm['qty']
            from_doc = item_bom_items.get('{}'.format(itm['item_code']), False)

            if from_doc:
                if flt(from_doc['stock_qty'], 2) != flt(qty, 2) or flt(from_doc['rate'], 2) != flt(rate, 2):
                    create_bom(doc)
                    return
            else:
                create_bom(doc)
                return
    else:
        # create BOM for BOM and Scrap items !
        # print('CREATE FRO EMPTY BOM')
        if len(doc.items) != 0:
            create_bom(doc)
        return

    # if need_new_bom: create_bom(doc)


def create_bom(doc):
    new_bom = frappe.new_doc('BOM')
    new_bom.item = doc.item_code
    new_bom.item_name = doc.item_name
    new_bom.uom = doc.stock_uom
    new_bom.is_active = 1
    new_bom.is_default = 1
    new_bom.set_rate_of_sub_assembly_item_based_on_bom = 1
    new_bom.quantity = 1
    new_bom.rm_cost_as_per = frappe.db.get_value(
        'Hampden Settings', 'Hampden Settings', 'rate_based_on') or "Valuation Rate"  # doc.rm_cost_as_per

    for item in doc.items:
        new_bom.append('items', {
            'item_code': item.item_code,
            'item_name': item.item_name,
            'operation': item.operation,
            'issue_step': item.issue_step,
            # 'bom_no': item.bom_no,
            'source_warehouse': item.source_warehouse,
            'allow_alternative_item': item.allow_alternative_item,
            'description': item.description,
            'image': item.image,
            'qty': item.qty,
            'uom': item.uom,
            'stock_qty': item.stock_qty,
            'stock_uom': item.stock_uom,
            'conversion_factor': item.conversion_factor,
            'rate': flt(item.rate),
            'base_rate': item.base_rate,
            'amount': item.amount,
            'base_amount': item.base_amount,
            'scrap': item.scrap,
            'qty_consumed_per_unit': item.qty_consumed_per_unit,
            'include_item_in_manufacturing': item.include_item_in_manufacturing,
            'original_item': item.original_item,
            'cutting_loss': item.cutting_loss
        })

    for item in doc.production_scrap_item:
        new_bom.append('scrap_items', {
            'item_code': item.item_code,
            'issue_step': item.issue_step,
            'item_name': item.item_name,
            'stock_qty': item.stock_qty,
            'rate': item.rate,
            'amount': item.amount,
            'stock_uom': item.stock_uom,
            'base_rate': item.base_rate,
            'base_amount': item.base_amount,
        })
    new_bom.save()
    new_bom.submit()
    frappe.db.commit()


@frappe.whitelist()
def get_valuation_rate(item_code, company=frappe.defaults.get_global_default('company')):
    """ Get weighted average of valuation rate from all warehouses """
    if not company:
        company = frappe.defaults.get_global_default('company')

    based_on = frappe.db.get_value(
        'Hampden Settings', 'Hampden Settings', 'rate_based_on') or "Valuation Rate"
    valuation_rate = 0

    if based_on == "Valuation Rate":
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
    elif based_on == "Last Purchase Rate":
        valuation_rate = frappe.db.get_value(
            "Item", item_code, "last_purchase_rate")

    return flt(valuation_rate)


def update_all_items_rates(doc, method):
    if doc.doctype in ["Sales Invoice", "Purchase Invoice"]:
        if not doc.update_stock:
            return

    settings = frappe.get_doc('Hampden Settings')
    make_updates = True if settings.update_item_rate else False
    allow_zero_rate = True if settings.allow_zero_rate else False

    if not make_updates:
        return
    
    transaction_items = []
    parents_to_update = set()

    for item in doc.items:
        transaction_items.append(item.item_code)
    
    # print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$", make_updates)
    for item in frappe.get_list('Item Item', filters={'item_code': ['in', transaction_items]}):
        if not frappe.db.exists('Item', item.name):
            continue
        item = frappe.get_doc('Item Item', item.name)
        rate = get_valuation_rate(item.item_code)
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
    
    for item in frappe.get_list('Production Scrap Item', filters={'item_code': ['in', transaction_items]}):
        item = frappe.get_doc('Production Scrap Item', item.name)
        parents_to_update.add(item.parent)
        rate = get_valuation_rate(item.item_code)
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


# def jv_for_work_orders(doc, method):
#     if doc.purpose == "Manufacture" and doc.work_order:
#         wo = frappe.get_doc('Work Order', doc.work_order)
#         settings = frappe.get_doc("Hampden Settings", "Hampden Settings")
#         if method == "on_cancel":
#             if wo.work_order_jv:
#                 jv = frappe.get_doc('Journal Entry', wo.work_order_jv)
#                 wo.work_order_jv = ''
#                 wo.save()
#                 jv.cancel()
#                 frappe.db.commit()
#         else:
#             if wo.status == "Completed":
#                 if not wo.production_item or settings.create_journal_for_work_order == 0:
#                     return
                
#                 production_item = frappe.get_doc('Item', wo.production_item)
#                 total_labor = flt((production_item.total_labor or 0))
#                 total_overhead = flt((production_item.total_overhead or 0))
#                 if total_labor == 0 and total_overhead == 0:
#                     frappe.msgprint(
#                         '0 Labor and Overhead for Item {}'.format(wo.production_item))
#                     return

                
#                 total_labor = total_labor * flt(wo.produced_qty)
#                 total_overhead = total_overhead * flt(wo.produced_qty)

#                 labo_acc = settings.labor_account
#                 over_acc = settings.overhead_account
#                 debt_acc = settings.creditor_account

#                 if not labo_acc or not over_acc or not debt_acc:
#                     frappe.throw('Account Needed !')

#                 je = frappe.new_doc("Journal Entry")
#                 je.voucher_type = "Journal Entry"
#                 je.remark = "Journal Entry To {}".format(wo.name)
#                 je.posting_date = doc.posting_date
#                 je.company = doc.company
#                 je.work_order = wo.name

#                 je.append("accounts", {"account": labo_acc,
#                           "debit_in_account_currency": total_labor})
#                 je.append("accounts", {"account": over_acc,
#                           "debit_in_account_currency": total_overhead})
#                 je.append("accounts", {"account": debt_acc, "credit_in_account_currency": (
#                     total_labor+total_overhead)})

#                 je.save()
#                 je.submit()

#                 wo.work_order_jv = je.name
#                 wo.save()


# def get_wo_dashboard_data(data):
#     data['transactions'].append(
#         {
#             'label': _('Accounting'),
#             'items': ['Journal Entry']
#         }
#     )
#     return data
def get_sales_order_dashboard_data(data):
    found = False
    for trans in data['transactions']:
        if _(trans['label']) == _('Manufacturing'):
            trans['items'].append(_('Production Order'))
            found = True
    if not found:
        data['transactions'].append(
            {
                'label': _('Manufacturing'),
                'items': ['Production Order']
            }
        )
    return data

@frappe.whitelist()
def get_item_details(args, doc=None, for_validate=False, overwrite_warehouse=True):
    from erpnext.stock.get_item_details import get_item_details

    out = get_item_details(args, doc=doc, for_validate=for_validate, overwrite_warehouse=overwrite_warehouse)
    
    args = json.loads(args)

    if(args.get('doctype', False) == "Purchase Receipt"):
        metal_type = frappe.get_value('Item', out.item_code, 'metal_type') or ''
        dependents_list = []
        current_item = args.get('item_code', False)
        if args.get('item_code', False):
            sql_result = frappe.db.sql("""
                SELECT DISTINCT(dependent) as item_code
                FROM  `tabItem Association Table`
                WHERE independent='{}'""".format(args.get('item_code')), as_dict=True)
            for item in sql_result:
                args['item_code'] = item.item_code
                i = get_item_details(args, doc=doc, for_validate=for_validate, overwrite_warehouse=overwrite_warehouse)
                dependents_list.append(i)
        out.update({
            'metal_type': metal_type,
            'dependents_list': dependents_list
        })
    
    if(args.get('doctype', False) == "Sales Invoice"):
        if args.get('production_invoice', 0)==1 and args.get('production_order', False):
            if args.get('production_invoice', 0)==1 and args.get('production_order', False):
                item_code = args.get('item_code', False)
                if frappe.db.exists('Production Order', args.get('production_order')):
                    production_order = frappe.get_doc('Production Order', args.get('production_order'))
                    prod_item = production_order.production_item

                if item_code and prod_item == item_code:
                    rate = flt(production_order.raw_material_cost)
                    out.update({
                        'rate': rate,
                        'base_rate': rate * out.get('conversion_factor', 1),
                        'price_list_rate': rate,
                        'base_price_list_rate': rate * out.get('conversion_factor', 1)
                    })
    return out


def validate_stock_entry(doc, method):
    doc.pro_doc = frappe._dict()
    if doc.production_order:
        doc.pro_doc = frappe.get_doc('Production Order', doc.production_order)
    
    doc.validate_production_order()
    doc.validate_finished_goods_in_production_order()

def submit_stock_entry(doc, method):
    doc.update_production_order()
    if doc.production_order and doc.purpose == "Manufacture":
        doc.update_so_in_serial_number_for_production()
    update_all_items_rates(doc, method)

def cancel_stock_entry(doc, method):
    doc.update_production_order()
    update_all_items_rates(doc, method)

def submit_journal_entry(doc, method):
    # Set is paid = 1 if any journal is created for production order
    orders = set()
    for account in doc.accounts:
        if account.reference_type == 'Production Order':
            if account.reference_name:
                orders.add(account.reference_name)
    for order in orders:
        order = frappe.get_doc('Production Order', order)
        order.db_set('is_paid', 1, update_modified=False)

def cancel_journal_entry(doc, method):
    orders = set()
    orders_str = []
    for account in doc.accounts:
        if account.reference_type == 'Production Order':
            if account.reference_name:
                orders.add(account.reference_name)

    for order in orders:
        order = f"'{order}'"
        orders_str.append(order)
    
    other_jvs = []
    if len(orders_str) != 0:
        other_jvs = frappe.db.sql("""
            SELECT DISTINCT(jv.name)
            FROM `tabJournal Entry` jv
            LEFT JOIN `tabJournal Entry Account` jvd ON jv.name=jvd.parent
            WHERE jv.docstatus=1 AND jvd.reference_type = 'Production Order'
            AND jvd.reference_name in ({})
        """.format(", ".join(orders_str)))
    if len(other_jvs) == 0:
        for order in orders:
            order = frappe.get_doc('Production Order', order)
            order.db_set('is_paid', 0, update_modified=False)
    else:
        for order in orders:
            order = frappe.get_doc('Production Order', order)
            order.db_set('is_paid', 1, update_modified=False)

@frappe.whitelist()
def get_payment_entry_against_invoice(dt, dn, amount=None,  debit_in_account_currency=None, journal_entry=False, bank_account=None):
    from erpnext.accounts.doctype.journal_entry.journal_entry import get_party_account_based_on_invoice_discounting

    ref_doc = frappe.get_doc(dt, dn)
    if not ref_doc.production_order:
        frappe.throw('Can not pay against Non Production invoice')

    if dt == "Sales Invoice":
        party_type = "Customer"
        party_account = get_party_account_based_on_invoice_discounting(dn) or ref_doc.debit_to
    else:
        party_type = "Supplier"
        party_account = ref_doc.credit_to

    if (dt == "Sales Invoice" and ref_doc.outstanding_amount > 0) \
        or (dt == "Purchase Invoice" and ref_doc.outstanding_amount < 0):
            amount_field_party = "credit_in_account_currency"
            amount_field_bank = "debit_in_account_currency"
    else:
        amount_field_party = "debit_in_account_currency"
        amount_field_bank = "credit_in_account_currency"

    jv =  get_payment_entry(ref_doc, {
        "party_type": party_type,
        "party_account": party_account,
        "party_account_currency": ref_doc.party_account_currency,
        "amount_field_party": amount_field_party,
        "amount_field_bank": amount_field_bank,
        "amount": amount if amount else abs(ref_doc.outstanding_amount),
        "debit_in_account_currency": debit_in_account_currency,
        "remarks": 'Payment received against {0} {1}. {2}'.format(dt, dn, ref_doc.remarks),
        "is_advance": "No",
        "bank_account": bank_account,
        "journal_entry": journal_entry
    })

    jv_doc = frappe.new_doc('Journal Entry')
    jv_doc.update(jv)
    jv_doc.posting_date = frappe.utils.now()
    jv_doc.save()
    jv_doc.submit()
    frappe.db.commit()
    return 'Done'


def get_payment_entry(ref_doc, args):
    from erpnext.accounts.doctype.journal_entry.journal_entry import get_exchange_rate, get_account_currency, get_balance_on
    
    cost_center = ref_doc.get("cost_center") or frappe.get_cached_value('Company',  ref_doc.company,  "cost_center")
    exchange_rate = 1
    if args.get("party_account"):
        # Modified to include the posting date for which the exchange rate is required.
        # Assumed to be the posting date in the reference document
        exchange_rate = get_exchange_rate(ref_doc.get("posting_date") or ref_doc.get("transaction_date"),
            args.get("party_account"), args.get("party_account_currency"),
            ref_doc.company, ref_doc.doctype, ref_doc.name)

    je = frappe.new_doc("Journal Entry")
    je.update({
        "voucher_type": "Journal Entry",
        "company": ref_doc.company,
        "remark": args.get("remarks")
    })
    
    party_row = je.append("accounts", {
        "account": args.get("party_account"),
        "party_type": args.get("party_type"),
        "party": ref_doc.get(args.get("party_type").lower()),
        "cost_center": cost_center,
        "account_type": frappe.db.get_value("Account", args.get("party_account"), "account_type"),
        "account_currency": args.get("party_account_currency") or \
                            get_account_currency(args.get("party_account")),
        "balance": get_balance_on(args.get("party_account")),
        "party_balance": get_balance_on(party=args.get("party"), party_type=args.get("party_type")),
        "exchange_rate": exchange_rate,
        args.get("amount_field_party"): args.get("amount"),
        "is_advance": args.get("is_advance"),
        "reference_type": ref_doc.doctype,
        "reference_name": ref_doc.name
    })
    production_order = frappe.get_doc('Production Order', ref_doc.production_order)
    settings = frappe.get_doc('Hampden Settings', 'Hampden Settings')
    for i in ['Intrinsic', 'Fabrication', 'Cutting']:
        account = None
        amount = 0
        if i == "Intrinsic" and settings.intrinsic_account:
            account = settings.intrinsic_account
            amount = production_order.intrinsic_material_cost
        
        if i == "Fabrication" and settings.fabrication_account:
            account = settings.fabrication_account
            amount = production_order.fabrication_cost
        
        if i == "Cutting" and settings.cutting_loss_account:
            account = settings.cutting_loss_account
            amount = production_order.cutting_loss_cost
        
        # if i == "Variance" and settings.default_variance_account:
        #     account = settings.default_variance_account
        if not account or not amount:
            continue

        je.append("accounts", {
            "account": account,
            "account_type": frappe.db.get_value("Account", account, "account_type"),
            "account_currency": get_account_currency(account),
            "balance": get_balance_on(account),
            "exchange_rate": exchange_rate,
            "debit_in_account_currency": amount
        })

    je.set_amounts_in_company_currency()
    je.set_total_debit_credit()

    if not (je.total_debit == je.total_credit):
        # Make D
        if settings.variance_account: 

            if je.total_debit > je.total_credit:
                diff = je.total_debit - je.total_credit
                account = settings.variance_account
                je.append("accounts", {
                    "account": account,
                    "account_type": frappe.db.get_value("Account", account, "account_type"),
                    "account_currency": get_account_currency(account),
                    "balance": get_balance_on(account),
                    "exchange_rate": exchange_rate,
                    "credit_in_account_currency": diff
                })
            else:
                diff = je.total_credit - je.total_debit
                account = settings.variance_account
                je.append("accounts", {
                    "account": account,
                    "account_type": frappe.db.get_value("Account", account, "account_type"),
                    "account_currency": get_account_currency(account),
                    "balance": get_balance_on(account),
                    "exchange_rate": exchange_rate,
                    "debit_in_account_currency": diff
                })
            
            je.set_amounts_in_company_currency()
            je.set_total_debit_credit()

    return je if args.get("journal_entry") else je.as_dict()
    

# @frappe.whitelist()
# def get_item_details(args, doc=None, for_validate=False, overwrite_warehouse=True):
#     from erpnext.stock.get_item_details import get_item_details
#     details = get_item_details(args, doc=doc, for_validate=for_validate, overwrite_warehouse=overwrite_warehouse)
#     if doc and doc.get('doctype', False) == 'Sales Invoice':
#         if args.get('production_invoice', 0)==1 and args.get('production_order', False):
#             item_code = args.get('item_code', False)
#             if frappe.db.exists('Production Order', args.get('production_order')):
#                 production_order = frappe.get_doc('Production Order', args.get('production_order'))
#                 prod_item = production_order.production_item

#             if item_code and prod_item == item_code:
#                 details['rate'] = production_order.total_cost + 100

@frappe.whitelist()
def make_production_orders(items, sales_order, company, project=None):
	'''Make Production Orders against the given Sales Order for the given `items`'''
	items = json.loads(items).get('items')
	out = []

	for i in items:
		if not i.get("bom"):
			frappe.throw(_("Please select BOM against item {0}").format(i.get("item_code")))
		if not i.get("pending_qty"):
			frappe.throw(_("Please select Qty against item {0}").format(i.get("item_code")))
		master_item = frappe.get_doc('Item', i['item_code'])
		order = frappe.get_doc(dict(
			doctype='Production Order',
			production_item=i['item_code'],
			bom_no=i.get('bom'),
			qty=i['pending_qty'],
			company=company,
			sales_order=sales_order,
			sales_order_item=i['sales_order_item'],
			project=project,
			fg_warehouse=i['warehouse'],
			description=i['description'],
		    production_route = master_item.production_route
		)).insert()
		for step in master_item.production_item_table:
			order.append('production_steps', {
                'production_step': step.production_step,
                'issue_step': step.issue_step,
                'labor': step.labor,
                'overhead': step.overhead
            })
		# order.set_required_items()
		order.total_labor = master_item.total_labor
		order.total_overhead = master_item.total_overhead
		order.scrap_material_cost = master_item.scrap_material_cost
		order.intrinsic_material_cost = master_item.intrinsic_material_cost
		order.fabrication_cost = master_item.fabrication_cost
		order.cutting_loss_cost = master_item.cutting_loss_cost
		order.total_production_route = master_item.total_production_route
		order.raw_material_cost = master_item.raw_material_cost
		order.total_cost = master_item.total_cost
		order.set_scrap_items()
		order.set_work_order_operations()
		order.save()
		out.append(order)

	return [p.name for p in out]


def get_default_bom_item(item_code):
	bom = frappe.get_all('BOM', dict(item=item_code, is_active=True),
			order_by='is_default desc')
	bom = bom[0].name if bom else None

	return bom

@frappe.whitelist()
def get_production_order_items(sales_order):
    '''Returns items with BOM that already do not have a linked work order'''
    items = []
    if not frappe.db.exists('Sales Order', sales_order):
        return items
    
    sales_order = frappe.get_doc('Sales Order', sales_order)
    
    item_codes = [i.item_code for i in sales_order.items]
    product_bundle_parents = [pb.new_item_code for pb in frappe.get_all("Product Bundle", {"new_item_code": ["in", item_codes]}, ["new_item_code"])]

    for table in [sales_order.items, sales_order.packed_items]:
        for i in table:
            bom = get_default_bom_item(i.item_code)
            stock_qty = i.qty if i.doctype == 'Packed Item' else i.stock_qty
            # if not for_raw_material_request:
            #     total_work_order_qty = flt(frappe.db.sql('''select sum(qty) from `tabProduction Order`
            #         where production_item=%s and sales_order=%s and sales_order_item = %s and docstatus<2''', (i.item_code, self.name, i.name))[0][0])
            #     pending_qty = stock_qty - total_work_order_qty
            # else:
            #     pending_qty = stock_qty
            pending_qty = stock_qty

            if pending_qty and i.item_code not in product_bundle_parents:
                if bom:
                    items.append(dict(
                        name= i.name,
                        item_code= i.item_code,
                        description= i.description,
                        bom = bom,
                        warehouse = i.warehouse,
                        pending_qty = pending_qty,
                        required_qty = pending_qty,
                        sales_order_item = i.name
                    ))
                else:
                    items.append(dict(
                        name= i.name,
                        item_code= i.item_code,
                        description= i.description,
                        bom = '',
                        warehouse = i.warehouse,
                        pending_qty = pending_qty,
                        required_qty = pending_qty,
                        sales_order_item = i.name
                    ))
    return items


@frappe.whitelist()
def get_production_details(order):
    result = {}
    if not frappe.db.exists('Production Order', order):
        result = {}

    order = frappe.get_doc('Production Order', order)
    item = frappe.get_doc('Item', order.production_item)
    
    sales_order_informarions = None
    if order.sales_order:
        sales_order = frappe.get_doc('Sales Order', order.sales_order)
        sales_order_informarions = {
            'label': "Selling Information",
            'value_type': 'list',
            'value': [
                {
                    'label': "Sales Order",
                    'value_type': 'str',
                    'value': sales_order.name
                },
                {
                    'label': "Customer",
                    'value_type': 'str',
                    'value': sales_order.customer
                },
                {
                    'label': "Sales Order Date",
                    'value_type': 'str',
                    'value': sales_order.transaction_date
                },
                {
                    'label': "Delivery Date",
                    'value_type': 'str',
                    'value': sales_order.delivery_date
                },
                {
                    'label': "Selling Price List",
                    'value_type': 'str',
                    'value': sales_order.selling_price_list
                },
                {
                    'label': "Grand Total",
                    'value_type': 'str',
                    'value': sales_order.grand_total
                },
                {
                    'label': "Currency",
                    'value_type': 'str',
                    'value': sales_order.currency
                }
            ]
        }
    
    item_informations = {
            'label': "Item Information",
            'value_type': 'list',
            'value': [
                {
                    'label': "Item Code",
                    'value_type': 'str',
                    'value': item.item_code,
                },
                {
                    'label': "Item Name",
                    'value_type': 'str',
                    'value': item.item_name,
                },
                {
                    'label': "Item Group",
                    'value_type': 'str',
                    'value': item.item_group,
                },
                {
                    'label': "Production Route",
                    'value_type': 'str',
                    'value': item.production_route,
                },
                {
                    'label': "Item Description",
                    'value_type': 'str',
                    'value': item.description,
                }
            ]
        }
    production_informations = {
            'label': "Production Information",
            'value_type': 'list',
            'value': [
                {
                    'label': "Production Order",
                    'value_type': 'str',
                    'value': order.name
                },
                {
                    'label': "Production Steps",
                    'value_type': 'table',
                    'header':['Production Step', 'Status', 'Complete By', 'Completed On'],
                    'value': [(step.production_step, step.date or '', (step.completed_by or None)) for step in order.production_steps],
                },
            ]
        }
    result = [
        item_informations
    ]
    if sales_order_informarions:
        result.append(sales_order_informarions)
    result.append(production_informations)

    return result


def test_email(doc, method):
    if doc.attached_to_doctype == "Communication":
        if doc.attached_to_name:
            attached_to_name = doc.attached_to_name
            comunincation_doc = frappe.get_doc("Communication", attached_to_name ) 
        if comunincation_doc.reference_doctype == "ETL Setup Screen":
            if frappe.db.exists("ETL Setup Screen", comunincation_doc.reference_name):
                etl_doc = frappe.get_doc("ETL Setup Screen", comunincation_doc.reference_name)
                etl_doc.customer = "C1"
                etl_doc.transform_method = "STULLER"
                etl_doc.file_to_process = doc.file_url
                etl_doc.save()
            else:
                frappe.log_error(message="Doc Not Found", title=f"Failed to Get Doc")
        else:
            frappe.log_error(message="DocType Not ET", title=f"Failed to Get Doc")
