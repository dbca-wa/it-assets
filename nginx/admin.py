import os
import urllib
from datetime import datetime,timedelta


from django.contrib import admin
from django.urls import path,reverse
from django.utils.html import format_html, mark_safe
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Q

from django_q.tasks import async_task

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
                return queryset.filter(Q(redirect_to__isnull=False) | Q(redirect_to_other__isnull=False))
            if self.value() == 'false':
                return queryset.filter(redirect_to__isnull=True,redirect_to_other__isnull=True)

    list_display = ('name', 'system_alias','system_env','domain','auth_domain','clientip_subnet','_redirect','config_modified','_daily_access_report')
    ordering = ('name',)
    list_filter = ('system_env','auth_domain','clientip_subnet', RedirectToFilter, ("system_alias__system", admin.RelatedOnlyFieldListFilter))
    readonly_fields = ('name','auth_domain','clientip_subnet','_configure_txt','_redirect',"config_modified","config_changed_columns","_daily_access_report")
    fields = ("name", "domain", "system_alias", "system_env", "auth_domain","clientip_subnet", "_redirect", 'config_modified', 'config_changed_columns', "_configure_txt","_daily_access_report")

    search_fields = ['name']
    inlines = [WebAppListenInline, WebAppLocationInline]

    def _listens(self, obj):
        if not obj:
            return ""
        else:
            listens = [str(l) for l in obj.listens.all()]
            return format_html("<pre>{}</pre>", os.linesep.join(listens))
    _listens.short_description = "Listen"

    dailyreport_list_url_name = 'admin:{}_{}_changelist'.format(models.WebAppAccessDailyReport._meta.app_label,models.WebAppAccessDailyReport._meta.model_name)
    def _daily_access_report(self,obj):
        if not obj :
            return ""
        else:
            return mark_safe("<A href='{0}?log_day=7d&q={1}'>7 days</A><A style='margin-left:20px' href='{0}?log_day=4w&q={1}'>4 weeks</A>".format(reverse(self.dailyreport_list_url_name),obj.name))
    _daily_access_report.short_description = "Daily Access Report"

    def _redirect(self,obj):
        if not obj :
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

@admin.register(models.RequestPathNormalizer)
class RequestPathNormalizerAdmin(admin.ModelAdmin):
    list_display = ('filter_code','order','changed','applied')
    readonly_fields = ('changed','applied')
    ordering = ('-order','filter_code')


@admin.register(models.RequestParameterFilter)
class RequestParameterFilterAdmin(admin.ModelAdmin):
    list_display = ('filter_code','included_parameters','excluded_parameters','case_insensitive','order','changed','applied')
    readonly_fields = ('changed','applied')
    ordering = ('-order','filter_code')

class LogDayFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Log day'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'log_day'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        
        obj = models.WebAppAccessLog.objects.all().order_by("-log_starttime").first()
        if not obj:
            return []

        last_log_day = timezone.localtime(obj.log_starttime).date()
        days = [last_log_day - timedelta(days=d)  for d in range(0,7)]
        return [(d.strftime("%Y-%m-%d"),d.strftime("%Y-%m-%d")) for d in days]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value() :
            return queryset.filter(log_starttime__gte=timezone.make_aware(datetime.strptime(self.value(),"%Y-%m-%d")),log_starttime__lt=timezone.make_aware(datetime.strptime(self.value(),"%Y-%m-%d")) + timedelta(days=1))
        else:
            return queryset

class DailyLogDayFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Log day'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'log_day'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        obj = model_admin.model.objects.all().order_by("-log_day").first()
        if not obj:
            return []

        last_log_day = obj.log_day
        days = [last_log_day - timedelta(days=d)  for d in range(0,7)]
        result = [(d.strftime("%Y-%m-%d"),d.strftime("%Y-%m-%d")) for d in days]
        result.append(("7d","Last 7 days"))
        result.append(("4w","Last 4 weeks"))
        return result


    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        val = self.value()
        if not val:
            return queryset
        elif val in ("7d","4w"):
            obj = queryset.model.objects.all().order_by("-log_day").first()
            if not obj:
                return queryset

            last_log_day = obj.log_day
            if val == "7d":
                start_day = (last_log_day - timedelta(days=6))
            else:
                start_day = (last_log_day - timedelta(days=27))
            return queryset.filter(log_day__gte=start_day)
        else:
            return queryset.filter(log_day=timezone.make_aware(datetime.strptime(self.value(),"%Y-%m-%d")).date())

class HttpStatusGroupFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Http Status Group'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'http_status_group'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [
            ("succeed","Succeed Requests"),
            ("unauthorized","Unauthorized Requests"),
            ("client_closed","Client Closed Requests"),
            ("error","Error Requests"),
            ("timeout","Timeout Requests"),
        ]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        val = self.value()
        if not val:
            return queryset
        elif val == "succeed":
            return queryset.filter(http_status__gt=0,http_status__lt=400)
        elif val == "unauthorized":
            return queryset.filter(http_status__in=(401,403))
        elif val == "timeout":
            return queryset.filter(http_status=408)
        elif val == "error":
            return queryset.filter(Q(http_status=0) | Q(http_status__gte=400)).exclude(http_status__in=(401,403,408,499))
        elif val == "client_closed":
            return queryset.filter(http_status=499)
        else:
            return queryset

class WebServerMixin(object):
    app_change_url_name = 'admin:{}_{}_change'.format(models.WebApp._meta.app_label,models.WebApp._meta.model_name)
    def _webserver(self,obj):
        if not obj:
            return ""
        elif not obj.webapp:
            return obj.webserver
        else:
            return mark_safe("<A href='{}'>{}</A>".format(reverse(self.app_change_url_name,args=(obj.webapp.id,)),obj.webserver))
    _webserver.short_description = "Webserver"


@admin.register(models.WebAppAccessDailyReport)
class WebAppAccessDailyReportAdmin(WebServerMixin,admin.ModelAdmin):
    list_display = ('log_day','_webserver','_requests','_success_requests','_error_requests','_unauthorized_requests','_timeout_requests','_client_closed_requests')
    readonly_fields = list_display
    ordering = ('-log_day','-requests',)

    list_filter = (DailyLogDayFilter,)

    search_fields = ['webserver']

    dailylog_list_url_name = 'admin:{}_{}_changelist'.format(models.WebAppAccessDailyLog._meta.app_label,models.WebAppAccessDailyLog._meta.model_name)
    def _requests(self,obj):
        if not obj:
            return ""
        elif obj.requests == 0:
            return "0"
        else:
            return mark_safe("<A href='{}?log_day={}&q={}'>{}</A>".format(reverse(self.dailylog_list_url_name),obj.log_day.strftime("%Y-%m-%d"),obj.webserver,obj.requests))
    _requests.short_description = "Requests"

    def _success_requests(self,obj):
        if not obj:
            return ""
        elif obj.success_requests == 0:
            return "0"
        else:
            return mark_safe("<A href='{}?log_day={}&q={}&http_status_group=succeed'>{}</A>".format(reverse(self.dailylog_list_url_name),obj.log_day.strftime("%Y-%m-%d"),obj.webserver,obj.success_requests))
    _success_requests.short_description = "Success Requests"

    def _error_requests(self,obj):
        if not obj:
            return ""
        elif obj.error_requests == 0:
            return "0"
        else:
            return mark_safe("<A href='{}?log_day={}&q={}&http_status_group=error'>{}</A>".format(reverse(self.dailylog_list_url_name),obj.log_day.strftime("%Y-%m-%d"),obj.webserver,obj.error_requests))
    _error_requests.short_description = "Error Requests"

    def _client_closed_requests(self,obj):
        if not obj:
            return ""
        elif obj.client_closed_requests == 0:
            return "0"
        else:
            return mark_safe("<A href='{}?log_day={}&q={}&http_status_group=client_closed'>{}</A>".format(reverse(self.dailylog_list_url_name),obj.log_day.strftime("%Y-%m-%d"),obj.webserver,obj.client_closed_requests))
    _client_closed_requests.short_description = "Client Closed Requests"

    def _unauthorized_requests(self,obj):
        if not obj:
            return ""
        elif obj.unauthorized_requests == 0:
            return "0"
        else:
            return mark_safe("<A href='{}?log_day={}&q={}&http_status_group=unauthorized'>{}</A>".format(reverse(self.dailylog_list_url_name),obj.log_day.strftime("%Y-%m-%d"),obj.webserver,obj.unauthorized_requests))
    _unauthorized_requests.short_description = "Unauthorized Requests"

    def _timeout_requests(self,obj):
        if not obj:
            return ""
        elif obj.timeout_requests == 0:
            return "0"
        else:
            return mark_safe("<A href='{}?log_day={}&q={}&http_status_group=timeout'>{}</A>".format(reverse(self.dailylog_list_url_name),obj.log_day.strftime("%Y-%m-%d"),obj.webserver,obj.timeout_requests))
    _timeout_requests.short_description = "Timeout Requests"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

