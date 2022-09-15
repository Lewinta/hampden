// Copyright (c) 2021, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Hampden Settings', {
	refresh: function (frm) {
		['labor_account', 'overhead_account', 'creditor_account',
		'intrinsic_account', 'fabrication_account', 'cutting_loss_account', 'variance_account']
		.forEach(field => {
			frm.toggle_reqd(field, frm.doc.auto_jv)
		})
		
		frm.toggle_reqd('default_currency', frm.doc.auto_item_price)
		frm.toggle_reqd('default_price_list', frm.doc.auto_item_price)

		frm.set_query('default_price_list', function(doc) {
			return {
				filters: {
					"selling": 1
				}
			};
		});
	},
	auto_jv: function (frm) {
		['labor_account', 'overhead_account', 'creditor_account',
		'intrinsic_account', 'fabrication_account', 'cutting_loss_account', 'variance_account']
		.forEach(field => {
			frm.toggle_reqd(field, frm.doc.auto_jv)
		})
	},
	auto_item_price: function(frm){
		frm.toggle_reqd('default_currency', frm.doc.auto_item_price)
		frm.toggle_reqd('default_price_list', frm.doc.auto_item_price)
	},
	validate: function (frm) {

	},
	based_on_vr: function (frm) {
		frappe.call({
			doc: frm.doc,
			method: 'update_rates_with_valuation',
			callback: function (r) {
				console.log('DOOONNN')
			}
		})
	},
	based_on_lpr: function (frm) {
		frappe.call({
			doc: frm.doc,
			method: 'update_rates_with_last_purchase_rate',
			callback: function (r) {
				console.log('DOOONNN')
			}
		})
	}
});
