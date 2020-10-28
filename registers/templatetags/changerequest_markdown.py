from django import template

register = template.Library()


@register.filter(is_safe=True)
def change_markdown(obj, field):
    return obj.formatted_markdown(field)
