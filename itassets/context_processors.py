from django.conf import settings


def from_settings(request):
    """Inject variables from project settings into every template context.
    """
    return {
        'ENVIRONMENT_NAME': settings.ENVIRONMENT_NAME,
        'ENVIRONMENT_COLOUR': settings.ENVIRONMENT_COLOUR,
        'VERSION_NO': settings.VERSION_NO,
    }
