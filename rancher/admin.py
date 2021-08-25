import logging
import traceback
import json

from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html, mark_safe
from django.urls import reverse,resolve
from django.utils import timezone
from django.contrib.admin.views.main import ChangeList

from django_q.tasks import async_task

from . import models
from . import rancher_harvester
from . import forms
from .decorators import  add_changelink,many2manyinline

logger = logging.getLogger(__name__)

class ReverseChangeList(ChangeList):
    def get_results(self, request):
        super().get_results(request)
        if not isinstance(self.result_list,list):
            self.result_list = list(self.result_list)

        self.result_list.reverse()


class LookupAllowedMixin(object):
    def lookup_allowed(self, lookup, value):
        return True

class RequestMixin(object):
    request = None
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        self.request = request
        return qs

class DatetimeMixin(object):
    def _modified(self,obj):
        if not obj or not obj.modified :
            return ""
        else:
            return timezone.localtime(obj.modified).strftime("%Y-%m-%d %H:%M:%S")
    _modified.short_description = "Modified"

    def _created(self,obj):
        if not obj or not obj.created :
            return ""
        else:
            return timezone.localtime(obj.created).strftime("%Y-%m-%d %H:%M:%S")
    _created.short_description = "Created"

    def _updated(self,obj):
        if not obj or not obj.updated :
            return ""
        else:
            return timezone.localtime(obj.updated).strftime("%Y-%m-%d %H:%M:%S")
    _updated.short_description = "updated"

    def _starttime(self,obj):
        if not obj or not obj.starttime :
            return ""
        else:
            return timezone.localtime(obj.starttime).strftime("%Y-%m-%d %H:%M:%S")
    _starttime.short_description = "Start Time"

    def _endtime(self,obj):
        if not obj or not obj.endtime :
            return ""
        else:
            return timezone.localtime(obj.endtime).strftime("%Y-%m-%d %H:%M:%S")
    _endtime.short_description = "End Time"

    def _last_heartbeat(self,obj):
        if not obj or not obj.last_heartbeat :
            return ""
        else:
            return timezone.localtime(obj.last_heartbeat).strftime("%Y-%m-%d %H:%M:%S")
    _last_heartbeat.short_description = "Last Heartbeat"

    def _scaned(self,obj):
        if not obj or not obj.scaned :
            return ""
        else:
            return timezone.localtime(obj.scaned).strftime("%Y-%m-%d %H:%M:%S")
    _scaned.short_description = "Scan Time"

    def _added(self,obj):
        if not obj or not obj.added :
            return ""
        else:
            return timezone.localtime(obj.added).strftime("%Y-%m-%d %H:%M:%S")
    _added.short_description = "Added"

    def _resource_scaned(self,obj):
        if not obj or not obj.resource_scaned :
            return ""
        else:
            return timezone.localtime(obj.resource_scaned).strftime("%Y-%m-%d %H:%M:%S")
    _resource_scaned.short_description = "resource_scaned"

class EnvValueMixin(object):
    def _value(self,obj):
        if not obj or not obj.value :
            return ""
        else:
            return mark_safe("<pre style='white-space:pre-wrap'>{}</pre>".format(obj.value))
    _value.short_description = "Value"

class ContainerImageLinkMixin(object):
    image_change_url_name = 'admin:{}_{}_change'.format(models.ContainerImage._meta.app_label,models.ContainerImage._meta.model_name)

    def _containerimage(self,obj):
        if not obj :
            return ""
        elif not obj.image or not obj.containerimage_id:
            return ""
        else:
            url = reverse(self.image_change_url_name, args=(obj.containerimage_id,))
            return mark_safe("<A href='{}'>{}</A>".format(url,obj.image))
    _containerimage.short_description = "Image"

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
                if "/rancher/project/" in self.request.path and self.request.META.get("QUERY_STRING"):
                    url = "{}?{}".format(url,self.request.META.get("QUERY_STRING"))
                return mark_safe("<span style='white-space:nowrap;'><A href='{2}' target='manage_workloads'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{0}' style='margin-left:5px'>{1}</A></span>".format(
                    url,
                    "{}({})".format(project.name,project.projectid) if project.name else project.projectid,
                    project.managementurl
                ))
            else:
                return ""
    _project.short_description = "Project"

    def _projectid(self,obj):
        if not obj :
            return ""
        else:
            project = self.get_project(obj)
            if project:
                return mark_safe("{0}<A href='{1}' style='margin-left:20px' target='manage_workloads'><img src='/static/img/view.jpg' width=16 height=16></A>".format(
                    "{}({})".format(project.name,project.projectid) if project.name else project.projectid,
                   project.managementurl
                ))
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
            if not namespace:
                return ""
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


