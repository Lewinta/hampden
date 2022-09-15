import frappe

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_orders(doctype, txt, searchfield, start, page_len, filters):
	
    batch = filters.get("batch", False)
    if not batch:
        return []
    
    if not frappe.db.exists('Production Batch', batch):
        return []
    
    batch = frappe.get_doc('Production Batch', batch)
    steps = []

    for step in batch.production_steps:
        steps.append({
            'step': step.production_step,
            'issue':step.issue_step
        })
    
    result = []
    orders_with_route = frappe.db.sql(""" 
        SELECT po.name, po.production_item
        FROM `tabProduction Order` po
        WHERE po.docstatus = 1 AND po.status <> 'Completed'
        AND  ( po.name LIKE %(txt)s OR po.production_item LIKE %(txt)s )
        AND po.batch IS NULL
        ORDER BY po.name DESC
		LIMIT %(offset)s, %(limit)s
    """.format(searchfield), dict(
				txt="%{0}%".format(txt),
				offset=start,
				limit=page_len
			))
    for order in orders_with_route:
        order1 = frappe.get_doc('Production Order', order[0])
        if len(order1.production_steps) != len(steps):
            continue
        same = True
        for order_step in order1.production_steps:
            batch_step = steps[order_step.idx - 1]
            if (batch_step['step'] != order_step.production_step) or batch_step['issue'] != order_step.issue_step:
                same = False
        if same:
            result.append(order)

    return result