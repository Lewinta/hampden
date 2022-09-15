erpnext.TransactionController.prototype.item_code = function (doc, cdt, cdn) {
    var me = this;
    var item = frappe.get_doc(cdt, cdn);
    var update_stock = 0, show_batch_dialog = 0;
    if (['Sales Invoice'].includes(this.frm.doc.doctype)) {
        update_stock = cint(me.frm.doc.update_stock);
        show_batch_dialog = update_stock;

    } else if ((this.frm.doc.doctype === 'Purchase Receipt' && me.frm.doc.is_return) ||
        this.frm.doc.doctype === 'Delivery Note') {
        show_batch_dialog = 1;
    }
    // clear barcode if setting item (else barcode will take priority)
    if (!this.frm.from_barcode) {
        item.barcode = null;
    }

    this.frm.from_barcode = false;
    if (item.item_code || item.barcode || item.serial_no) {
        if (!this.validate_company_and_party()) {
            this.frm.fields_dict["items"].grid.grid_rows[item.idx - 1].remove();
        } else {
            return this.frm.call({
                method: "hampden.api.get_item_details",
                child: item,
                args: {
                    doc: me.frm.doc,
                    args: {
                        item_code: item.item_code,
                        barcode: item.barcode,
                        serial_no: item.serial_no,
                        batch_no: item.batch_no,
                        set_warehouse: me.frm.doc.set_warehouse,
                        warehouse: item.warehouse,
                        customer: me.frm.doc.customer || me.frm.doc.party_name,
                        quotation_to: me.frm.doc.quotation_to,
                        supplier: me.frm.doc.supplier,
                        currency: me.frm.doc.currency,
                        update_stock: update_stock,
                        conversion_rate: me.frm.doc.conversion_rate,
                        price_list: me.frm.doc.selling_price_list || me.frm.doc.buying_price_list,
                        price_list_currency: me.frm.doc.price_list_currency,
                        plc_conversion_rate: me.frm.doc.plc_conversion_rate,
                        company: me.frm.doc.company,
                        order_type: me.frm.doc.order_type,
                        is_pos: cint(me.frm.doc.is_pos),
                        is_return: cint(me.frm.doc.is_return),
                        is_subcontracted: me.frm.doc.is_subcontracted,
                        transaction_date: me.frm.doc.transaction_date || me.frm.doc.posting_date,
                        ignore_pricing_rule: me.frm.doc.ignore_pricing_rule,
                        doctype: me.frm.doc.doctype,
                        name: me.frm.doc.name,
                        project: item.project || me.frm.doc.project,
                        qty: item.qty || 1,
                        metal_type: item.metal_type || '',
                        stock_qty: item.stock_qty,
                        conversion_factor: item.conversion_factor,
                        weight_per_unit: item.weight_per_unit,
                        weight_uom: item.weight_uom,
                        manufacturer: item.manufacturer,
                        stock_uom: item.stock_uom,
                        pos_profile: me.frm.doc.doctype == 'Sales Invoice' ? me.frm.doc.pos_profile : '',
                        cost_center: item.cost_center,
                        tax_category: me.frm.doc.tax_category,
                        item_tax_template: item.item_tax_template,
                        child_docname: item.name,
                        production_invoice: me.frm.doc.production_invoice || 0,
                        production_order: me.frm.doc.production_order || '',
                    }
                },

                callback: function (r) {
                    if (!r.exc) {
                        frappe.run_serially([
                            () => {
                                var d = locals[cdt][cdn];
                                me.add_taxes_from_item_tax_template(d.item_tax_rate);
                                if (d.free_item_data) {
                                    me.apply_product_discount(d.free_item_data);
                                }
                            },
                            () => me.frm.script_manager.trigger("price_list_rate", cdt, cdn),
                            () => {
                                // Update Current Row Rate Based On Metal Type!
                                if (me.frm.doc.doctype == "Purchase Receipt") {
                                    var d = locals[cdt][cdn];
                                    let d_rate = 0
                                    // if (d.metal_type == '14K') {
                                    //     d_rate = me.frm.doc.gm_14k || 0
                                    // }
                                    // if (d.metal_type == '10K') {
                                    //     d_rate = me.frm.doc.gm_10k || 0
                                    // }
                                    // if (d.metal_type == 'Silver') {
                                    //     d_rate = me.frm.doc.ssgm || 0
                                    // }
                                    d.rate = d_rate
                                    d.base_rate = d_rate
                                    d.qty = 0
                                    // Add Dependents list With Rate
                                    if (r.message && r.message.dependents_list) {
                                        r.message.dependents_list.forEach(deb_item => {
                                            const new_row = me.frm.add_child('items', {
                                                'item_code': deb_item.item_code
                                            })
                                            new_row.base_rate = deb_item.base_rate || 0
                                            new_row.rate = 0
                                            // if (flt(me.frm.doc.total_invoiced) != 0) {
                                            //     let deb_item_rate =   me.frm.doc.total_invoiced - (d.rate||0 * d.qty||1)
                                            //     deb_item_rate = deb_item_rate / (deb_item.qty || 1)
                                            //     new_row.rate = deb_item_rate
                                            // }

                                            new_row.actual_qty = deb_item.actual_qty
                                            new_row.base_price_list_rate = deb_item.base_price_list_rate || 0
                                            new_row.batch_no = deb_item.batch_no || ''
                                            new_row.brand = deb_item.brand || ''
                                            new_row.delivered_by_supplier = deb_item.delivered_by_supplier || 0
                                            new_row.cost_center = deb_item.cost_center || ''
                                            new_row.description = deb_item.description || ''
                                            new_row.discount_percentage = deb_item.discount_percentage || 0
                                            new_row.expense_account = deb_item.expense_account || ''
                                            new_row.gross_profit = deb_item.gross_profit || 0
                                            new_row.has_batch_no = deb_item.has_batch_no || 0
                                            new_row.has_serial_no = deb_item.has_serial_no || 0
                                            new_row.image = deb_item.image || ''
                                            new_row.income_account = deb_item.income_account || ''
                                            new_row.is_fixed_asset = deb_item.is_fixed_asset || 0
                                            new_row.item_group = deb_item.item_group || ''
                                            new_row.item_name = deb_item.item_name || ''
                                            new_row.last_purchase_rate = deb_item.last_purchase_rate || 0
                                            new_row.qty = 0
                                            new_row.manufacturer = deb_item.manufacturer || ''
                                            new_row.manufacturer_part_no = deb_item.manufacturer_part_no || ''
                                            new_row.price_list_rate = deb_item.price_list_rate || 0
                                            new_row.projected_qty = deb_item.projected_qty || 0
                                            new_row.reserved_qty = deb_item.reserved_qty || 0
                                            new_row.stock_qty = deb_item.stock_qty || 0
                                            new_row.stock_uom = deb_item.stock_uom || ''
                                            new_row.supplier = deb_item.supplier || ''
                                            new_row.supplier_part_no = deb_item.supplier_part_no || ''
                                            new_row.uom = deb_item.uom || ''
                                            new_row.update_stock = deb_item.update_stock || 0
                                            new_row.valuation_rate = deb_item.valuation_rate || 0
                                            new_row.warehouse = deb_item.warehouse || ''
                                            new_row.is_dependent_item = 1
                                            new_row.link_to = d.item_code || ''
                                        });
                                    }
                                }
                            },
                            () => me.toggle_conversion_factor(item),
                            () => {
                                if (show_batch_dialog && !item.has_serial_no
                                    && !item.has_batch_no) {
                                    show_batch_dialog = false;
                                }
                            },
                            () => {
                                if (show_batch_dialog)
                                    return frappe.db.get_value("Item", item.item_code, ["has_batch_no", "has_serial_no"])
                                        .then((r) => {
                                            if (r.message && !frappe.flags.hide_serial_batch_dialog &&
                                                (r.message.has_batch_no || r.message.has_serial_no)) {
                                                frappe.flags.hide_serial_batch_dialog = false;
                                            }
                                        });
                            },
                            () => {
                                if (show_batch_dialog && !frappe.flags.hide_serial_batch_dialog) {
                                    var d = locals[cdt][cdn];
                                    $.each(r.message, function (k, v) {
                                        if (!d[k]) d[k] = v;
                                    });

                                    if (d.has_batch_no && d.has_serial_no) {
                                        d.batch_no = undefined;
                                    }

                                    erpnext.show_serial_batch_selector(me.frm, d, (item) => {
                                        me.frm.script_manager.trigger('qty', item.doctype, item.name);
                                        if (!me.frm.doc.set_warehouse)
                                            me.frm.script_manager.trigger('warehouse', item.doctype, item.name);
                                    }, undefined, !frappe.flags.hide_serial_batch_dialog);
                                }
                            },
                            () => me.conversion_factor(doc, cdt, cdn, true),
                            () => me.remove_pricing_rule(item),
                            () => {
                                if (item.apply_rule_on_other_items) {
                                    let key = item.name;
                                    me.apply_rule_on_other_items({ key: item });
                                }
                            }
                        ]);
                    }
                }
            });
        }
    }
}

erpnext.TransactionController.prototype.qty = function (doc, cdt, cdn) {
    let item = frappe.get_doc(cdt, cdn);
    if (doc.doctype == "Purchase Receipt") {
        if (!item.is_dependent_item) {
            doc.items.forEach(row => {
                if (row.link_to == item.item_code) {
                    row.qty = item.qty || 0
                    const current_item_amount = (item.rate || 0) * (item.qty || 1)
                    row.rate = ((doc.total_invoiced || 0) - (current_item_amount || 0))  / (item.qty || 1)
                }
            })
            cur_frm.refresh_fields()
        }

        if (item.is_dependent_item && flt(item.is_dependent_item || 1) == 1) {
            doc.items.forEach(row => {
                if (item.link_to == row.item_code) {
                    row.qty = item.qty || 0
                    const current_item_amount = (row.rate || 0) * (row.qty || 1)
                    item.rate = ((doc.total_invoiced || 0) - (current_item_amount || 0)) / (row.qty || 1)
                }
            })
            cur_frm.refresh_fields()
        }
    }
    this.conversion_factor(doc, cdt, cdn, true);
    this.apply_pricing_rule(item, true);
}