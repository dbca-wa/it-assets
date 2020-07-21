import os

from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.urls import reverse

from . import models
from rancher.models import Workload


@admin.register(models.Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent')
    ordering = ('-score',)

    def has_add_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.SystemAlias)
class SystemAliasAdmin(admin.ModelAdmin):
    list_display = ('name', 'system')
    ordering = ('name',)
    search_fields = ['name']

    def has_add_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.SystemEnv)
class SystemEnvAdmin(admin.ModelAdmin):
    list_display = ('name', )
    ordering = ('name',)

    def has_add_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.WebServer)
class WebServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'other_names', 'host')
    readonly_fields = ('other_names', '_apps')
    ordering = ('name',)
    list_filter = ('category',)

    app_change_url_name = 'admin:{}_{}_change'.format(models.WebApp._meta.app_label, models.WebApp._meta.model_name)

    def _apps(self, obj):
        if not obj:
            return ""
        else:
            apps = set()
            for location_server in models.WebAppLocationServer.objects.filter(server=obj):
                apps.add(location_server.location.app)

            return mark_safe("<pre>{}</pre>".format("\n".join("<A href='{}'>{}</A>".format(reverse(self.app_change_url_name, args=(app.id,)), app.name) for app in apps)))
    _apps.short_description = "Webapps"

    def has_add_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True


class ConfigureTxtMixin(object):
    def _configure_txt(self, obj):
        if not obj or not obj.configure_txt:
            return ""
        else:
            return format_html("""<A href="javascript:void" onclick="django.jQuery('#id_{0}_{1}').toggle();django.jQuery(this).html((django.jQuery(this).html() == 'Show')?'Hide':'Show')">Show</A>
<pre id="id_{0}_{1}" style="display:none">
{2}
</pre>""", obj.__class__.__name__, obj.pk, obj.configure_txt)
    _configure_txt.short_description = "Raw Configure"


class WebAppLocationMixin(object):
    workload_change_url_name = 'admin:{}_{}_change'.format(Workload._meta.app_label, Workload._meta.model_name)

    def _process_handler(self, obj):
        if not obj:
            return ""
        elif obj.forward_protocol:
            result = None
            for server in obj.servers.all():
                if server.rancher_workload:
                    url = reverse(self.workload_change_url_name, args=(server.rancher_workload.id,))
                    if result:
                        result = "{}\n<A href='{}'>{}://{}:{}{}</A><A href='{}' style='margin-left:50px' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(result,url,obj.get_forward_protocol_display(),server.server.name,server.port,obj.forward_path or "",server.rancher_workload.viewurl,server.rancher_workload.managementurl)
                    else:
                        result = "<A href='{}'>{}://{}:{}{}</A><A href='{}' style='margin-left:50px' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(url,obj.get_forward_protocol_display(),server.server.name,server.port,obj.forward_path or "",server.rancher_workload.viewurl,server.rancher_workload.managementurl)
                else:
                    if result:
                        result = "{}\n{}://{}:{}{}".format(result,obj.get_forward_protocol_display(),server.server.name,server.port,obj.forward_path or "")
                    else:
                        result = "{}://{}:{}{}".format(obj.get_forward_protocol_display(),server.server.name,server.port,obj.forward_path or "")
            return mark_safe("<pre>{}</pre>".format(result))
        elif obj.redirect:
            return format_html("<pre>{}</pre>",obj.redirect)
        elif obj.return_code:
            return format_html("<pre>return {}</pre>",obj.return_code)
        elif obj.refuse:
            return mark_safe("<pre>deny all</pre>")
        else:
            return ""
    _process_handler.short_description = "Process Handler"


class WebAppListenInline(ConfigureTxtMixin,admin.TabularInline):
    readonly_fields = ('app','listen_host','listen_port','https',"config_modified","config_changed_columns",'_configure_txt')
    fields = ('app','listen_host','listen_port','https',"config_modified","config_changed_columns",'_configure_txt')
    model = models.WebAppListen

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WebAppLocationInline(ConfigureTxtMixin,WebAppLocationMixin,admin.TabularInline):
    readonly_fields = ('app','location','location_type','auth_type','_configure_txt','cors_enabled',"_process_handler","config_modified","config_changed_columns")
    fields = ('app','location','location_type','auth_type','cors_enabled',"_process_handler","config_modified","config_changed_columns",'_configure_txt')
    model = models.WebAppLocation

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.WebApp)
class WebAppAdmin(ConfigureTxtMixin, admin.ModelAdmin):

    class RedirectToFilter(admin.SimpleListFilter):
        """Filter on True/False if an object has a value for redirect_to.
        """
        title = 'redirect to'
        parameter_name = 'redirect_to_boolean'

        def lookups(self, request, model_admin):
            return (
                ('true', 'True'),
                ('false', 'False'),
            )

        def queryset(self, request, queryset):
            if self.value() == 'true':
                return queryset.filter(redirect_to__isnull=False)
            if self.value() == 'false':
                return queryset.filter(redirect_to__isnull=True)

    list_display = ('name', 'system_alias', 'system_env', 'domain', 'auth_domain', '_redirect', 'config_modified')
    ordering = ('name',)
    list_filter = ('system_env', RedirectToFilter, ("system_alias__system", admin.RelatedOnlyFieldListFilter))
    readonly_fields = ('name', 'auth_domain', '_configure_txt', '_redirect', "config_modified", "config_changed_columns")
    fields = ("name", "domain", "system_alias", "system_env", "auth_domain", "_redirect", 'config_modified', 'config_changed_columns', "_configure_txt")
    search_fields = ['name']
    inlines = [WebAppListenInline, WebAppLocationInline]

    def _listens(self, obj):
        if not obj:
            return ""
        else:
            listens = [str(l) for l in obj.listens.all()]
            return format_html("<pre>{}</pre>", os.linesep.join(listens))
    _listens.short_description = "Listen"

    def _redirect(self, obj):
        if not obj:
            return ""
        if obj.redirect_to:
            return mark_safe("<A href='/admin/nginx/webapp/{0}/change/'>{1}{2}</A>".format(obj.redirect_to.id, obj.redirect_to, obj.redirect_path or ""))
        elif obj.redirect_to_other:
            if obj.redirect_path:
                return "{}{}".format(obj.redirect_to_other, obj.redirect_path)
            else:
                return obj.redirect_to_other
        else:
            return ""
    _redirect.short_description = "Redirect To"

    def has_add_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


class LocationAppListFitler(admin.RelatedOnlyFieldListFilter):
    pass


class WebAppLocationServerInline(admin.TabularInline):
    readonly_fields = ("user_added",)
    fields = ('server','port','user_added')
    model = models.WebAppLocationServer
    extra = 0

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(models.WebAppLocation)
class WebAppLocationAdmin(ConfigureTxtMixin,WebAppLocationMixin,admin.ModelAdmin):
    list_display = ('app', 'location','location_type','auth_type','cors_enabled',"_process_handler","config_modified")
    readonly_fields = ('app','location','location_type','auth_type','refuse','_configure_txt',"_process_handler","config_modified","config_changed_columns")
    fields = ('app','location','location_type','auth_type','refuse',"_process_handler","config_modified","config_changed_columns",'_configure_txt')
    ordering = ('app','location_type','location')

    list_filter = (("app",LocationAppListFitler),)
    inlines = [WebAppLocationServerInline]

    def has_delete_permission(self, request, obj=None):
        return False
