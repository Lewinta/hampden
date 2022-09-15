// Copyright (c) 2021, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Productions Monitor', {
	setup(frm) {
		frm.columns = ['Item', 'Production Order', 'Customer Order', 'Production Progress']
		frm.data = []
		frm.orderDetails = {}
		frm.activePage = 0
		frm.pageSize = 10
		frm.lastPage = 0
		frm.emptyMsg = `<h1 class="text-center text-muted"">No Production Order found</h1>`
		frm.lodadingMesasge = `<h1 class="text-center text-muted"">Loading Production Orders</h1>`
		frm.disable_save()
	},
	onload(frm) {
		var order_list_wrapper = $(frm.fields_dict['order_list'].wrapper);
		$(order_list_wrapper).html(frm.lodadingMesasge)
		return frappe.call({
			method: "frappe.client.get_count",
			args: {
				doctype: "Production Order",
				filters: {
					'docstatus': ["!=", 2]
				}
			},
			callback: function (r) {
				if (r.message) {
					const count = r.message || 0
					frm.lastPage = cint(count / frm.pageSize)
					frm.trigger('load_data')
				}
			}
		});

	},
	refresh(frm) {
		frm.activePage = 0
		frm.pageSize = 10
		// frm.add
		frm.trigger('refresh_data')
	},
	load_data(frm) {
		return frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Production Order",
				fields: ['production_item', 'name', 'sales_order', 'material_transferred_for_manufacturing', 'produced_qty', 'qty', 'status'],
				limit_start: frm.activePage * frm.pageSize,
				limit_page_length: frm.pageSize,
				order_by:"modified desc"
			},
			callback: function (r) {
				if (r.message) {
					frm.data = r.message.map(elm => {
						return {
							production_item: elm.production_item,
							produciton_order: elm.name,
							sales_order: elm.sales_order,
							trans_qty_percent: (elm.material_transferred_for_manufacturing/100 || 0) * 100 / flt(elm.qty),
							produced_qty_percent: (elm.produced_qty/100 || 0) * 100 / flt(elm.qty),
							qty: elm.qty
						}
					})
					frm.trigger('refresh_data')
				}
			}
		});
	},
	refresh_data(frm) {
		var order_list_wrapper = $(frm.fields_dict['order_list'].wrapper);
		if(frm.data.length == 0){
			$(order_list_wrapper).html(frm.emptyMsg)
			return
		}
		const $ths = frm.columns.map(col => {
			return `<th scope="col" class="text-center" style="border-bottom: 0;">${col}</th>`
		}).join('');

		const $trData = frm.data.map(tr => {
			const $tr = `<tr data-item="${tr['production_item']}" data-porder="${tr['produciton_order']}" data-corder="${tr['sales_order']}">
							<td><a class="clicked-href" href="" onclick="return">${tr['production_item']}</a></td>
							<td><a class="clicked-href" href="" onclick="return">${tr['produciton_order']}</a></td>
							<td><a class="clicked-href" href="" onclick="return">${tr['sales_order']}</a></td>
							<td>
							<div class="progress-display">
								<span class="completion mr-2">${flt(tr['trans_qty_percent'], 2)}%</span>
								<div>
								<div class="progress">
									<div class="progress-bar bg-warning" role="progressbar" aria-valuenow="${tr['trans_qty_percent']}" aria-valuemin="0" aria-valuemax="100" style="width: ${tr['trans_qty_percent']}%;"></div>
								</div>
								</div>
							</div>
							</td>
						</tr>`
			// $tr.onClick((e) => {
			// 	console.log($tr)
			// })
			return $tr
		}).join('')

		$(order_list_wrapper).html(`
		<div class="card">
			<div class="card-body tbl-header">
				<table class="table table-borderless text-center table-hover styled-table">
					<thead>
						<tr>
							${$ths}
						</tr>
					</thead>
					<tbody>
						${$trData}
					</tbody>
				</table>
			</div>
			<div class="card-footer text-muted">
				<nav aria-label="Page navigation example">
					<ul class="pagination justify-content-center pagination-sm">
					<li class="page-item page-prev-item ${frm.activePage == 0 ? "disabled" : ""}">
						<span class="page-link prev-link">Previous</span>
					</li>
					<li class="page-item page-next-item  ${frm.activePage == frm.lastPage ? "disabled" : ""}"">
						<span class="page-link next-link">Next</span>
					</li>
					</ul>
				</nav>
			</div>
		</div>`
		)
		$(order_list_wrapper).find('.prev-link').click((e) => {
			if (frm.activePage == 0) {
				$(order_list_wrapper).find('.page-prev-item').addClass('disabled')
				return
			}
			frm.activePage -= 1
			frm.trigger('load_data')
			frm.trigger('refresh_data')
		})
		$(order_list_wrapper).find('.next-link').click((e) => {
			//TODO(1): Load Count of Orders
			if (frm.activePage == frm.lastPage) {
				$(order_list_wrapper).find('.page-next-item').addClass('disabled')
				return
			}

			frm.activePage += 1
			frm.trigger('load_data')
			frm.trigger('refresh_data')
		})
		$(order_list_wrapper).find('tbody tr').click((e) => {
			return frappe.call({
				method: "hampden.api.get_production_details",
				args: {
					order: $(e.currentTarget).attr('data-porder')
				},
				callback: function (r) {
					if (r.message) {
						frm.details_html = ''

						r.message.forEach(data => {
							frm.details_html += get_value_as_html(data, data['value_type'], false)
						})
						frm.trigger('detials_wrapper')
					}
				}
			});
		})
		$(order_list_wrapper).find('tbody tr td .clicked-href').click((e) => {
			e.stopPropagation()
			console.log("CLICK", e, $(e.currentTarget).text())
		})
	},
	detials_wrapper(frm) {
		var order_details_wrapper = $(frm.fields_dict['order_details'].wrapper);
		$(order_details_wrapper).html(`
			${frm.details_html}
		`)
	}
});

