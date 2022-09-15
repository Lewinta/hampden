// Copyright (c) 2021, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Order", {
    setup: function(frm) {
        if (frm.doc.docstatus != 1) {
            // var df = frappe.meta.get_docfield("Production Order Steps", "finish_the_step", frm.doc.name)
            // df.hidden = 1;
            // frm.refresh_fields();
            $('div[data-fieldname="production_steps"]').find('.grid-footer').hide()
        }
        frm.custom_make_buttons = {
            'Stock Entry': 'Start',
            'Pick List': 'Create Pick List',
            'Job Card': 'Create Job Card'
        };

        // Set query for warehouses
        frm.set_query("wip_warehouse", function() {
            return {
                filters: {
                    'company': frm.doc.company,
                }
            };
        });

        frm.set_query("source_warehouse", function() {
            return {
                filters: {
                    'company': frm.doc.company,
                }
            };
        });

        frm.set_query("source_warehouse", "required_items", function() {
            return {
                filters: {
                    'company': frm.doc.company,
                }
            };
        });
        frm.set_query("source_warehouse", "scrap_items", function() {
            return {
                filters: {
                    'company': frm.doc.company,
                }
            };
        });

        frm.set_query("sales_order", function() {
            return {
                filters: {
                    "status": ["not in", ["Closed", "On Hold"]]
                }
            };
        });

        frm.set_query("fg_warehouse", function() {
            return {
                filters: {
                    'company': frm.doc.company,
                    'is_group': 0
                }
            };
        });

        frm.set_query("scrap_warehouse", function() {
            return {
                filters: {
                    'company': frm.doc.company,
                    'is_group': 0
                }
            };
        });

        // Set query for BOM
        frm.set_query("bom_no", function() {
            if (frm.doc.production_item) {
                return {
                    query: "erpnext.controllers.queries.bom",
                    filters: { item: cstr(frm.doc.production_item) }
                };
            } else {
                frappe.msgprint(__("Please enter Production Item first"));
            }
        });

        // Set query for FG Item
        frm.set_query("production_item", function() {
            return {
                query: "erpnext.controllers.queries.item_query",
                filters: [
                    ['is_stock_item', '=', 1],
                    ['default_bom', '!=', '']
                ]
            };
        });

        // Set query for FG Item
        frm.set_query("project", function() {
            return {
                filters: [
                    ['Project', 'status', 'not in', 'Completed, Cancelled']
                ]
            };
        });

        // frm.set_query("operation", "required_items", function () {
        // 	return {
        // 		query: "hampden.hampden.doctype.production_order.production_order.get_bom_operations",
        // 		filters: {
        // 			'parent': frm.doc.bom_no,
        // 			'parenttype': 'BOM'
        // 		}
        // 	};
        // });
        // frm.set_query("operation", "scrap_items", function () {
        // 	return {
        // 		query: "hampden.hampden.doctype.production_order.production_order.get_bom_operations",
        // 		filters: {
        // 			'parent': frm.doc.bom_no,
        // 			'parenttype': 'BOM'
        // 		}
        // 	};
        // });
        frm.set_query("production_item", function() {
            if (frm.doc.sales_order) {
                return {
                    query: "hampden.hampden.doctype.production_order.production_order.get_sales_order_items",
                    filters: {
                        'sales_order': frm.doc.sales_order
                    }
                }
            } else {
                return { filters: {} }
            }
        });
        // formatter for Production order operation
        frm.set_indicator_formatter('operation',
            function(doc) { return (frm.doc.qty == doc.completed_qty) ? "green" : "orange"; });
    },

    onload: function(frm) {
        if (frm.doc.docstatus != 1) {
            // var df = frappe.meta.get_docfield("Production Order Steps", "finish_the_step", frm.doc.name)
            // df.hidden = 1;
            // frm.refresh_fields();
            $('div[data-fieldname="production_steps"]').find('.grid-footer').hide()
        }
        if (!frm.doc.status)
            frm.doc.status = 'Draft';

        frm.add_fetch("sales_order", "project", "project");

        if (frm.doc.__islocal) {
            frm.set_value({
                "actual_start_date": "",
                "actual_end_date": ""
            });
            erpnext.production_order.set_default_warehouse(frm);
        }
    },

    source_warehouse: function(frm) {
        let transaction_controller = new erpnext.TransactionController();
        transaction_controller.autofill_warehouse(frm.doc.required_items, "source_warehouse", frm.doc.source_warehouse);
        transaction_controller.autofill_warehouse(frm.doc.scrap_items, "source_warehouse", frm.doc.source_warehouse);
    },

    refresh: function(frm) {
        if (frm.doc.docstatus != 1 || (frm.doc.docstatus == 1)) {
            // var df = frappe.meta.get_docfield("Production Order Steps", "finish_the_step", frm.doc.name)
            // df.hidden = 1;
            // frm.refresh_fields();
            $('div[data-fieldname="production_steps"]').find('.grid-footer').hide()
        }
        erpnext.toggle_naming_series();
        erpnext.production_order.set_custom_buttons(frm);
        frm.set_intro("");

        if (frm.doc.docstatus === 0 && !frm.doc.__islocal) {
            frm.set_intro(__("Submit this Production Order for further processing."));
        }

        if (frm.doc.docstatus === 1) {
            frm.trigger('show_progress_for_items');
            frm.trigger('show_progress_for_operations');
        }

        if (frm.doc.docstatus === 1 &&
            frm.doc.operations && frm.doc.operations.length &&
            frm.doc.qty != frm.doc.produced_qty) {

            const not_completed = frm.doc.operations.filter(d => {
                if (d.status != 'Completed') {
                    return true;
                }
            });

        }

        if (frm.doc.required_items && frm.doc.allow_alternative_item) {
            const has_alternative = frm.doc.required_items.find(i => i.allow_alternative_item === 1);
            if (frm.doc.docstatus == 0 && has_alternative) {
                frm.add_custom_button(__('Alternate Item'), () => {
                    erpnext.utils.select_alternate_items({
                        frm: frm,
                        child_docname: "required_items",
                        warehouse_field: "source_warehouse",
                        child_doctype: "Production Order Item",
                        original_item_field: "original_item",
                        condition: (d) => {
                            if (d.allow_alternative_item) { return true; }
                        }
                    });
                });
            }
        }
        if (frm.doc.scrap_items && frm.doc.allow_alternative_item) {
            const has_alternative = frm.doc.scrap.find(i => i.allow_alternative_item === 1);
            if (frm.doc.docstatus == 0 && has_alternative) {
                frm.add_custom_button(__('Alternate Item'), () => {
                    erpnext.utils.select_alternate_items({
                        frm: frm,
                        child_docname: "scrap",
                        warehouse_field: "source_warehouse",
                        child_doctype: "Production Order Item",
                        original_item_field: "original_item",
                        condition: (d) => {
                            if (d.allow_alternative_item) { return true; }
                        }
                    });
                });
            }
        }
        if (frm.doc.status == "Completed" &&
            frm.doc.__onload.backflush_raw_materials_based_on == "Material Transferred for Manufacture") {
            frm.add_custom_button(__('Create BOM'), () => {
                frm.trigger("make_bom");
            });
        }
    },

    make_bom: function(frm) {
        frappe.call({
            method: "make_bom",
            doc: frm.doc,
            callback: function(r) {
                if (r.message) {
                    var doc = frappe.model.sync(r.message)[0];
                    frappe.set_route("Form", doc.doctype, doc.name);
                }
            }
        });
    },

    show_progress_for_items: function(frm) {
        var bars = [];
        var message = '';
        var added_min = false;

        // produced qty
        var title = __('{0} items in production', [frm.doc.qty]);
        bars.push({
            'title': title,
            'width': (frm.doc.produced_qty) + '%',
            'progress_class': 'progress-bar-success'
        });
        if (bars[0].width == '0%') {
            bars[0].width = '0.5%';
            added_min = 0.5;
        }
        message = title;
        // pending qty
        if (!frm.doc.skip_transfer) {
            var pending_complete = frm.doc.material_transferred_for_manufacturing;
            if (pending_complete) {
                var width = ((pending_complete) - added_min);
                title = __('{0} % of items in progress', [flt(pending_complete, 2)]);
                bars.push({
                    'title': title,
                    'width': (width > 100 ? "99.5" : width) + '%',
                    'progress_class': 'progress-bar-warning'
                });
                if (frm.doc.produced_qty == 100) {
                    title = __('{0} % of items completed', [flt(frm.doc.produced_qty, 2)]);
                }
                message = message + '. ' + title;
            }
        }
        frm.dashboard.add_progress(__('Status'), bars, message);
    },

    show_progress_for_operations: function(frm) {
        if (frm.doc.operations && frm.doc.operations.length) {

            let progress_class = {
                "Work in Progress": "progress-bar-warning",
                "Completed": "progress-bar-success"
            };

            let bars = [];
            let message = '';
            let title = '';
            let status_wise_oprtation_data = {};
            let total_completed_qty = frm.doc.qty * frm.doc.operations.length;

            frm.doc.operations.forEach(d => {
                if (!status_wise_oprtation_data[d.status]) {
                    status_wise_oprtation_data[d.status] = [d.completed_qty, d.operation];
                } else {
                    status_wise_oprtation_data[d.status][0] += d.completed_qty;
                    status_wise_oprtation_data[d.status][1] += ', ' + d.operation;
                }
            });

            for (let key in status_wise_oprtation_data) {
                title = __("{0} Operations: {1}", [key, status_wise_oprtation_data[key][1].bold()]);
                bars.push({
                    'title': title,
                    'width': status_wise_oprtation_data[key][0] / total_completed_qty * 100 + '%',
                    'progress_class': progress_class[key]
                });

                message += title + '. ';
            }

            frm.dashboard.add_progress(__('Status'), bars, message);
        }
    },

    production_item: function(frm) {
        if (frm.doc.production_item) {
            frappe.call({
                method: "hampden.hampden.doctype.production_order.production_order.get_item_details",
                args: {
                    item: frm.doc.production_item,
                    project: frm.doc.project
                },
                freeze: true,
                callback: function(r) {
                    if (r.message) {
                        // frm.set_value('sales_order', "");
                        // frm.trigger('set_sales_order');
                        erpnext.in_production_item_onchange = true;

                        $.each(["description", "stock_uom", "bom_no", "allow_alternative_item",
                            "total_overhead", "scrap_material_cost", "total_labor",
                            "intrinsic_material_cost", "fabrication_cost", "cutting_loss_cost", "total_production_route", "raw_material_cost",
                            "total_cost", "transfer_material_against", "item_name", "production_route"
                        ], function(i, field) {
                            frm.set_value(field, r.message[field]);
                        });
                        if (r.message && r.message['production_steps']) {
                            frm.clear_table('production_steps')

                            r.message['production_steps'].forEach(step => {
                                frm.add_child('production_steps', step)
                            })
                            frm.refresh_field('production_steps')
                        }
                        if (r.message["set_scrap_wh_mandatory"]) {
                            frm.toggle_reqd("scrap_warehouse", true);
                        }

                        if (r.message && r.message['wip_warehouse']) {
                            frm.set_value('wip_warehouse', r.message['wip_warehouse']);
                        }
                        if (r.message && r.message['scrap_warehouse']) {
                            frm.set_value('scrap_warehouse', r.message['scrap_warehouse']);
                        }
                        if (r.message && r.message['target_warehouse']) {
                            frm.set_value('fg_warehouse', r.message['target_warehouse']);
                        }
                        frm.refresh_field('wip_warehouse')
                        frm.refresh_field('scrap_warehouse')
                        frm.refresh_field('fg_warehouse')

                        erpnext.in_production_item_onchange = false;
                    }
                }
            });
        }
    },

    project: function(frm) {
        if (!erpnext.in_production_item_onchange && !frm.doc.bom_no) {
            frm.trigger("production_item");
        }
    },

    bom_no: function(frm) {
        return frm.call({
            doc: frm.doc,
            method: "get_items_and_operations_from_bom",
            freeze: true,
            callback: function(r) {
                if (r.message["set_scrap_wh_mandatory"]) {
                    frm.toggle_reqd("scrap_warehouse", true);
                }
            }
        });
    },

    use_multi_level_bom: function(frm) {
        if (frm.doc.bom_no) {
            frm.trigger("bom_no");
        }
    },

    qty: function(frm) {
        frm.trigger('bom_no');
    },

    before_submit: function(frm) {
        frm.toggle_reqd(["fg_warehouse", "wip_warehouse"], true);
        frm.fields_dict.required_items.grid.toggle_reqd("source_warehouse", true);
        frm.fields_dict.scrap_items.grid.toggle_reqd("source_warehouse", true);
        frm.toggle_reqd("transfer_material_against",
            frm.doc.operations && frm.doc.operations.length > 0);
        frm.fields_dict.operations.grid.toggle_reqd("workstation", frm.doc.operations);
    },

    set_sales_order: function(frm) {
        if (frm.doc.production_item) {
            frappe.call({
                method: "hampden.hampden.doctype.production_order.production_order.query_sales_order",
                args: { production_item: frm.doc.production_item },
                callback: function(r) {
                    frm.set_query("sales_order", function() {
                        erpnext.in_production_item_onchange = true;
                        return {
                            filters: [
                                ["Sales Order", "name", "in", r.message]
                            ]
                        };
                    });
                }
            });
        }
    },

    additional_operating_cost: function(frm) {
        erpnext.production_order.calculate_cost(frm.doc);
        erpnext.production_order.calculate_total_cost(frm);
    }
});
frappe.ui.form.on("Production Order Steps", {
    finish_the_step: function(frm, cdt, cdn) {
        if (frm.doc.docstatus != 1) {
            frappe.throw('Please Submit Order before Update the Step!')
            return
        } else {
            const row = locals[cdt][cdn]
            if (row.date) {
                frappe.confirm(
                        'Are you sure to reset step?',
                        function() {
                            frappe.call({
                                    method: 'reset_production_step',
                                    doc: frm.doc,
                                    freeze: true,
                                    freeze_message: __("update date process starting"),
                                    args: {
                                        row: row.idx
                                    },
                                    callback: function(r) {
                                        if (!r.exc) {
                                            // frappe.throw("$$$")
                                            frm.reload_doc()
                                                // if (r.message && ['ERROR', 'RELOAD'].includes(r.message)) {
                                                // 	frm.reload_doc()
                                                // } else {
                                                // 	// if (row.issue_step) {
                                                // 	// 	var doclist = frappe.model.sync(r.message);
                                                // 	// 	frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                                                // 	// }
                                                // }
                                        }
                                    }
                                })
                                // window.close();
                        },
                        function() {
                            show_alert('Thanks for continue here!')
                        }
                    )
                    // frappe.throw('the step is completed!')
                return
            }
            frappe.call({
                method: 'update_production_step',
                doc: frm.doc,
                freeze: true,
                freeze_message: __("update date process starting"),
                args: {
                    row: row.idx
                },
                callback: function(r) {
                    if (!r.exc) {
                        if (r.message && ['ERROR', 'RELOAD'].includes(r.message)) {
                            frm.reload_doc()
                        } else {
                            if (row.issue_step) {
                                var doclist = frappe.model.sync(r.message);
                                frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                            }
                        }
                    }
                }
            })
        }

    }
});
frappe.ui.form.on("Production Order Item", {
    source_warehouse: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (!row.item_code) {
            frappe.throw(__("Please set the Item Code first"));
        } else if (row.source_warehouse) {
            frappe.call({
                "method": "erpnext.stock.utils.get_latest_stock_qty",
                args: {
                    item_code: row.item_code,
                    warehouse: row.source_warehouse
                },
                callback: function(r) {
                    frappe.model.set_value(row.doctype, row.name,
                        "available_qty_at_source_warehouse", r.message);
                }
            });
        }
    }
});
frappe.ui.form.on("Production Order Scrap", {
    source_warehouse: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (!row.item_code) {
            frappe.throw(__("Please set the Item Code first"));
        } else if (row.source_warehouse) {
            frappe.call({
                "method": "erpnext.stock.utils.get_latest_stock_qty",
                args: {
                    item_code: row.item_code,
                    warehouse: row.source_warehouse
                },
                callback: function(r) {
                    frappe.model.set_value(row.doctype, row.name,
                        "available_qty_at_source_warehouse", r.message);
                }
            });
        }
    }
});



