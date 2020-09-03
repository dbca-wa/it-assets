import traceback
import logging

from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.utils import timezone

from django_q.tasks import async_task

# Register your models here.
from . import models
from . import rancher_harvester
from nginx.models import WebApp

logger = logging.getLogger(__name__)


class ClusterLinkMixin(object):
    cluster_change_url_name = 'admin:{}_{}_change'.format(models.Cluster._meta.app_label,models.Cluster._meta.model_name)
    get_cluster = staticmethod(lambda obj:obj.cluster)

    def _cluster(self,obj):
        if not obj :
            return ""
        else:
            cluster = self.get_cluster(obj)
            url = reverse(self.cluster_change_url_name, args=(cluster.id,))
            return mark_safe("<A href='{}'>{}</A>".format(url,cluster.name))
    _cluster.short_description = "Cluster"

class ProjectLinkMixin(object):
    project_change_url_name = 'admin:{}_{}_change'.format(models.Project._meta.app_label,models.Project._meta.model_name)
    get_project = staticmethod(lambda obj:obj.project)

    def _project(self,obj):
        if not obj :
            return ""
        else:
            project = self.get_project(obj)
            if project:
                url = reverse(self.project_change_url_name, args=(project.id,))
                return mark_safe("<span style='white-space:nowrap;'><A href='{2}' target='manage_workloads'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{0}' style='margin-left:5px'>{1}</A></span>".format(url,project.name or project.projectid,project.managementurl))
            else:
                return ""
    _project.short_description = "Project"

    def _projectid(self,obj):
        if not obj :
            return ""
        else:
            project = self.get_project(obj)
            if project:
                return mark_safe("{0}<A href='{1}' style='margin-left:20px' target='manage_workloads'><img src='/static/img/view.jpg' width=16 height=16></A>".format(project.projectid,project.managementurl))
            else:
                return ""
    _projectid.short_description = "Projectid"

    def _projectid_with_link(self,obj):
        return self._project(obj)
    _projectid_with_link.short_description = "Projectid"

class NamespaceLinkMixin(object):
    namespace_change_url_name = 'admin:{}_{}_change'.format(models.Namespace._meta.app_label,models.Namespace._meta.model_name)
    get_namespace = staticmethod(lambda obj:obj.namespace)
    def _namespace(self,obj):
        if not obj :
            return ""
        else:
            namespace = self.get_namespace(obj)
            url = reverse(self.namespace_change_url_name, args=(namespace.id,))
            return mark_safe("<A href='{}'>{}</A>".format(url,namespace.name))
    _namespace.short_description = "Namespace"


class VolumeLinkMixin(object):
    volume_change_url_name = 'admin:{}_{}_change'.format(models.PersistentVolume._meta.app_label,models.PersistentVolume._meta.model_name)
    get_volume = staticmethod(lambda obj:obj.volume)
    def _volume(self,obj):
        if not obj or not obj.volume:
            return ""
        else:
            volume = self.get_volume(obj)
            url = reverse(self.volume_change_url_name, args=(volume.id,))
            return mark_safe("<A href='{}'>volume</A>".format(url))
    _volume.short_description = "Volume"


class DatabaseLinkMixin(object):
    database_change_url_name = 'admin:{}_{}_change'.format(models.Database._meta.app_label,models.Database._meta.model_name)
    get_database = staticmethod(lambda obj:obj.database)
    def _database(self,obj):
        if not obj :
            return ""
        else:
            database = self.get_database(obj)
            url = reverse(self.database_change_url_name, args=(database.id,))
            return mark_safe("<A href='{}'>{}</A>".format(url,database.name))
    _database.short_description = "Database"


class ContainersLinkMixin(object):
    containers_url_name = 'admin:{}_{}_changelist'.format(models.Container._meta.app_label,models.Container._meta.model_name)
    def _containers(self,obj):
        if not obj :
            return ""
        else:
            url = reverse(self.containers_url_name, args=[])
            return mark_safe("<A href='{}?workload__id__exact={}'>Containers</A>".format(url,obj.id))
    _containers.short_description = "Containers"

