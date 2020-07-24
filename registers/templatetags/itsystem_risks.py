from django import template

register = template.Library()


@register.filter(is_safe=True)
def get_category_risk(obj, category):
    # Template filter tag to allow the ITSystem get_risk() method to be called in a template.
    return obj.get_risk(category)
