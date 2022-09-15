// Copyright (c) 2022, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Customer PO', {
	refresh: function(frm) {
		if (!frm.is_new() && frm.doc.docstatus == 1 && !frm.doc.sales_order){
			frm.add_custom_button(__('Create Sales Order'), function () {
				frm.trigger("create_sales_order");
			});
		}
	},
	create_sales_order: function(frm) {
		frappe.call({
			method: "create_sales_order",
			doc: frm.doc,
			callback: function(r){
				frappe.set_route("Form", "Sales Order", r.message.doc_name);
			}
		})

	}
});


frappe.ui.form.on('Customer PO Item', {
	qty: function(frm, cdt, cdn){
		let row = locals[cdt][cdn]
		let rate = row.rate	 || 0
		let qty = row.qty || 0
		row.amount = qty * rate
		frm.refresh_fields()
	},
	rate: function(frm, cdt, cdn){
		let row = locals[cdt][cdn]
		let rate = row.rate	 || 0
		let qty = row.qty || 0
		row.amount = qty * rate
		frm.refresh_fields()
	}
});