class ResponseTimeMixin(object):
    def _max_response_time(self,obj):
        if not obj:
            return ""
        else:
            return round(obj.max_response_time,2)
    _max_response_time.short_description = "Max response time"

    def _min_response_time(self,obj):
        if not obj:
            return ""
        else:
            return round(obj.min_response_time,2)
    _min_response_time.short_description = "Min response time"

    def _avg_response_time(self,obj):
        if not obj:
            return ""
        else:
            return round(obj.avg_response_time,2)
    _avg_response_time.short_description = "Avg response time"

    def _total_response_time(self,obj):
        if not obj:
            return ""
        else:
            return round(obj.total_response_time,2)
    _total_response_time.short_description = "Total response time"


class RequestPathMixin(object):
    location_change_url_name = 'admin:{}_{}_change'.format(models.WebAppLocation._meta.app_label,models.WebAppLocation._meta.model_name)
    def _request_path(self,obj):
        if not obj:
            return ""
        elif not obj.webapplocation:
            return obj.request_path
        else:
            return mark_safe("<A href='{}'>{}</A>".format(reverse(self.location_change_url_name,args=(obj.webapplocation.id,)),obj.request_path))
    _request_path.short_description = "Request path"

class HttpStatusMixin(object):
    def _http_status(self,obj):
        if not obj:
            return ""
        elif obj.http_status == 0:
            return "Unknown"
        else:
            return obj.http_status
    _http_status.short_description = "Http Status"



@admin.register(models.WebAppAccessDailyLog)
class WebAppAccessDailyLogAdmin(HttpStatusMixin,ResponseTimeMixin,WebServerMixin,RequestPathMixin,admin.ModelAdmin):
    list_display = ('log_day','_webserver','_request_path','path_parameters','_http_status','_requests','_max_response_time','_min_response_time','_avg_response_time')
    readonly_fields = ('log_day','_webserver','_request_path','path_parameters','_http_status','_requests','_max_response_time','_min_response_time','_avg_response_time','all_path_parameters')
    ordering = ('-log_day','webserver','request_path',)

    list_filter = (DailyLogDayFilter,HttpStatusGroupFilter)

    search_fields = ['webserver']

    log_list_url_name = 'admin:{}_{}_changelist'.format(models.WebAppAccessLog._meta.app_label,models.WebAppAccessLog._meta.model_name)
    def _requests(self,obj):
        if not obj:
            return ""
        else:
            return mark_safe("<A href='{}?log_day={}&{}&request_path={}&http_status={}&{}'>{}</A>".format(
                reverse(self.log_list_url_name),
                obj.log_day.strftime("%Y-%m-%d"),
                "webserver={}".format(obj.webserver) if obj.webserver else "webserver__isnull=True",
                urllib.parse.quote(obj.request_path),
                obj.http_status,
                "path_parameters={}".format(urllib.parse.quote(obj.path_parameters)) if obj.path_parameters else "path_parameters__isnull=True",
                obj.requests))
    _requests.short_description = "Requests"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


    def has_add_permission(self, request, obj=None):
        return False




@admin.register(models.WebAppAccessLog)
class WebAppAccessLogAdmin(HttpStatusMixin,ResponseTimeMixin,WebServerMixin,RequestPathMixin,admin.ModelAdmin):
    list_display = ('_log_starttime','_webserver','_request_path','path_parameters','_http_status','requests','_max_response_time','_min_response_time','_avg_response_time')
    readonly_fields = ('_log_starttime','_log_endtime','_webserver','_request_path','path_parameters','_http_status','requests','_max_response_time','_min_response_time','_avg_response_time','all_path_parameters')
    ordering = ('-log_starttime','webserver','request_path',)

    search_fields = ['webserver']

    list_filter = (LogDayFilter,HttpStatusGroupFilter)

    def get_urls(self):
        urls = super().get_urls()
        urls = [
            path("run_log_harvesting/", self.run_log_harvesting, name="run_log_harvesting"),
        ] + urls
        return urls

    log_list_url_name = 'admin:{}_{}_changelist'.format(models.WebAppAccessLog._meta.app_label,models.WebAppAccessLog._meta.model_name)
    def run_log_harvesting(self,request):
        try:
            async_task("nginx.log_harvester.harvest")
            self.message_user(request, "A log havesting process has been scheduled.")
        except Exception as ex:
            self.message_user(request, "Failed to schedule the log harvesting process.{}".format(str(ex)),level=messages.ERROR)
        return redirect(self.log_list_url_name)

    def _log_starttime(self,obj):
        if not obj:
            return ""
        else:
            return timezone.localtime(obj.log_starttime).strftime("%Y-%m-%d %H:%M:%S")
    _log_starttime.short_description = "Log Starttime"

    def _log_endtime(self,obj):
        if not obj:
            return ""
        else:
            return timezone.localtime(obj.log_endtime).strftime("%Y-%m-%d %H:%M:%S")
    _log_endtime.short_description = "Log Endtime"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


    def has_add_permission(self, request, obj=None):
        return False