class ContainerLinkMixin(object):
    container_url_name = 'admin:{}_{}_change'.format(models.Container._meta.app_label,models.Container._meta.model_name)
    def _container(self,obj):
        if not obj :
            return ""
        else:
            url = reverse(self.container_url_name, args=[obj.container.id])
            return mark_safe("<A href='{}?container__id__exact={}'>{} ({})</A>".format(url,obj.container.workload.name,obj.container.containerid,timezone.localtime(obj.container.started).strftime("%Y-%m-%d %H:%M:%S") if obj.container.started else ""))
    _container.short_description = "Container"

    def _container_short(self,obj):
        if not obj :
            return ""
        else:
            url = reverse(self.container_url_name, args=[obj.container.id])
            return mark_safe("<A href='{}?container__id__exact={}'>{} ({})</A>".format(url,obj.container.id,obj.container.workload.name,timezone.localtime(obj.container.started).strftime("%Y-%m-%d %H:%M:%S") if obj.container.started else ""))
    _container.short_description = "Container"

class LogsLinkMixin(object):
    logs_url_name = 'admin:{}_{}_changelist'.format(models.ContainerLog._meta.app_label,models.ContainerLog._meta.model_name)
    def _logs(self,obj):
        if not obj or not obj.log:
            return ""
        else:
            url = reverse(self.logs_url_name, args=[])
            if obj.warning and obj.error:
                return mark_safe("<A href='{0}?container__id__exact={1}'>Logs</A><A style='margin-left:5px' href='{0}?container__id__exact={1}&level={2}'>Errors</A><A style='margin-left:5px' href='{0}?container__id__exact={1}&level={3}'>Warnings</A>".format(url,obj.id,models.ContainerLog.ERROR,models.ContaienrLog.WARNING))
            elif obj.warning:
                return mark_safe("<A href='{0}?container__id__exact={1}'>Logs</A><A style='margin-left:5px' href='{0}?container__id__exact={1}&level={2}'>Warnings</A>".format(url,obj.id,models.ContaienrLog.WARNING))
            elif obj.error:
                return mark_safe("<A href='{0}?container__id__exact={1}'>Logs</A><A style='margin-left:5px' href='{0}?container__id__exact={1}&level={2}'>Errors</A>".format(url,obj.id,models.ContainerLog.ERROR))
            else:
                return mark_safe("<A href='{0}?container__id__exact={1}'>Logs</A>".format(url,obj.id))
    _logs.short_description = "Logs"