class ContainersLinkMixin(object):
    containers_url_name = 'admin:{}_{}_changelist'.format(models.Container._meta.app_label,models.Container._meta.model_name)
    _containers_url = None

    container_url_name = 'admin:{}_{}_change'.format(models.Container._meta.app_label,models.Container._meta.model_name)

    containerlogs_url_name = 'admin:{}_{}_changelist'.format(models.ContainerLog._meta.app_label,models.ContainerLog._meta.model_name)
    _containerlogs_url = None

    @property
    def containers_url(self):
        if not  ContainersLinkMixin._containers_url:
            ContainersLinkMixin._containers_url = reverse(ContainersLinkMixin.containers_url_name, args=[])

        return ContainersLinkMixin._containers_url

    @property
    def containerlogs_url(self):
        if not ContainersLinkMixin._containerlogs_url:
            ContainersLinkMixin._containerlogs_url = reverse(ContainersLinkMixin.containerlogs_url_name, args=[])

        return ContainersLinkMixin._containerlogs_url

    def _containers(self,obj):
        if not obj :
            return ""
        elif not obj.latest_containers:
            url = reverse(self.containers_url_name, args=[])
            return mark_safe("<A href='{0}?workload__id__exact={1}'>All</A>".format(url,obj.id))
        elif len(obj.latest_containers) == 1:
            change_url = reverse(self.container_url_name, args=[obj.latest_containers[0][0]])

            logs_link = ""
            if obj.latest_containers[0][2]:
                logs_link = "<A href='{0}?container__id__exact={1}'><img src='/static/img/info.png' width=16 height=16></A>".format(self.containerlogs_url,obj.latest_containers[0][0])

            if obj.latest_containers[0][2] & models.Workload.ERROR == models.Workload.ERROR:
                logs_link = "{0}<A href='{1}?container__id__exact={2}&level={3}' style='margin-left:5px'><img src='/static/img/error.png' width=16 height=16></A>".format(
                    logs_link,
                    self.containerlogs_url,
                    obj.latest_containers[0][0],
                    models.ContainerLog.ERROR
                )
            elif obj.latest_containers[0][2] & models.Workload.WARNING == models.Workload.WARNING:
                logs_link = "{0}<A href='{1}?container__id__exact={2}&level__gte={3}' style='margin-left:5px'><img src='/static/img/warning.png' width=16 height=16></A>".format(
                    logs_link,
                    self.containerlogs_url,
                    obj.latest_containers[0][0],
                    models.ContainerLog.WARNING
                )

            if logs_link:
                return mark_safe("<span style='white-space:nowrap'>{3}<A href='{0}' style='margin-left:5px'>Latest</A><A style='margin-left:5px' href='{1}?workload__id__exact={2}'>All</A></span>".format(
                    change_url,self.containers_url,obj.id,logs_link
                ))
            else:
                return mark_safe("<span style='white-space:nowrap'><A href='{0}'>Latest</A><A style='margin-left:5px' href='{1}?workload__id__exact={2}'>All</A></span>".format(
                    change_url,self.containers_url,obj.id
                ))
        else:
            containerids = ",".join(str(o[0]) for o in obj.latest_containers)
            level = 0
            for container in obj.latest_containers:
                level |= container[2]

            logs_link = ""
            if level:
                logs_link = "<A href='{0}?container__id__in={1}'><img src='/static/img/info.png' width=16 height=16></A>".format(self.containerlogs_url,containerids)

            if level & models.Workload.ERROR == models.Workload.ERROR:
                logs_link = "{0}<A href='{1}?container__id__in={2}&level={3}' style='margin-left:5px'><img src='/static/img/error.png' width=16 height=16></A>".format(
                    logs_link,
                    self.containerlogs_url,
                    containerids,
                    models.ContainerLog.ERROR
                )
            elif level & models.Workload.WARNING == models.Workload.WARNING:
                logs_link = "{0}<A href='{1}?container__id__in={2}&level__gte={3}' style='margin-left:5px'><img src='/static/img/warning.png' width=16 height=16></A>".format(
                    logs_link,
                    self.containerlogs_url,
                    containerids,
                    models.ContainerLog.WARNING
                )

            if logs_link:
                return mark_safe("<span style='white-space:nowrap'>{3}<A href='{0}?id__in={2}' style='margin-left:5px'>Latest</A><A style='margin-left:5px' href='{0}?workload__id__exact={1}'>All</A></span>".format(
                    self.containers_url,obj.id,containerids,logs_link
                ))
            else:
                return mark_safe("<span style='white-space:nowrap'><A href='{0}?id__in={2}'>Latest</A><A style='margin-left:5px' href='{0}?workload__id__exact={1}'>All</A></span>".format(
                    self.containers_url,obj.id,containerids
                ))
    _containers.short_description = "Containers"

    def _running_status(self,obj):
        if not obj :
            return ""
        elif not obj.latest_containers:
            return "Stopped"
        else:
            return "Running" if any(o[1] for o in obj.latest_containers) else "Stopped"
    _running_status.short_description = "Status"

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
                return mark_safe("<A href='{0}?container__id__exact={1}'>Logs</A><A style='margin-left:5px' href='{0}?container__id__exact={1}&level={2}'>Errors</A><A style='margin-left:5px' href='{0}?container__id__exact={1}&level={3}'>Warnings</A>".format(url,obj.id,models.ContainerLog.ERROR,models.ContainerLog.WARNING))
            elif obj.warning:
                return mark_safe("<A href='{0}?container__id__exact={1}'>Logs</A><A style='margin-left:5px' href='{0}?container__id__exact={1}&level={2}'>Warnings</A>".format(url,obj.id,models.ContainerLog.WARNING))
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
            if obj.__class__ == models.ContainerImage:
                workloads = obj.workloads
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
                elif obj.__class__ == models.ContainerImage:
                    return mark_safe("<A href='{}?containerimage__id__exact={}'>{}</A>".format(url,obj.id,workloads))
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
    _active_workloads.short_description = "Active Workloads"

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


class WorkloadInlineMixin(RequestMixin,ClusterLinkMixin,ProjectLinkMixin,NamespaceLinkMixin,WorkloadLinkMixin):
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
class ClusterAdmin(WorkloadsLinkMixin,DatetimeMixin,admin.ModelAdmin):
    list_display = ('name','ip', 'clusterid','_workloads','_active_workloads','_deleted_workloads','_modified','added_by_log') if settings.ENABLE_ADDED_BY_CONTAINERLOG else ('name','ip', 'clusterid','_workloads','_active_workloads','_deleted_workloads','_modified')

    readonly_fields = ('ip','clusterid','_workloads','_active_workloads','_deleted_workloads','_modified','_created','added_by_log') if settings.ENABLE_ADDED_BY_CONTAINERLOG else ('ip','clusterid','_workloads','_active_workloads','_deleted_workloads','_modified','_created')

    ordering = ('name',)
    #actions = ('refresh','enforce_refresh')


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
class ProjectAdmin(RequestMixin,LookupAllowedMixin,ClusterLinkMixin,ProjectLinkMixin,WorkloadsLinkMixin,admin.ModelAdmin):
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


