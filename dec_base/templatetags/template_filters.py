from django import template
register = template.Library()

@register.filter
def truefalse(value):
    '''
    Assumes
    '''
    if value == 'True':
        # Unicode character 'tick'
        return u'\u2713'
    else:
        # Unicode character 'cross'
        return u'\u2718'