class WorkloadsLinkMixin(object):
    workloads_url_name = 'admin:{}_{}_changelist'.format(models.Workload._meta.app_label,models.Workload._meta.model_name)
    def _workloads(self,obj):
        if not obj :
            return ""
        else:
            workloads = obj.active_workloads + obj.deleted_workloads
            if workloads:
                url = reverse(self.workloads_url_name, args=[])
                if obj.__class__ == models.Cluster:
                    return mark_safe("<A href='{}?cluster__id__exact={}'>{}</A>".format(url,obj.id,workloads))
                elif obj.__class__ == models.Project:
                    return mark_safe("<A href='{}?project__id__exact={}'>{}</A>".format(url,obj.id,workloads))
                elif obj.__class__ == models.Namespace:
                    return mark_safe("<A href='{}?namespace__id__exact={}'>{}</A>".format(url,obj.id,workloads))
                else:
                    return workloads
            else:
                return "0"
    _workloads.short_description = "Workloads"

    def _active_workloads(self,obj):
        if not obj :
            return ""
        else:
            workloads = obj.active_workloads
            if workloads:
                url = reverse(self.workloads_url_name, args=[])
                if obj.__class__ == models.Cluster:
                    return mark_safe("<A href='{}?cluster__id__exact={}&deleted__isnull=True'>{}</A>".format(url,obj.id,workloads))
                elif obj.__class__ == models.Project:
                    return mark_safe("<A href='{}?project__id__exact={}&deleted__isnull=True'>{}</A>".format(url,obj.id,workloads))
                elif obj.__class__ == models.Namespace:
                    return mark_safe("<A href='{}?namespace__id__exact={}&deleted__isnull=True'>{}</A>".format(url,obj.id,workloads))
                else:
                    return workloads
            else:
                return "0"
    _active_workloads.short_description = "Acrive Workloads"

    def _deleted_workloads(self,obj):
        if not obj :
            return ""
        else:
            workloads = obj.deleted_workloads
            if workloads:
                url = reverse(self.workloads_url_name, args=[])
                if obj.__class__ == models.Cluster:
                    return mark_safe("<A href='{}?cluster__id__exact={}&deleted__isnull=False'>{}</A>".format(url,obj.id,workloads))
                elif obj.__class__ == models.Project:
                    return mark_safe("<A href='{}?project__id__exact={}&deleted__isnull=False'>{}</A>".format(url,obj.id,workloads))
                elif obj.__class__ == models.Namespace:
                    return mark_safe("<A href='{}?namespace__id__exact={}&deleted__isnull=False'>{}</A>".format(url,obj.id,workloads))
                else:
                    return workloads
            else:
                return "0"
    _deleted_workloads.short_description = "Deleted Workloads"

