
frappe.ui.form.on('Purchase Receipt', {
	gold_lock: function (frm) {
		// 1 troy oz = 31.1035 gm
		// 14K = 14/24 of pure gold
		// 10K = 10/24 of pure gold
		let gm14k = ((flt(frm.doc.gold_lock) || 0) / 31.1035) * (14 / 24);
		let gm10k = ((flt(frm.doc.gold_lock) || 0) / 31.1035) * (10 / 24);
		frm.set_value("gm_14k", flt(gm14k));
		frm.set_value("gm_10k", flt(gm10k));
		// frm.trigger('update_items_rates')
	},
	silver_lock: function (frm) {
		// SS = Sterling Silver = 0.995 of pure silver
		let ss = (frm.doc.silver_lock / 31.1035) * .995;
		frm.set_value("ssgm", flt(ss));
		// frm.trigger('update_items_rates')
	},
	total_invoiced: function (frm) { frm.trigger('update_items_rates') },
	update_items_rates: function (frm) {
		// console.log('update_items_rates')
		frm.doc.items.forEach(row => {
			if (!row.is_dependent_item) {
				// let current_item_rate = 0
				// if (row.metal_type == '10K') {
				// 	row.rate = frm.doc.gm_10k || 0
				// 	current_item_rate = frm.doc.gm_10k || 0
				// 	row.amount = (row.rate || 0) * (row.qty || 1)
				// }
				// if (row.metal_type == '14K') {
				// 	row.rate = frm.doc.gm_14k
				// 	current_item_rate = frm.doc.gm_14k || 0
				// 	row.amount = (row.rate || 0) * (row.qty || 1)
				// }
				// if (row.metal_type == 'Silver') {
				// 	row.rate = frm.doc.ssgm
				// 	current_item_rate = frm.doc.ssgm || 0
				// 	row.amount = (row.rate || 0) * (row.qty || 1)
				// }
				// row.amount row= (row.rate || 0) * (row.qty || 1)
				// Update Linked Items
				frm.doc.items.forEach(drow => {

					if (drow.is_dependent_item && flt(drow.is_dependent_item || 1) == 1) {
						if (drow.link_to == row.item_code) {
							let current_item_amount = row.amount
							if(drow.qty && drow.qty!=0){
								const rate = ((frm.doc.total_invoiced || 0) - (current_item_amount || 0)) / (drow.qty || 1)
								drow.rate = rate
								drow.amount = (rate || 0) * (drow.qty || 1)
							}
						}
					}

				})
			}
		})
		let total = 0
		frm.doc.items.forEach(row => {
			total += row.amount || 0
		})
		frm.doc.total = total
		frm.refresh_fields()
	},
});

frappe.ui.form.on('Purchase Receipt Item', {
	rate: function (frm, cdt, cdn) {
		let item = frappe.get_doc(cdt, cdn);
		if (frm.doc.doctype == "Purchase Receipt") {
			if (!item.is_dependent_item) {
				frm.doc.items.forEach(row => {
					if (row.link_to == item.item_code) {
						row.qty = item.qty || 0
						const current_item_amount = (item.rate || 0) * (item.qty || 1)
						row.rate = ((frm.doc.total_invoiced || 0) - (current_item_amount || 0)) / (item.qty || 1)
					}
				})
				cur_frm.refresh_fields()
			}

			if (item.is_dependent_item && flt(item.is_dependent_item || 1) == 1) {
				frm.doc.items.forEach(row => {
					if (item.link_to == row.item_code) {
						row.qty = item.qty || 0
						const current_item_amount = (row.rate || 0) * (row.qty || 1)
						item.rate = ((frm.doc.total_invoiced || 0) - (current_item_amount || 0)) / (row.qty || 1)
					}
				})
				cur_frm.refresh_fields()
			}
		}
		frm.cscript.conversion_factor(frm.doc, cdt, cdn, true);
		frm.cscript.apply_pricing_rule(item, true);
	}
})