class WorkloadInline4Namespace(DeletedMixin,WorkloadLinkMixin,DatetimeMixin,admin.TabularInline):
    model = models.Workload
    readonly_fields = ('_name_with_link', 'kind','image','itsystem',"suspend","_modified","_deleted")
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
class NamespaceAdmin(RequestMixin,LookupAllowedMixin,DeletedMixin,ClusterLinkMixin,WorkloadsLinkMixin,ProjectLinkMixin,admin.ModelAdmin):
    list_display = ('name','_cluster','_project',"system_namespace","_workloads",'_active_workloads','_deleted_workloads','_deleted',"added_by_log") if settings.ENABLE_ADDED_BY_CONTAINERLOG else  ('name','_cluster','_project',"system_namespace","_workloads",'_active_workloads','_deleted_workloads','_deleted')

    readonly_fields = ('name','_cluster','_project',"system_namespace","_workloads",'_active_workloads','_deleted_workloads','_deleted',"added_by_log") if settings.ENABLE_ADDED_BY_CONTAINERLOG else ('name','_cluster','_project',"system_namespace","_workloads",'_active_workloads','_deleted_workloads','_deleted')

    fields = readonly_fields
    ordering = ('cluster__name','project__name','name')
    list_filter = ('project','system_namespace',ExistingStatusFilter)

    inlines = [WorkloadInline4Namespace]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

class SecretItemInline(DatetimeMixin,EnvValueMixin,admin.TabularInline):
    model = models.SecretItem
    readonly_fields = ('name','_value','_modified','_created','_updated')
    fields = readonly_fields
    ordering = ('name',)

@admin.register(models.Secret)
class SecretAdmin(RequestMixin,DeletedMixin,LookupAllowedMixin,ClusterLinkMixin,ProjectLinkMixin,NamespaceLinkMixin,DatetimeMixin,admin.ModelAdmin):
    list_display = ('name','_cluster',"_project","_namespace","_deleted","_modified","_created","_updated")
    readonly_fields = ('name','_cluster',"_project","_namespace","_references","_deleted","_modified","_created","_updated")
    ordering = ('cluster__name','name')
    list_filter = ('cluster',)

    search_fields = ['name']

    inlines = [SecretItemInline]

    workload_change_url_name = 'admin:{}_{}_change'.format(models.Workload._meta.app_label,models.Workload._meta.model_name)
    def _references(self,obj):
        if not obj :
            return ""
        result = None
        for item in models.WorkloadEnv.objects.filter(secret=obj).order_by("workload","name"):
            url = reverse(self.workload_change_url_name, args=(item.workload.id,))
            if result:
                result = "<A href={0}>{1}.{2}<>".format(url,item.workload.item.name)
            else:
                result = "{3}<br><A href={0}>{1}.{2}<>".format(url,item.workload.item.name,result)

        return mark_safe(result)
    _references.short_description = "References"


    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

class ConfigMapItemInline(DatetimeMixin,EnvValueMixin,admin.TabularInline):
    model = models.ConfigMapItem
    readonly_fields = ('name','_value','_modified','_created','_updated')
    fields = readonly_fields
    ordering = ('name',)

@admin.register(models.ConfigMap)
class ConfigMapAdmin(DeletedMixin,LookupAllowedMixin,ClusterLinkMixin,NamespaceLinkMixin,DatetimeMixin,admin.ModelAdmin):
    list_display = ('name','_cluster',"_namespace","_deleted","_modified","_created","_updated")
    readonly_fields = list_display
    ordering = ('cluster__name','namespace__name','name')
    list_filter = ('cluster','namespace')

    search_fields = ['name']

    inlines = [ConfigMapItemInline]

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
class PersistentVolumeAdmin(LookupAllowedMixin,DeletedMixin,ClusterLinkMixin,DatetimeMixin,admin.ModelAdmin):
    list_display = ('name','_cluster', 'kind','storage_class_name','volumepath','_capacity','writable',"_modified",'_deleted')
    readonly_fields = ('name','_cluster', 'kind','storage_class_name','volumepath','_capacity',"volume_mode","uuid",'writable','reclaim_policy','_node_affinity',"_modified","_created",'_deleted')
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


class WorkloadEnvInline(DatetimeMixin,EnvValueMixin,admin.TabularInline):
    readonly_fields = ('name','_value','_configmap','_secret','_modified','_created')
    fields = ('name','_value',"_configmap","_secret",'_modified')
    model = models.WorkloadEnv
    classes = ["collapse"]

    configmap_change_url_name = 'admin:{}_{}_change'.format(models.ConfigMap._meta.app_label,models.ConfigMap._meta.model_name)
    def _configmap(self,obj):
        if not obj or not obj.configmap:
            return ""
        else:
            url = reverse(self.configmap_change_url_name, args=(obj.configmap.id,))
            if obj.configmapitem:
                return mark_safe("<A href='{}'>{}</A>".format(url,obj.configmapitem))
            else:
                return mark_safe("<A href='{}'>{}</A>".format(url,obj.configmap))
    _configmap.short_description = "Config Map"

    secret_change_url_name = 'admin:{}_{}_change'.format(models.Secret._meta.app_label,models.Secret._meta.model_name)
    def _secret(self,obj):
        if not obj or not obj.secret:
            return ""
        else:
            url = reverse(self.secret_change_url_name, args=(obj.secret.id,))
            if obj.secretitem:
                return mark_safe("<A href='{}'>{}</A>".format(url,obj.secretitem))
            else:
                return mark_safe("<A href='{}'>{}</A>".format(url,obj.secret))
    _secret.short_description = "Secret"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadListeningInline(DeletedMixin,DatetimeMixin,admin.TabularInline):
    readonly_fields = ('_listen','protocol','container_port','_modified','_deleted')
    fields = ('_listen','protocol','container_port','_modified','_deleted')
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