erpnext.production_order = {
    set_custom_buttons: function(frm) {
        var doc = frm.doc;
        if (doc.docstatus === 1) {
            if (doc.status != 'Stopped' && doc.status != 'Completed') {
                frm.add_custom_button(__('Stop'), function() {
                    erpnext.production_order.stop_production_order(frm, "Stopped");
                }, __("Status"));
            } else if (doc.status == 'Stopped') {
                frm.add_custom_button(__('Re-open'), function() {
                    erpnext.production_order.stop_production_order(frm, "Resumed");
                }, __("Status"));
            }

            const show_start_btn = (frm.doc.skip_transfer ||
                frm.doc.transfer_material_against == 'Job Card') ? 0 : 1;

            if (show_start_btn) {
                if ((flt(doc.material_transferred_for_manufacturing) < flt(doc.qty)) &&
                    frm.doc.status != 'Stopped') {
                    frm.has_start_btn = true;

                    var start_btn = frm.add_custom_button(__('Start'), function() {
                        erpnext.production_order.make_se(frm, 'Material Transfer for Manufacture');
                    });
                    start_btn.addClass('btn-primary');
                }
            }

            if (!frm.doc.skip_transfer) {
                // If "Material Consumption is check in Manufacturing Settings, allow Material Consumption
                if ((flt(doc.produced_qty) < flt(doc.material_transferred_for_manufacturing)) &&
                    frm.doc.status != 'Stopped') {
                    frm.has_finish_btn = true;

                    if (frm.doc.__onload && frm.doc.__onload.material_consumption == 1) {
                        // Only show "Material Consumption" when required_qty > consumed_qty
                        var counter = 0;
                        var tbl = frm.doc.required_items || [];
                        var tbl_lenght = tbl.length;
                        for (var i = 0, len = tbl_lenght; i < len; i++) {
                            let wo_item_qty = frm.doc.required_items[i].transferred_qty || frm.doc.required_items[i].required_qty;
                            if (flt(wo_item_qty) > flt(frm.doc.required_items[i].consumed_qty)) {
                                counter += 1;
                            }
                        }

                        var tbl2 = frm.doc.scrap_items || [];
                        var tbl_lenght = tbl2.length;
                        for (var i = 0, len = tbl_lenght; i < len; i++) {
                            let wo_item_qty = frm.doc.scrap_items[i].transferred_qty || frm.doc.scrap_items[i].required_qty;
                            if (flt(wo_item_qty) > flt(frm.doc.scrap_items[i].consumed_qty)) {
                                counter += 1;
                            }
                        }
                        if (counter > 0) {
                            var consumption_btn = frm.add_custom_button(__('Material Consumption'), function() {
                                const backflush_raw_materials_based_on = frm.doc.__onload.backflush_raw_materials_based_on;
                                erpnext.production_order.make_consumption_se(frm, backflush_raw_materials_based_on);
                            });
                            consumption_btn.addClass('btn-primary');
                        }
                    }

                    // var finish_btn = frm.add_custom_button(__('Finish'), function () {
                    // 	frappe.call({
                    // 		method: 'finish_order_by_user',
                    // 		doc: frm.doc,
                    // 		callback: function (r) {
                    // 			if (!r.exc) {
                    // 				if (r.message && ['ERROR', 'RELOAD'].includes(r.message)) {
                    // 					frm.reload_doc()
                    // 				} else {
                    // 					if (row.issue_step) {
                    // 						var doclist = frappe.model.sync(r.message);
                    // 						frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                    // 					}
                    // 				}
                    // 			}
                    // 		}
                    // 	})
                    // });

                    // if (doc.material_transferred_for_manufacturing >= doc.qty) {
                    // 	// all materials transferred for manufacturing, make this primary
                    // 	finish_btn.addClass('btn-primary');
                    // }
                }
                if (frm.doc.status != 'Stopped' && frm.doc.status == 'Completed') {
                    var pay_btn = frm.add_custom_button(__('Sell Item'), function() {
                        if (frm.doc.sales_order) {
                            frappe.call({
                                method: 'create_sales_invoice',
                                doc: frm.doc,
                                callback: function(r) {
                                    console.log(r);
                                    if (!r.exc) {
                                        if (r.message) {
                                            var doclist = frappe.model.sync(r.message);
                                            console.log(doclist[0]);
                                            doclist[0].items[0].rate = flt(frm.doc.total_cost) + 100
                                            doclist[0].items[0].amount = (flt(frm.doc.total_cost) + 100) * flt(frm.doc.qty)

                                            frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                                        }
                                    }
                                }
                            })
                        } else {
                            let d = new frappe.ui.Dialog({
                                title: __('Select Customer'),
                                fields: [{
                                    "label": "Customer",
                                    "fieldname": "customer",
                                    "fieldtype": "Link",
                                    "reqd": 1,
                                    "options": "Customer"
                                }],
                                primary_action: function() {
                                    var data = d.get_values();
                                    frappe.call({
                                        method: "create_sales_invoice_with_customer",
                                        doc: frm.doc,
                                        args: {
                                            customer: data.customer
                                        },
                                        callback: function(r) {
                                            if (!r.exc) {
                                                if (r.message) {
                                                    d.hide();
                                                    frappe.set_route("Form", 'Sales Invoice', r.message)
                                                        // var doclist = frappe.model.sync(r.message);
                                                        // doclist[0].items[0].rate = flt(frm.doc.total_cost) + 100
                                                        // doclist[0].items[0].amount = (flt(frm.doc.total_cost) + 100) * flt(frm.doc.qty)

                                                    // frappe.set_route("Form", doclist[0].doctype, doclist[0].name)
                                                }
                                            }
                                        }
                                    });
                                },
                                primary_action_label: __('Create')
                            });
                            d.show();
                        }

                    });
                    pay_btn.addClass('btn-primary');
                }
                if (frm.doc.status != 'Stopped' && frm.doc.is_paid == 0) {
                    // var pay_btn = frm.add_custom_button(__('Make Journal Entry'), function () {
                    // 	frappe.call({
                    // 		method: 'create_jv_by_user',
                    // 		doc: frm.doc,
                    // 		callback: function (r) {
                    // 			if (!r.exc) {
                    // 				if (r.message && ['ERROR', 'RELOAD'].includes(r.message)) {
                    // 					frappe.msgprint("Journal Entry is Created!")
                    // 					frm.reload_doc()
                    // 				} else {
                    // 					if (row.issue_step) {
                    // 						var doclist = frappe.model.sync(r.message);
                    // 						frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                    // 					}
                    // 				}
                    // 			}
                    // 		}
                    // 	})
                    // });
                    // pay_btn.addClass('btn-primary');
                }
            } else {
                if ((flt(doc.produced_qty) < flt(doc.qty)) && frm.doc.status != 'Stopped') {
                    // var finish_btn = frm.add_custom_button(__('Finish'), function () {
                    // 	frappe.call({
                    // 		method: 'finish_order_by_user',
                    // 		doc: frm.doc,
                    // 		callback: function (r) {
                    // 			if (!r.exc) {
                    // 				if (r.message && ['ERROR', 'RELOAD'].includes(r.message)) {
                    // 					frm.reload_doc()
                    // 				} else {
                    // 					if (row.issue_step) {
                    // 						var doclist = frappe.model.sync(r.message);
                    // 						frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                    // 					}
                    // 				}
                    // 			}
                    // 		}
                    // 	})
                    // });
                    // finish_btn.addClass('btn-primary');
                }
            }
        }

    },
    calculate_cost: function(doc) {
        if (doc.operations) {
            var op = doc.operations;
            doc.planned_operating_cost = 0.0;
            for (var i = 0; i < op.length; i++) {
                var planned_operating_cost = flt(flt(op[i].hour_rate) * flt(op[i].time_in_mins) / 60, 2);
                frappe.model.set_value('Work Order Operation', op[i].name,
                    "planned_operating_cost", planned_operating_cost);
                doc.planned_operating_cost += planned_operating_cost;
            }
            refresh_field('planned_operating_cost');
        }
    },

    calculate_total_cost: function(frm) {
        let variable_cost = flt(frm.doc.actual_operating_cost) || flt(frm.doc.planned_operating_cost);
        frm.set_value("total_operating_cost", (flt(frm.doc.additional_operating_cost) + variable_cost));
    },

    set_default_warehouse: function(frm) {
        if (!(frm.doc.wip_warehouse || frm.doc.fg_warehouse)) {
            frappe.call({
                method: "hampden.hampden.doctype.production_order.production_order.get_default_warehouse",
                callback: function(r) {
                    if (!r.exe) {
                        frm.set_value("wip_warehouse", r.message.wip_warehouse);
                        frm.set_value("fg_warehouse", r.message.fg_warehouse);
                    }
                }
            });
        }
    },

    get_max_transferable_qty: (frm, purpose) => {
        let max = 0;
        if (frm.doc.skip_transfer) {
            max = flt(frm.doc.qty) - flt(frm.doc.produced_qty);
        } else {
            if (purpose === 'Manufacture') {
                max = flt(frm.doc.material_transferred_for_manufacturing) - flt(frm.doc.produced_qty);
            } else {
                max = flt(frm.doc.qty) - flt(frm.doc.material_transferred_for_manufacturing);
            }
        }
        return flt(max, precision('qty'));
    },

    show_prompt_for_qty_input: function(frm, purpose) {
        let max = this.get_max_transferable_qty(frm, purpose);
        return new Promise((resolve, reject) => {
            frappe.prompt({
                fieldtype: 'Float',
                label: __('Qty for {0}', [purpose]),
                fieldname: 'qty',
                description: __('Max: {0}', [max]),
                default: max
            }, data => {
                max += (frm.doc.qty * (frm.doc.__onload.overproduction_percentage || 0.0)) / 100;

                if (data.qty > max) {
                    frappe.msgprint(__('Quantity must not be more than {0}', [max]));
                    reject();
                }
                data.purpose = purpose;
                resolve(data);
            }, __('Select Quantity'), __('Create'));
        });
    },

    make_se: function(frm, purpose) {
        this.show_prompt_for_qty_input(frm, purpose)
            .then(data => {
                return frappe.xcall('hampden.hampden.doctype.production_order.production_order.finish', {
                    'production_order_id': frm.doc.name,
                    'purpose': purpose,
                    'qty': data.qty
                });
            }).then(stock_entry => {
                frappe.model.sync(stock_entry);
                frappe.set_route('Form', stock_entry.doctype, stock_entry.name);
            });

    },

    make_consumption_se: function(frm, backflush_raw_materials_based_on) {
        if (!frm.doc.skip_transfer) {
            var max = (backflush_raw_materials_based_on === "Material Transferred for Manufacture") ?
                flt(frm.doc.material_transferred_for_manufacturing) - flt(frm.doc.produced_qty) :
                flt(frm.doc.qty) - flt(frm.doc.produced_qty);
            // flt(frm.doc.qty) - flt(frm.doc.material_transferred_for_manufacturing);
        } else {
            var max = flt(frm.doc.qty) - flt(frm.doc.produced_qty);
        }

        frappe.call({
            method: "hampden.hampden.doctype.production_order.production_order.make_stock_entry",
            args: {
                "production_order_id": frm.doc.name,
                "purpose": "Material Consumption for Manufacture",
                "qty": max
            },
            callback: function(r) {
                var doclist = frappe.model.sync(r.message);
                frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
            }
        });
    },

    stop_production_order: function(frm, status) {
        frappe.call({
            method: "hampden.hampden.doctype.production_order.production_order.stop_unstop",
            args: {
                production_order: frm.doc.name,
                status: status
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value("status", r.message);
                    frm.reload_doc();
                }
            }
        });
    }
};