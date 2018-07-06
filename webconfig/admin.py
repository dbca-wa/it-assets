from webconfig.models import Domain, FQDN, Site, Location
from django.contrib import admin


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(FQDN)
class FQDNAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'name', 'domain')
    search_fields = ('name', 'domain__name')
    list_filter = ('domain',)


class LocationInline(admin.TabularInline):
    model = Location


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    search_fields = ('fqdn__name', 'fqdn__domain__name')
    list_display = ('__str__', 'enabled', 'status', 'availability')
    list_filter = (
        'fqdn__domain', 'enabled', 'status', 'availability', 'allow_http', 'locations__auth_level',
        'locations__allow_cors', 'locations__allow_websockets')
    inlines = (LocationInline,)
    filter_horizontal = ('aliases',)