class WorkloadLinkMixin(object):
    workload_change_url_name = 'admin:{}_{}_change'.format(models.Workload._meta.app_label,models.Workload._meta.model_name)
    get_workload = staticmethod(lambda obj:obj.workload)
    def _workload(self,obj):
        if not obj :
            return ""
        else:
            workload = self.get_workload(obj)
            url = reverse(self.workload_change_url_name, args=(workload.id,))
            if workload.is_deleted or workload.added_by_log:
                return mark_safe("<A href='{}'>{}({})</A>".format(url,workload.name,workload.kind))
            else:
                return mark_safe("<A href='{3}' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{4}' target='manage_workload' style='margin-left:5px'><img src='/static/img/setting.jpg' width=16 height=16></A><A href='{0}' style='margin-left:5px'>{1}({2})</A>".format(url,workload.name,workload.kind,workload.viewurl,workload.managementurl))
    _workload.short_description = "Workload"

    def _manage(self,obj):
        if not obj :
            return ""
        else:
            workload = self.get_workload(obj)
            if workload.is_deleted or workload.added_by_log:
                return ""
            else:
                return mark_safe("<A href='{}' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(workload.viewurl,workload.managementurl))
    _manage.short_description = ""

    def _name(self,workload):
        if not workload :
            return ""
        elif workload.is_deleted or workload.added_by_log:
            return workload.name
        else:
            return mark_safe("{}<A href='{}' style='margin-left:20px' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(workload.name,workload.viewurl,workload.managementurl))
    _name.short_description = "Name"

    def _name_with_link(self,obj):
        if not obj :
            return ""
        else:
            workload = self.get_workload(obj)
            url = reverse(self.workload_change_url_name, args=(workload.id,))
            if workload.is_deleted or workload.added_by_log:
                return mark_safe("<A href='{}'>{}</A>".format(url,workload.name))
            else:
                return mark_safe("<A href='{2}' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{3}' target='manage_workload' style='margin-left:5px'><img src='/static/img/setting.jpg' width=16 height=16></A><A href='{0}' style='margin-left:5px'>{1}</A>".format(url,workload.name,workload.viewurl,workload.managementurl))
    _name_with_link.short_description = "Name"


class WorkloadInlineMixin(ClusterLinkMixin,ProjectLinkMixin,NamespaceLinkMixin,WorkloadLinkMixin):
    readonly_fields = ('_workload','_cluster','_project','_namespace','user',"password",'config_items')
    fields = readonly_fields
    ordering = ('workload',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Cluster)
class ClusterAdmin(WorkloadsLinkMixin,admin.ModelAdmin):
    list_display = ('name','ip', 'clusterid','_workloads','_active_workloads','_deleted_workloads','succeed_resources','failed_resources','refreshed','modified','added_by_log')
    readonly_fields = ('ip','clusterid','_workloads','_active_workloads','_deleted_workloads','succeed_resources','failed_resources','refreshed','modified','created','added_by_log','_refresh_message')
    ordering = ('name',)
    actions = ('refresh','enforce_refresh')

    def _refresh_message(self,obj):
        if not obj :
            return ""
        else:
            return mark_safe("<pre>{}</pre>".format(obj.refresh_message))
    _refresh_message.short_description = "Refresh Message"

    def has_add_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def enforce_refresh(self, request, queryset):
        for cluster in queryset:
            try:
                async_task("rancher.rancher_harvester.harvest",cluster,reconsume=True)
                self.message_user(request, "The process to harvest all configuration files of the cluster({}) has been scheduled.".format(cluster))
            except Exception as ex:
                self.message_user(request, "Failed to schedule the process to harvest all configuration files of the cluster({}).{}".format(cluster,str(ex)),level=messages.ERROR)

    enforce_refresh.short_description = 'Enforce refresh'

    def refresh(self, request, queryset):
        for cluster in queryset:
            try:
                async_task("rancher.rancher_harvester.harvest",cluster)
                self.message_user(request, "The process to harvest the changed configuration files of the cluster({}) has been scheduled.".format(cluster))
            except Exception as ex:
                self.message_user(request, "Failed to schedule the process to harvest the changed configuration files of the cluster({}).{}".format(cluster,str(ex)),level=messages.ERROR)

    refresh.short_description = 'Refresh'

class DeletedMixin(object):
    def _deleted(self,obj):
        if not obj :
            return ""
        elif obj.deleted:
            return mark_safe("<img src='/static/admin/img/icon-yes.svg'> {}".format(timezone.localtime(obj.deleted).strftime("%Y-%m-%d %H:%M:%S")))
        else:
            return mark_safe("<img src='/static/admin/img/icon-no.svg'>")
    _deleted.short_description = "Deleted"


@admin.register(models.Project)
class ProjectAdmin(ClusterLinkMixin,ProjectLinkMixin,WorkloadsLinkMixin,admin.ModelAdmin):
    list_display = ('_projectid_with_link','_cluster','name','_workloads','_active_workloads','_deleted_workloads')
    readonly_fields = ('_projectid','_cluster','_workloads','_active_workloads','_deleted_workloads')
    fields = ('_projectid','_cluster','name','_workloads','_active_workloads','_deleted_workloads')
    ordering = ('cluster__name','name',)
    list_filter = ('cluster',)
    list_display_links = None

    get_project = staticmethod(lambda obj:obj)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadInline(DeletedMixin,WorkloadLinkMixin,admin.TabularInline):
    model = models.Workload
    readonly_fields = ('_name_with_link', 'kind','image',"suspend","modified","_deleted")
    fields = readonly_fields
    ordering = ('name',)
    get_workload = staticmethod(lambda obj:obj)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class ExistingStatusFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Existing Status'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'existing_status'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [("living","Living"),("deleted","Deleted"),("added_by_log","Added by Log")]


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
        elif val == 'living':
            return queryset.filter(deleted__isnull=True)
        elif val == "deleted":
            return queryset.filter(deleted__isnull=False)
        elif val == "added_by_log":
            return queryset.filter(added_by_log=True)
        else:
            return queryset

@admin.register(models.Namespace)
class NamespaceAdmin(DeletedMixin,ClusterLinkMixin,WorkloadsLinkMixin,ProjectLinkMixin,admin.ModelAdmin):
    list_display = ('name','_cluster','_project',"_workloads",'_active_workloads','_deleted_workloads','_deleted',"added_by_log")
    readonly_fields = ('name','_cluster','_project',"_workloads",'_active_workloads','_deleted_workloads','_deleted',"added_by_log")
    fields = readonly_fields
    ordering = ('cluster__name','project__name','name')
    list_filter = ('project',ExistingStatusFilter)

    inlines = [WorkloadInline]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class WorkloadVolumeInline(DeletedMixin,WorkloadInlineMixin,admin.TabularInline):
    model = models.WorkloadVolume
    readonly_fields = ('_workload','_cluster','_project','_namespace','_deleted')
    fields = readonly_fields
    ordering = ('workload',)
    get_cluster = staticmethod(lambda obj:obj.workload.cluster)
    get_project = staticmethod(lambda obj:obj.workload.project)
    get_namespace = staticmethod(lambda obj:obj.workload.namespace)


@admin.register(models.PersistentVolume)
class PersistentVolumeAdmin(DeletedMixin,ClusterLinkMixin,admin.ModelAdmin):
    list_display = ('name','_cluster', 'kind','storage_class_name','volumepath','_capacity','writable',"modified",'_deleted')
    readonly_fields = ('name','_cluster', 'kind','storage_class_name','volumepath','_capacity',"volume_mode","uuid",'writable','reclaim_policy','_node_affinity',"modified","created",'_deleted')
    ordering = ('cluster','name',)
    list_filter = ('cluster',ExistingStatusFilter)
    inlines = [WorkloadVolumeInline]

    def _capacity(self,obj):
        if not obj :
            return ""
        if obj.capacity > 1024:
            if obj.capacity % 1024 == 0:
                return "{}G".format(int(obj.capacity / 1024))
            else:
                return "{}G".format(round(obj.capacity / 1024),2)
        else:
            return "{}M".format(obj.capacity)
    _capacity.short_description = "Capacity"

    def _node_affinity(self,obj):
        if not obj :
            return ""
        else:
            return mark_safe("<pre>{}</pre>".format(obj.node_affinity))
    _node_affinity.short_description = "Node Affinity"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadEnvInline(admin.TabularInline):
    readonly_fields = ('name','value','modified','created')
    fields = ('name','value','modified')
    model = models.WorkloadEnv
    classes = ["collapse"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadListeningInline(DeletedMixin,admin.TabularInline):
    readonly_fields = ('_listen','protocol','container_port','modified','_deleted')
    fields = ('_listen','protocol','container_port','modified','_deleted')
    model = models.WorkloadListening
    classes = ["collapse"]

    def _listen(self,obj):
        if not obj :
            return ""
        else:
            return obj.listen
    _listen.short_description = "Listen"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadVolumeInline(DeletedMixin,VolumeLinkMixin,admin.TabularInline):
    readonly_fields = ('name','mountpath','subpath','writable','volumepath','_capacity','_volume','_other_config','_deleted')
    fields = ('name','mountpath','subpath','writable','volumepath','_capacity','_volume','_other_config','_deleted')
    model = models.WorkloadVolume
    classes = ["collapse"]

    def _other_config(self,obj):
        if not obj :
            return ""
        elif obj.other_config:
            return mark_safe("<pre>{}</pre>".format(obj.other_config))
        else:
            return ""
    _other_config.short_description = "Other Config"

    def _capacity(self,obj):
        if not obj or not obj.volume:
            return ""
        else:
            return "{}G".format(obj.volume.capacity)
    _capacity.short_description = "Capacity"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadDatabaseInline1(DeletedMixin,DatabaseLinkMixin,admin.TabularInline):
    model = models.WorkloadDatabase
    readonly_fields = ('_server','_port','_database','schema','user',"password",'config_items','_deleted')
    fields = readonly_fields
    ordering = ('workload',)

    def _server(self,obj):
        if not obj :
            return ""
        else:
            return obj.database.server.host
    _server.short_description = "Server"

    def _port(self,obj):
        if not obj :
            return ""
        else:
            return obj.database.server.port
    _port.short_description = "Port"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Workload)
class WorkloadAdmin(DeletedMixin,ClusterLinkMixin, ProjectLinkMixin, NamespaceLinkMixin, WorkloadLinkMixin,ContainersLinkMixin, admin.ModelAdmin):
    list_display = ('_name_with_link', '_cluster', '_project', '_namespace', 'kind', 'image', '_image_vulns_str','_containers', 'modified','_deleted',"added_by_log")
    list_display_links = None
    readonly_fields = ('_name', '_cluster', '_project', '_namespace', 'kind', 'image', '_webapps','_containers', 'modified',"suspend","added_by_log")
    fields = ('_name', '_cluster', '_project', '_namespace', 'kind', 'image', '_image_vulns_str', 'image_scan_timestamp', '_webapps','_containers',"suspend", 'modified','_deleted',"added_by_log")
    ordering = ('cluster__name', 'project__name', 'namespace__name', 'name',)
    list_filter = ('cluster',ExistingStatusFilter,"kind", 'namespace')
    search_fields = ['name', 'project__name', 'namespace__name']
    get_workload = staticmethod(lambda obj: obj)

    inlines = [WorkloadDatabaseInline1, WorkloadListeningInline, WorkloadEnvInline, WorkloadVolumeInline]
    webapp_change_url_name = 'admin:{}_{}_change'.format(WebApp._meta.app_label, WebApp._meta.model_name)

    def _webapps(self, obj):
        if not obj:
            return ""
        else:
            apps = obj.webapps
            if apps:
                result = None
                for app in apps:
                    url = reverse(self.webapp_change_url_name, args=(app.id,))
                    if result:
                        result = "{}\n<A href='{}'>{}</A>".format(result, url, app.name)
                    else:
                        result = "<A href='{}'>{}</A>".format(url, app.name)
                return mark_safe("<pre>{}</pre>".format(result))
            else:
                return ""
    _webapps.short_description = "Web Applications"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadDatabaseInline2(DeletedMixin,WorkloadInlineMixin,admin.TabularInline):
    model = models.WorkloadDatabase
    readonly_fields = ('_workload','_cluster','_project','_namespace','user',"password",'config_items','_deleted')
    fields = readonly_fields
    ordering = ('workload',)
    get_cluster = staticmethod(lambda obj:obj.workload.cluster)
    get_project = staticmethod(lambda obj:obj.workload.project)
    get_namespace = staticmethod(lambda obj:obj.workload.namespace)


@admin.register(models.Database)
class DatabaseAdmin(admin.ModelAdmin):
    list_display = ('name','_server','_ip','_internal_name','_internal_port')
    readonly_fields = ('name','_server_name','_ip','_internal_name','_internal_port','_workload')
    ordering = ('server__host','name')
    list_filter = ('server','name')
    search_fields = ['name']

    inlines = [WorkloadDatabaseInline2]

    def _ip(self,obj):
        if not obj :
            return ""
        else:
            return obj.server.ip
    _ip.short_description = "IP"

    def _server_name(self,obj):
        if not obj :
            return ""
        elif obj.server.other_names:
            return "{} :[{}]".format(obj.server.host," , ".join(obj.server.other_names))
        else:
            return obj.server.host
    _server_name.short_description = "Server"

    def _server(self,obj):
        if not obj :
            return ""
        elif obj.server.other_names:
            return "{} , {}".format(obj.server.host," , ".join(obj.server.other_names))
        else:
            return obj.server.host
    _server.short_description = "server"

    def _internal_name(self,obj):
        if not obj :
            return ""
        else:
            return obj.server.internal_name
    _internal_name.short_descrinternal_nametion = "Internal Name"

    def _internal_port(self,obj):
        if not obj :
            return ""
        else:
            return obj.server.internal_port
    _internal_port.short_descrtion = "Internal Port"

    workload_change_url_name = 'admin:{}_{}_change'.format(models.Workload._meta.app_label,models.Workload._meta.model_name)
    def _workload(self,obj):
        if not obj :
            return ""
        elif not obj.server.workload:
            return ""
        else:
            url = reverse(self.workload_change_url_name, args=(obj.server.workload.id,))
            return mark_safe("<A href='{}'>{}</A><A href='{}' style='margin-left:50px' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(url,obj.server.workload.name,obj.server.workload.viewurl,obj.server.workload.managementurl))
    _workload.short_description = "Workload"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

class RunningStatusFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Running Status'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'is_running'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [(True,"Running"),(False,"Terminated")]


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
        elif val == 'True':
            return queryset.filter(container_terminated__isnull=True)
        else:
            return queryset.filter(container_terminated__isnull=False)

@admin.register(models.Container)
class ContainerAdmin(ClusterLinkMixin,NamespaceLinkMixin,WorkloadLinkMixin,LogsLinkMixin,admin.ModelAdmin):
    list_display = ('_containerid','_cluster', '_namespace', '_workload','status','poduid','_started', '_terminated','_last_checked',"_logs")
    readonly_fields = ('containerid','_cluster', '_namespace', '_workload','image','poduid','podip','status','pod_created','pod_started','container_created', 'container_started', 'container_terminated','exitcode','last_checked',"_logs",'ports','envs')
    ordering = ('cluster__name', 'namespace__name', 'workload__name','workload__kind','-container_started')
    list_filter = ('cluster',"workload__kind","status")
    search_fields = ['workload__name','workload__namespace__name','containerid']

    def _last_checked(self,obj):
        if not obj:
            return ""
        else:
            return timezone.localtime(obj.last_checked).strftime("%Y-%m-%d %H:%M:%S")
    _last_checked.short_description = "Last Check"

    def _started(self,obj):
        if not obj:
            return ""
        elif obj.container_started:
            return timezone.localtime(obj.container_started).strftime("%Y-%m-%d %H:%M:%S")
        elif obj.pod_started:
            return timezone.localtime(obj.pod_started).strftime("%Y-%m-%d %H:%M:%S")
        else:
            return ""
    _started.short_description = "Started"

    def _terminated(self,obj):
        if not obj:
            return ""
        elif obj.container_terminated:
            return timezone.localtime(obj.container_terminated).strftime("%Y-%m-%d %H:%M:%S")
        else:
            return ""
    _terminated.short_description = "Terminated"

    def _containerid(self,obj):
        if not obj:
            return ""
        elif obj.containerid:
            return "{}...{}".format(obj.containerid[:8],obj.containerid[-8:])
        else:
            return ""
    _containerid.short_description = "Containerid"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(models.ContainerLog)
class ContainerLogAdmin(ContainerLinkMixin,admin.ModelAdmin):
    list_display = ("_logtime",'_container_short',"level","source","_short_message")
    readonly_fields = ("_logtime",'_container',"level","source","_message")

    list_filter = ("level",)

    ordering = ("container","logtime")
    search_fields = ['container__id','container__workload__name']

    def _short_message(self,obj):
        if not obj or not obj.message:
            return ""
        else:
            return "{} ...".format(obj.message[:100])
    _short_message.short_description = "message"

    def _message(self,obj):
        if not obj or not obj.message:
            return ""
        elif "\n" in obj.message:
            return mark_safe("<pre>{}</pre>".format(obj.message))
        else:
            return mark_safe("<pre style='white-space:normal'>{}</pre>".format(obj.message))
    _message.short_description = "message"

    def _logtime(self,obj):
        if not obj :
            return ""
        else:
            return timezone.localtime(obj.logtime).strftime("%Y-%m-%d %H:%M:%S.%f")
    _logtime.short_description = "Logtime"


    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