function get_value_as_html(data, type, parent_type = false) {
	if (type == 'list') {
		const header_html = `<h6 class="heading-small text-muted mb-4">${data['label']}</h6>`
		let body_html = ''
		data['value'].forEach(v => {
			const field = get_value_as_html(v, v['value_type'], 'list')
			body_html += field
		})
		return `
			<div class="card card-padding">
				<div class="card-header">
				${header_html}
				</div>
				<div class="card-body">
					<div class="row">
					${body_html}
					</div>
				</div>
			</div>
			`
	} else if (type == 'table') {
		const header_html = `<h6 class="heading-small text-muted mb-4"><label class="form-control-label"">${data['label']}</label></h6>`
		let body_html = ''
		let thead = ''
		data['header'].forEach(v => {
			const field = `<td>${v}</td></td>`
			thead += field
		})
		data['value'].forEach(v => {
			const field = `<tr>
								<td>${v[0]}</td>
								<td>
									<span class="indicator whitespace-nowrap ${v[1]? 'green': 'orange'}">
										<span>${v[1]? 'Complete': 'In Process'}</span>
									</span>
								</td>
								<td>${v[2] || ''}</td>
								<td>${v[1]}</td>
							</tr>`
			body_html += field
		})
		return `
		<div class="col-sm-12">
			${header_html}
			<table class="table table-borderless text-center table-hover styled-table">
				<thead class="card-header">
					<tr>${thead}</tr>
				</thead>
				<tbody class="card-body">
					${body_html}
				</tbody>
			</table>
		</div>
			`
	} else if (type == 'str' && parent_type == 'table') {
		console.log("STR, TABLE");
	} else if (type == 'str' && parent_type == 'list') {
		console.log("STR, LIST");
		const html_prop = data['label'].replaceAll(' ', '-').toLowerCase()
		return `<div class="col-lg-6">
			<div class="form-group">
			<label class="form-control-label" for="${html_prop}">${data['label']}</label>
			<input type="text" id="${html_prop}" class="form-control" placeholder="${data['value']}" value="${data['value']}" disabled>
			</div>
		</div>`
	} else if (type == 'str') {
		const html_prop = data['label'].replaceAll(' ', '-').toLowerCase()
		return `<div class="col-lg-6">
			<div class="form-group">
			<label class="form-control-label" for="${html_prop}">${data['label']}</label>
			<input type="text" id="${html_prop}" class="form-control" placeholder="${data['value']}" value="${data['value']}" disabled>
			</div>
		</div>`
	}else if(type == 'br') {
		return `<div class="col-sm-12" style="border: 1px solid"></div>`
	}
}