class WorkloadInline4Image(RequestMixin,DeletedMixin,ClusterLinkMixin,ProjectLinkMixin,WorkloadLinkMixin,NamespaceLinkMixin,DatetimeMixin,admin.TabularInline):
    model = models.Workload
    readonly_fields = ('_name_with_link','_cluster','_project','_namespace', 'kind','image','itsystem',"suspend","_modified","_deleted")
    fields = readonly_fields
    ordering = ('name',)
    get_workload = staticmethod(lambda obj:obj)
    classes = ["collapse"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@many2manyinline("vulnerability")
class VulnerabilityInline4Os(RequestMixin,admin.TabularInline):
    model = models.Vulnerability.oss.through
    readonly_fields = ('vulnerabilityid', 'pkgname', 'installedversion', 'get_severity_display','affected_images','fixedversion', 'publisheddate', 'lastmodifieddate' )
    fields = readonly_fields
    #fields = readonly_fields
    ordering = ('-vulnerability__severity','vulnerability__pkgname')

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class VulnerabilitiesMixin(object):
    vulns_url_name = 'admin:{}_{}_changelist'.format(models.Vulnerability._meta.app_label,models.Vulnerability._meta.model_name)
    get_os = None
    def _vulnerabilities(self,obj):
        if not obj:
            return ""
        else:
            if self.get_os:
                obj = self.get_os(obj)
            if not obj:
                return ""

            result = ""
            if obj.criticals:
                result = "<span>Critical:{}</span>".format(obj.criticals)
            if obj.highs:
                if result:
                    result = "{}<span style='margin-left:5px'>High:{}</span>".format(result,obj.highs)
                else:
                    result = "<span>High:{}</span>".format(obj.highs)
            if obj.mediums:
                if result:
                    result = "{}<span style='margin-left:5px'>Medium:{}</span>".format(result,obj.mediums)
                else:
                    result = "<span>Medium:{}</span>".format(obj.mediums)
            if obj.lows:
                if result:
                    result = "{}<span style='margin-left:5px'>Low:{}</span>".format(result,obj.lows)
                else:
                    result = "<span>Low:{}</span>".format(obj.lows)
            if obj.unknowns:
                if result:
                    result = "{}<span style='margin-left:5px'>Unknown:{}</span>".format(result,obj.unknowns)
                else:
                    result = "<span>Low:{}</span>".format(obj.unknowns)


            return mark_safe(result)
    _vulnerabilities.short_description = "Vulnerabilities"

class ImagesMixin(object):
    images_url_name = 'admin:{}_{}_changelist'.format(models.ContainerImage._meta.app_label,models.ContainerImage._meta.model_name)
    get_os = None
    def _images(self,obj):
        if not obj:
            return ""
        else:
            if self.get_os:
                obj = self.get_os(obj)
            if not obj or not obj.images:
                return ""
            else:
                url = "{}?os={}".format(reverse(self.images_url_name,args=None),obj.id)
                return mark_safe("<A href='{}'>{}</A>".format(url,obj.images))
    _images.short_description = "Images"

@many2manyinline("operatingsystem")
class OperatingSystemInline(RequestMixin,ImagesMixin,VulnerabilitiesMixin,admin.TabularInline):
    model = models.Vulnerability.oss.through
    readonly_fields = ('name','version','_images','criticals',"highs","mediums","lows","unknowns" )
    fields = readonly_fields
    ordering = ('operatingsystem__name','operatingsystem__version')

    get_os = lambda self,o:o.operatingsystem

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class ScanSummaryMixin(object):
    get_image = None

    def _scan_summary(self,obj):
        if not obj:
            return ""
        else:
            if self.get_image:
                obj = self.get_image(obj)
            if not obj:
                return ""
            if obj.scan_status < 0:
                result = obj.scan_message
            elif obj.scan_status == 0:
                result = ""
            else:
                result = ""
                if obj.criticals:
                    result = "<span>Critical:{}</span>".format(obj.criticals)
                if obj.highs:
                    if result:
                        result = "{}<span style='margin-left:5px'>High:{}</span>".format(result,obj.highs)
                    else:
                        result = "<span>High:{}</span>".format(obj.highs)
                if obj.mediums:
                    if result:
                        result = "{}<span style='margin-left:5px'>Medium:{}</span>".format(result,obj.mediums)
                    else:
                        result = "<span>Medium:{}</span>".format(obj.mediums)
                if obj.lows:
                    if result:
                        result = "{}<span style='margin-left:5px'>Low:{}</span>".format(result,obj.lows)
                    else:
                        result = "<span>Low:{}</span>".format(obj.lows)
                if obj.unknowns:
                    if result:
                        result = "{}<span style='margin-left:5px'>Unknown:{}</span>".format(result,obj.unknowns)
                    else:
                        result = "<span>Low:{}</span>".format(obj.unknowns)
    
            return mark_safe(result)

    _scan_summary.short_description = "Scan Report"

@many2manyinline("containerimage")
class ContainerImageInline(RequestMixin,ScanSummaryMixin,WorkloadsLinkMixin,admin.TabularInline):
    model = models.ContainerImage.vulnerabilities.through
    readonly_fields = ('imageid','os','workloads', 'get_scan_status_display', '_scan_summary' )
    fields = readonly_fields
    get_image = lambda self,o:o.containerimage

    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        qs = qs.select_related('containerimage').defer("containerimage__scan_result","containerimage__scan_message","containerimage__vulnerabilities")
        return qs

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@add_changelink("imageid")
class ContainerImageInline4Os(RequestMixin,ScanSummaryMixin,WorkloadsLinkMixin,admin.TabularInline):
    model = models.ContainerImage
    readonly_fields = ('imageid','os','workloads', 'get_scan_status_display', '_scan_summary' )
    fields = readonly_fields

    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        qs = qs.defer("scan_result","scan_message")
        return qs

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(models.OperatingSystem)
class OperatingSystemAdmin(RequestMixin,ImagesMixin,VulnerabilitiesMixin,admin.ModelAdmin):
    list_display = ('name','version','_images','criticals',"highs","mediums","lows","unknowns" )
    readonly_fields = list_display
    fields = readonly_fields
    list_filter = ("name",)
    ordering = ["name","version"]

    inlines = [ContainerImageInline4Os,VulnerabilityInline4Os]

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(models.Vulnerability)
class VulnerabilityAdmin(RequestMixin,admin.ModelAdmin):
    list_display = ('vulnerabilityid', 'pkgname', 'installedversion','severity','affected_oss','affected_images','fixedversion', 'publisheddate', 'lastmodifieddate' )
    readonly_fields = ('vulnerabilityid', 'pkgname', 'installedversion','severity','affected_oss','affected_images','severitysource','fixedversion', 'publisheddate', 'lastmodifieddate','_description','_scan_result' )
    list_filter = ("severity",)
    search_fields = ['pkgname','vulnerabilityid']
    ordering = ["-severity","pkgname","installedversion"]

    inlines = [ContainerImageInline,OperatingSystemInline]
    #inlines = [OperatingSystemInline]

    list_url_name = '{}_{}_changelist'.format(models.Vulnerability._meta.app_label,models.Vulnerability._meta.model_name)
    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        if resolve(request.path_info).url_name == self.list_url_name:
            qs = qs.defer("scan_result","description","severitysource")

        return qs

    def _scan_result(self,obj):
        if not obj:
            return ""
        elif not obj.scan_result:
            return ""
        else:
            return format_html("""<A href="javascript:void" onclick="django.jQuery('#id_image_{0}').toggle();django.jQuery(this).html((django.jQuery(this).html() == 'Show')?'Hide':'Show')">Show</A>
<pre id="id_image_{0}" style="display:none;white-space:break-spaces">
{1}
</pre>""", obj.id,json.dumps(obj.scan_result,indent=4))
    _scan_result.short_description = "Scan Result"

    def _description(self,obj):
        if not obj:
            return ""
        elif not obj.description:
            return ""
        else:
            return mark_safe("<pre style='white-space:break-spaces'>{}</pre>".format(obj.description))
    _description.short_description = "Description"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@many2manyinline("vulnerability")
class VulnerabilityInline4Image(RequestMixin,admin.TabularInline):
    model = models.ContainerImage.vulnerabilities.through
    readonly_fields = ('vulnerabilityid','os', 'pkgname', 'installedversion', 'get_severity_display','affected_images','fixedversion', 'publisheddate', 'lastmodifieddate' )
    fields = readonly_fields
    #fields = readonly_fields
    ordering = ('-vulnerability__severity','vulnerability__vulnerabilityid','vulnerability__pkgname')
    classes = ["collapse"]

    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        qs = qs.select_related('vulnerability').defer("vulnerability__scan_result","vulnerability__description","vulnerability__oss")
        return qs

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(models.ContainerImage)
class ContainerImageAdmin(RequestMixin,DatetimeMixin,ScanSummaryMixin,WorkloadsLinkMixin, admin.ModelAdmin):
    list_display = ('imageid',"_account","_name",'tag','_workloads','os', 'scan_status', '_scan_summary', '_scaned' )
    readonly_fields = ('imageid',"_account","_name", 'tag','_workloads','os','_added', 'scan_status', '_scan_summary', '_scaned',"_scan_result","_scan_message" )

    list_filter = ("imagefamily__account","scan_status","os")
    ordering = ('imagefamily__account','imagefamily__name','tag')
    exclude = ("vulnerabilities",)

    actions = ('scan',)

    search_fields = ['imagefamily__name']

    inlines = [ VulnerabilityInline4Image,WorkloadInline4Image]

    list_url_name = '{}_{}_changelist'.format(models.ContainerImage._meta.app_label,models.ContainerImage._meta.model_name)
    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        if resolve(request.path_info).url_name == self.list_url_name:
            qs = qs.defer("scan_result","scan_message","vulnerabilities")

        return qs

    def _account(self,obj):
        if not obj or not obj.imagefamily:
            return ""
        else:
            return obj.imagefamily.account
    _account.short_description = "Account"

    def _name(self,obj):
        if not obj or not obj.imagefamily:
            return ""
        else:
            return obj.imagefamily.name
    _name.short_description = "Name"

    def _scan_result(self,obj):
        if not obj:
            return ""
        elif not obj.scan_result:
            return ""
        else:
            return format_html("""<A href="javascript:void" onclick="django.jQuery('#id_image_{0}').toggle();django.jQuery(this).html((django.jQuery(this).html() == 'Show')?'Hide':'Show')">Show</A>
<pre id="id_image_{0}" style="display:none">
{1}
</pre>""", obj.id,json.dumps(obj.scan_result,indent=4))
    _scan_result.short_description = "Scan Result"

    def _scan_message(self,obj):
        if not obj:
            return ""
        elif not obj.scan_message:
            return ""
        else:
            return mark_safe("<pre>{}</pre>".format(obj.scan_message))
    _scan_message.short_description = "Scan Message"

    def scan(self, request, queryset):
        for image in queryset:
            try:
                image.scan(rescan=True)
                if image.scan_status in (image.SCAN_FAILED,image.PARSE_FAILED):
                    self.message_user(request, "Failed to scan the image '{}'.{}".format(image.imageid,image.scan_message),level=messages.ERROR)
                else:
                    self.message_user(request, "Succeed to scan the image '{}'".format(image.imageid))
            except Exception as ex:
                self.message_user(request, "Failed to scan the image '{}'. {}".format(image.imageid,str(ex)),level=messages.ERROR)

    scan.short_description = 'Scan'

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class WorkloadResourceInline(DatetimeMixin,admin.TabularInline):
    model = models.WorkloadResource
    readonly_fields = ('resource_type','resource_id','config_items','config_source','properties','_updated',"_created")
    fields = readonly_fields
    ordering = ('resource_type','resource_id',)
    classes = ["collapse"]

@admin.register(models.Workload)
class WorkloadAdmin(RequestMixin,LookupAllowedMixin,DeletedMixin,ClusterLinkMixin, ProjectLinkMixin, NamespaceLinkMixin, WorkloadLinkMixin,ContainersLinkMixin,ContainerImageLinkMixin,DatetimeMixin, admin.ModelAdmin):
    list_display = ('_name_with_link', '_cluster', '_project', '_namespace', 'kind', '_containerimage','itsystem', '_containers','_running_status', '_modified','_deleted',"added_by_log") if settings.ENABLE_ADDED_BY_CONTAINERLOG else ('_name_with_link', '_cluster', '_project', '_namespace', 'kind', '_containerimage','itsystem', '_containers','_running_status', '_modified','_deleted')

    list_display_links = None

    readonly_fields = ('_name', '_cluster', '_project', '_namespace', 'kind', '_containerimage','_replicas','schedule','_containers','_running_status', '_modified',"suspend","added_by_log",'_resource_dependent_tree','_workload_dependent_tree') if settings.ENABLE_ADDED_BY_CONTAINERLOG else ('_name', '_cluster', '_project', '_namespace', 'kind', '_containerimage','_replicas','schedule','_containers','_running_status', '_modified',"suspend",'_resource_dependent_tree','_workload_dependent_tree')

    fields = ('_name', '_cluster', '_project', '_namespace', 'kind', '_containerimage', "_replicas",'schedule', '_containers','_running_status',"suspend", '_modified','_deleted',"added_by_log",'_resource_dependent_tree','_workload_dependent_tree') if settings.ENABLE_ADDED_BY_CONTAINERLOG else ('_name', '_cluster', '_project', '_namespace', 'kind', '_containerimage', "_replicas",'schedule','_containers','_running_status',"suspend", '_modified','_deleted','_resource_dependent_tree','_workload_dependent_tree')

    ordering = ('cluster__name', 'project__name', 'namespace__name', 'name',)
    list_filter = ('cluster',ExistingStatusFilter,"kind", 'namespace')
    search_fields = ['name', 'project__name', 'namespace__name']
    get_workload = staticmethod(lambda obj: obj)

    inlines = [WorkloadResourceInline, WorkloadListeningInline, WorkloadEnvInline, WorkloadVolumeInline]
    #inlines = [WorkloadListeningInline, WorkloadEnvInline, WorkloadVolumeInline]

    actions = ('scan_dependency','populate_resource_tree','populate_workload_tree')

    change_url_name = 'admin:{}_{}_change'.format(models.Workload._meta.app_label,models.Workload._meta.model_name)
    list_url_name = '{}_{}_changelist'.format(models.Workload._meta.app_label,models.Workload._meta.model_name)
    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        qs = qs.select_related("itsystem","cluster","project","namespace")
        if resolve(request.path_info).url_name == self.list_url_name:
            #qs = qs.only('name', 'cluster__name', 'project__projectid',"project__name", 'namespace__name', 'kind', 'image',"containerimage_id",'itsystem__name', 'latest_containers', 'modified','deleted',"added_by_log")
            pass

        return qs

    def _replicas(self,obj):
        if not obj:
            return ""
        elif obj.kind == "Deployment":
            return obj.replicas
        else:
            return ""
    _replicas.short_description = "Replicas"

    _htmlid = 0
    def get_tree_nodeid(self,nodetype):
        self._htmlid += 1
        return "{}_{}".format(nodetype,self._htmlid)

    def _format_resource_tree(self,tree,indent=0):
        dep_html = ""
        for dependent_type,dependent_type_name,type_dependents in tree[3]:
            type_tree_html = ""
            for dependent_pk,dependent_display,sub_dep_trees  in type_dependents:
                if sub_dep_trees:
                    resource_tree_id = self.get_tree_nodeid("res")
                    sub_tree_html = "".join(self._format_resource_tree(sub_tree,indent + 48) for sub_tree in sub_dep_trees)
                    type_tree_html = "{0}<div style='margin-left:{3}px'><img src='/static/img/plus.svg' onclick=\"toggle_tree(this,$('#{4}'))\" style='margin-right:5px'>{1}</div><div id='{4}' style='display:none'>{2}</div>".format(
                        type_tree_html,dependent_display,sub_tree_html,indent+32,resource_tree_id
                    )
                else:
                    type_tree_html = "{0}<div style='margin-left:{2}px'>{1}</div>".format(
                        type_tree_html,dependent_display,indent+32
                    )

            type_tree_id = self.get_tree_nodeid("restype")
            dep_html = "{0}<div style='margin-left:{2}px'><img src='/static/img/plus.svg' onclick=\"toggle_tree(this,$('#{4}'))\" style='margin-right:5px'>{1}</div><div id='{4}' style='display:none'>{3}</div>".format(
                dep_html,dependent_type_name,indent + 16,type_tree_html,type_tree_id
            )

        output_html = ""

        workload_url = reverse(self.change_url_name, args=(tree[0],))
        workload_name = "<A href='{0}'>{1}</A>".format(workload_url,tree[1])
        if indent > 0:
            if tree[3]:
                tree_id = self.get_tree_nodeid("tree")
                if tree[2]:
                    tree_html = "<div style='margin-left:{1}px'><img src='/static/img/plus.svg' onclick=\"toggle_tree(this,$('#{3}'))\" style='margin-right:5px'>{0}</div><div id='{3}' style='display:none'>{2}</div>".format(
                        workload_name,indent,dep_html,tree_id
                    )
                else:
                    tree_html = "<div style='margin-left:{1}px;text-decoration-line: line-through;color:red'><img src='/static/img/plus.svg' onclick=\"toggle_tree(this,$('#{3}'))\" style='margin-right:5px'>{0}</div><div id='{3}' style='display:none;'>{2}</div>".format(
                        workload_name,indent,dep_html,tree_id
                    )

            else:
                if tree[2]:
                    tree_html = "<div style='margin-left:{1}px'>{0}</div>".format(workload_name,indent)
                else:
                    tree_html = "<div style='margin-left:{1}px;text-decoration-line: line-through;color:red'>{0}</div>".format(workload_name,indent)

        elif dep_html:
            tree_html = dep_html
        else:
            tree_html = ""

        return tree_html

    def _resource_dependent_tree(self,obj):
        if not obj:
            return ""
        else:
            try:
                try:
                    tree = obj.dependenttree.restree
                except:
                    tree = None
                if tree:
                    if obj.toggle_tree_js:
                        return mark_safe(self._format_resource_tree(tree))
                    else:
                        obj.toggle_tree_js = True
                        return mark_safe("""
<script type="text/javascript">
    var $=django.jQuery;
    function toggle_tree(image,tree) {{
        tree.toggle()
        if (tree.is(":visible")) {{
            image.src = "/static/img/minus.svg"
        }} else {{
            image.src = "/static/img/plus.svg"
        }}
    }}
</script>
{}

""".format(self._format_resource_tree(tree)))
                else:
                    return ""
            except:
                traceback.print_exc()
                raise
    _resource_dependent_tree.short_description = "Resource Dependent Tree"

    def _format_workload_tree(self,tree,dependents=None,indent=0):
        dep_html = ""
        for dep_dependents,dep_workload_tree in tree[3]:
            
            dep_html = "{0}{1}".format(dep_html,self._format_workload_tree(dep_workload_tree,dependents=dep_dependents,indent=indent + 16))


        dependents_html = ""
        if dependents:
            dep_id = self.get_tree_nodeid("wl_dep")
            dependents_html = "<img src='/static/img/link.svg' onclick=\"$('#{1}').toggle()\" style='margin-left:5px'><div id='{1}' style='display:none'>{0}</div>".format(
                "".join("<div style='margin-left:32px;color:blue'>- {} : {}</div>".format(dep[1],dep[3]) for dep in dependents),
                dep_id
            )
                
        output_html = ""
        if indent == 0:
            workload_name = tree[1]
        else:
            workload_url = reverse(self.change_url_name, args=(tree[0],))
            workload_name = "<A href='{0}'>{1}</A>".format(workload_url,tree[1])
        if tree[3]:
            tree_id = self.get_tree_nodeid("wl_node")
            if tree[2]:
                tree_html = "<div style='margin-left:{1}px;'><span><img src='/static/img/plus.svg' onclick=\"toggle_tree(this,$('#{3}'))\" style='margin-right:5px'>{0}</span>{4}</div><div id='{3}' style='display:none;'>{2}</div>".format(
                    workload_name,indent,dep_html,tree_id,dependents_html
                )
            else:
                tree_html = "<div style='margin-left:{1}px;'><span style='text-decoration-line: line-through;color:red'><img src='/static/img/plus.svg' onclick=\"toggle_tree(this,$('#{3}'))\" style='margin-right:5px'>{0}</span>{4}</div><div id='{3}' style='display:none;'>{2}</div>".format(
                    workload_name,indent,dep_html,tree_id,dependents_html
                )

        else:
            if tree[2]:
                tree_html = "<div style='margin-left:{1}px;'><span>{0}</span>{2}</div>".format(workload_name,indent,dependents_html)
            else:
                tree_html = "<div style='margin-left:{1}px;'><span style='text-decoration-line: line-through;color:red'>{0}</span>{2}</div>".format(workload_name,indent,dependents_html)


        return tree_html

    def _workload_dependent_tree(self,obj):
        if not obj:
            return ""
        else:
            try:
                try: 
                    tree = obj.dependenttree.wltree
                except:
                    tree = None
                if tree:
                    if obj.toggle_tree_js:
                        return mark_safe(self._format_workload_tree(tree))
                    else:
                        obj.toggle_tree_js = True
                        return mark_safe("""
<script type="text/javascript">
    var $=django.jQuery;
    function toggle_tree(image,tree) {{
        tree.toggle()
        if (tree.is(":visible")) {{
            image.src = "/static/img/minus.svg"
        }} else {{
            image.src = "/static/img/plus.svg"
        }}
    }}
</script>
{}

""".format(self._format_workload_tree(tree)))
                else:
                    return ""
            except:
                traceback.print_exc()
                raise
    _workload_dependent_tree.short_description = "Workload Dependent Tree"

    def scan_dependency(self, request, queryset):
        for workload in queryset:
            try:
                workload.scan_dependency(rescan=True)
                self.message_user(request, "Succeed to scan the dependency of the workload '{}'".format(workload))
            except Exception as ex:
                self.message_user(request, "Failed to scan the dependency of the workload '{}'. {}".format(workload,str(ex)),level=messages.ERROR)

    scan_dependency.short_description = 'Scan Dependency'

    def populate_resource_tree(self, request, queryset):
        for workload in queryset:
            try:
                workload.populate_resource_dependent_tree(depth=1)
                self.message_user(request, "Succeed to poplate the resource dependent tree for the workload '{}'".format(workload))
            except Exception as ex:
                self.message_user(request, "Failed to populate the resource dependent tree for the workload '{}'. {}".format(workload,str(ex)),level=messages.ERROR)

    populate_resource_tree.short_description = 'Populate Resource Dependent Tree'

    def populate_workload_tree(self, request, queryset):
        for workload in queryset:
            try:
                workload.populate_workload_dependent_tree()
                self.message_user(request, "Succeed to poplate the workload dependent tree for the workload '{}'".format(workload))
            except Exception as ex:
                self.message_user(request, "Failed to populate the workload dependent tree for the workload '{}'. {}".format(workload,str(ex)),level=messages.ERROR)

    populate_workload_tree.short_description = 'Populate workload Dependent Tree'

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
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
class ContainerAdmin(LookupAllowedMixin,ClusterLinkMixin,NamespaceLinkMixin,WorkloadLinkMixin,LogsLinkMixin,admin.ModelAdmin):
    list_display = ('_containerid','_cluster', '_namespace', '_workload','status','poduid','_started', '_terminated','_last_checked',"_logs")
    readonly_fields = ('containerid','_cluster', '_namespace', '_workload','image','poduid','podip','status','_pod_created','_pod_started','_container_created', '_container_started', '_container_terminated','exitcode','_last_checked',"_logs",'ports','envs')
    ordering = ('cluster__name', 'namespace__name', 'workload__name','workload__kind','-container_started')
    list_filter = ('cluster',"workload__kind","status")
    search_fields = ['workload__name','workload__namespace__name','containerid']

    containers_url_name = '{}_{}_changelist'.format(models.Container._meta.app_label,models.Container._meta.model_name)
    show_full_result_count = False
    show_all = False

    def get_model_perms(self, request):
        """
        Return empty perms dict thus hiding the model from admin index.
        """
        return {}

    def get_queryset(self, request):
        if not resolve(request.path_info).url_name == self.containers_url_name:
            #not the list page
            return super().get_queryset(request)

        query_allowed = False
        for key in request.GET.keys():
            if key == "workload" or key.startswith("workload__"):
                query_allowed = True
                break
            elif key in ("id","pk") or key.startswith("id__") or key.startswith("pk__"):
                query_allowed = True
                break

        if query_allowed:
            return super().get_queryset(request)
        else:
            return models.ContainerLog.objects.none()

    def _container_terminated(self,obj):
        if not obj or not obj.container_terminated:
            return ""
        else:
            return timezone.localtime(obj.container_terminated).strftime("%Y-%m-%d %H:%M:%S")
    _container_terminated.short_description = "Container Terminated"

    def _container_started(self,obj):
        if not obj or not obj.container_started:
            return ""
        else:
            return timezone.localtime(obj.container_started).strftime("%Y-%m-%d %H:%M:%S")
    _container_started.short_description = "Container Started"

    def _container_created(self,obj):
        if not obj or not obj.container_created:
            return ""
        else:
            return timezone.localtime(obj.container_created).strftime("%Y-%m-%d %H:%M:%S")
    _container_created.short_description = "Container Created"

    def _pod_started(self,obj):
        if not obj or not obj.pod_started:
            return ""
        else:
            return timezone.localtime(obj.pod_started).strftime("%Y-%m-%d %H:%M:%S")
    _pod_started.short_description = "Pod Started"

    def _pod_created(self,obj):
        if not obj or not obj.pod_created:
            return ""
        else:
            return timezone.localtime(obj.pod_created).strftime("%Y-%m-%d %H:%M:%S")
    _pod_created.short_description = "Pod Created"

    def _last_checked(self,obj):
        if not obj or not obj.last_checked:
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
class ContainerLogAdmin(LookupAllowedMixin,ContainerLinkMixin,admin.ModelAdmin):
    list_display = ("_logtime",'_container_short',"level","source","_message")
    readonly_fields = ("_logtime",'_container',"level","source","_message")

    list_filter = ("level",)
    list_per_page = 500

    ordering = ("container__workload","-logtime")
    search_fields = ['container__id']
    show_full_result_count = False
    show_all = False

    containerlogs_url_name = '{}_{}_changelist'.format(models.ContainerLog._meta.app_label,models.ContainerLog._meta.model_name)
    def get_model_perms(self, request):
        """
        Return empty perms dict thus hiding the model from admin index.
        """
        return {}

    def get_changelist(self, request, **kwargs):
        """
        Return the ChangeList class for use on the changelist page.
        """
        return ReverseChangeList

    def get_queryset(self, request):
        if not resolve(request.path_info).url_name == self.containerlogs_url_name:
            #not the list page
            return super().get_queryset(request)

        query_allowed = False
        for key in request.GET.keys():
            if key == "container" or key.startswith("container__"):
                query_allowed = True
                break
            elif key in ("id","pk") or key.startswith("id__") or key.startswith("pk__"):
                query_allowed = True
                break

        if query_allowed:
            qs = super().get_queryset(request)
            return qs
        else:
            return models.ContainerLog.objects.none()

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


@admin.register(models.Harvester)
class HarvesterAdmin(DatetimeMixin,admin.ModelAdmin):
    list_display = ("name","get_status_display","_starttime","_last_heartbeat","_endtime","_short_message")
    readonly_fields = ("name","get_status_display","_starttime","_last_heartbeat","_endtime","_message")

    list_filter = ("name","status")

    ordering = ("name","-starttime")

    def _message(self,obj):
        if not obj or not obj.message:
            return ""
        elif "\n" in obj.message:
            return mark_safe("<pre>{}</pre>".format(obj.message))
        else:
            return mark_safe("<pre style='white-space:normal'>{}</pre>".format(obj.message))
    _message.short_description = "message"

    def _short_message(self,obj):
        if not obj or not obj.message:
            return ""
        else:
            return "{} ...".format(obj.message[:150])
    _short_message.short_description = "message"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(models.EnvScanModule)
class EnvScanModuleAdmin(DatetimeMixin,admin.ModelAdmin):
    list_display = ("resource_type","priority","multi","active","_modified","_added")

    readonly_fields = ("_modified","_added")

    list_filter = ("resource_type",)

    form = forms.EnvScanModuleForm

    list_url_name = '{}_{}_changelist'.format(models.EnvScanModule._meta.app_label,models.EnvScanModule._meta.model_name)
    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        if resolve(request.path_info).url_name == self.list_url_name:
            qs = qs.defer('sourcecode')
            pass

        return qs

@admin.register(models.ContainerImageFamily)
class ContainerImageFamilyAdmin(DatetimeMixin,admin.ModelAdmin):
    list_display = ("account","name","contacts","enable_notify","enable_warning_msg","_modified","_added")

    readonly_fields = ("account","name","_modified","_added")

    fields = ("account","name","contacts","enable_notify","enable_warning_msg","config","filtercode","_modified","_added")

    list_filter = ("account",)
    search_fields = ['name']

    form = forms.ContainerImageFamilyForm

    list_url_name = '{}_{}_changelist'.format(models.ContainerImageFamily._meta.app_label,models.ContainerImageFamily._meta.model_name)
    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        if resolve(request.path_info).url_name == self.list_url_name:
            qs = qs.defer('filtercode','config')
            pass

        return qs

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(models.WorkloadResource)
class WorkloadResourceAdmin(DatetimeMixin,admin.ModelAdmin):
    list_display = ("workload","imagefamily","resource_type","config_items","resource_id","config_source","_updated","_created")

    readonly_fields = ("workload","imagefamily","resource_type","config_items","resource_id","config_source","properties","scan_module","_updated","_created")

    list_filter = ("imagefamily","resource_type")
    search_fields = ['workload__name','resource_id']

    def get_queryset(self, request):
        qs =  super().get_queryset(request)
        qs = qs.select_related('workload',"imagefamily").only("resource_type","config_items","resource_id","config_source","properties","scan_module","updated","created","workload__cluster__name","workload__namespace__name","workload__name","imagefamily__account","imagefamily__name")
        return qs

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

