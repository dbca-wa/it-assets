from django.contrib.admin import ModelAdmin
from django.utils.encoding import smart_text


class OimModelAdmin(ModelAdmin):
    """ OimModelAdmin"""

    def has_module_permission(self, request):
        user = request.user
        if user.is_superuser:
            return True

        if user.is_staff:
            if user.groups.filter(name="OIM Staff").exists():
                return True

        return False


def smart_truncate(content, length=100, suffix='....(more)'):
    """Small function to truncate a string in a sensible way, sourced from:
    http://stackoverflow.com/questions/250357/smart-truncate-in-python
    """
    content = smart_text(content)
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length + 1].split(' ')[0:-1]) + suffix
