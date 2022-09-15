from __future__ import unicode_literals
from frappe import _


def get_data():
    return {
        'fieldname': 'production_order',
        'non_standard_fieldnames': {
			'Journal Entry': 'reference_name',
			'Payment Entry': 'reference_name',
		},
        'transactions': [
            {
                'label': _('Transactions'),
                'items': ['Stock Entry', 'Sales Invoice']
            },
            {
				'label': _('Payment'),
				'items': ['Journal Entry']
			}
        ]
    }
