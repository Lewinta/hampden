// Copyright (c) 2021, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Ordered Items To Be Manufactured', {
	refresh: function (frm) {
		frm.disable_save()
	},
	fetch_items: function (frm) {
		console.log(frm.doc.from_date)
		frappe.call({
			method: "fetch_order_items",
			doc: frm.doc,
			args: {
				from_date: frm.doc.from_date || false,
				to_date: frm.doc.to_date || false,
				with_manu_items: frm.doc.include_manufactured_items || 0,
			},
			callback: function (r) {
				let result = r.message || []
					// console.log(r.message)
					frm.clear_table('customer_order_items')
					result.forEach(row => {
						frm.add_child('customer_order_items', {
							'customer_order': row['name'] || '',
							'item_code': row['item_code'] || '',
							'item_name': row['item_name'],
							'qty': row['qty'],
							'sales_order_item': row['soi'],
							'production_status': row['production_order']? 'Production Item' :''
						})
					})
					frm.refresh_field('customer_order_items')
			}
		})
	},
	create_production_orders: function (frm) {
		let items = []
		frm.doc.customer_order_items.forEach(row => {
			if(row.sales_order_item) items.push(row.sales_order_item)
		})
		frappe.call({
			method: "create_production_orders",
			doc: frm.doc,
			args: {
				items: items || []
			},
			freeze: true,
			freeze_message: __("Create Productions Orders"),
			callback: function (r) {
				if (r.message) {
					cur_frm.clear_table('customer_order_items')
					frm.refresh_field('customer_order_items')
					// frappe.msgprint(__(""))
				}
			}
		})
	}
});
