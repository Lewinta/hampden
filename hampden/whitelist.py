from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cstr, flt
import json, copy

from six import string_types

from erpnext.controllers.item_variant import copy_attributes_to_variant

def make_variant_item_code(template_item_code, template_item_name, variant):
    """Uses template's item code and abbreviations to make variant's item code"""
    if variant.item_code:
        return
    ivs = frappe.get_doc('Item Variant Settings')
    add_dashes = ivs.add_dashes or 0
    include_temp_name = ivs.include_temp_name or 0

    abbreviations = []
    names = []
    for attr in variant.attributes:
        item_attribute = frappe.db.sql("""select i.numeric_values, v.abbr, IFNULL(v.attribute_short_value, '') as short_value, v.add_to_item_code
            from `tabItem Attribute` i left join `tabItem Attribute Value` v
                on (i.name=v.parent)
            where i.name=%(attribute)s and (v.attribute_value=%(attribute_value)s or i.numeric_values = 1)""", {
                "attribute": attr.attribute,
                "attribute_value": attr.attribute_value
            }, as_dict=True)

        if not item_attribute:
            continue
            # frappe.throw(_('Invalid attribute {0} {1}').format(frappe.bold(attr.attribute),
            #     frappe.bold(attr.attribute_value)), title=_('Invalid Attribute'),
            #     exc=InvalidItemAttributeValueError)

        abbr_or_value = cstr(attr.attribute_value) if item_attribute[0].numeric_values else item_attribute[0].abbr
        name = item_attribute[0].short_value if item_attribute[0].add_to_item_code else item_attribute[0].abbr
        names.append(name)
        abbreviations.append(abbr_or_value)
    
    added_from_name = False
    if names:
        dashes = ""
        temp_name = ""
        temp_dash = ""
        if add_dashes:
            dashes = "-"
        if include_temp_name:
            temp_name = template_item_code
            temp_dash = "-"
        variant.item_name = "{0}{1}{2}".format(temp_name,temp_dash, dashes.join(names))
    
    if abbreviations:
        dashes = ""
        temp_name = ""
        temp_dash = ""
        if add_dashes:
            dashes = "-"
        if include_temp_name:
            temp_name = template_item_code
            temp_dash = "-"
        variant.item_code = "{0}{1}{2}".format(temp_name,temp_dash, dashes.join(abbreviations))
    

@frappe.whitelist()
def create_variant(item, args):
    if isinstance(args, string_types):
        args = json.loads(args)

    template = frappe.get_doc("Item", item)
    variant = frappe.new_doc("Item")
    variant.variant_based_on = 'Item Attribute'
    variant_attributes = []

    for d in template.attributes:
        variant_attributes.append({
            "attribute": d.attribute,
            "attribute_value": args.get(d.attribute)
        })

    variant.set("attributes", variant_attributes)
    copy_attributes_to_variant(template, variant)
    make_variant_item_code(template.item_code, template.item_name, variant)

    return variant