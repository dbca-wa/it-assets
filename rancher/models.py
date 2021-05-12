import subprocess
import json
import logging
import re
from django.db import models,transaction
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.urls import reverse
from django.utils import timezone
from django.db.models.signals import pre_save,pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


class Cluster(models.Model):
    name = models.CharField(max_length=64,unique=True)
    clusterid = models.CharField(max_length=64,null=True,editable=False)
    ip = models.CharField(max_length=128,null=True,editable=False)
    comments = models.TextField(null=True,blank=True)
    added_by_log = models.BooleanField(editable=False,default=False)
    active_workloads = models.PositiveIntegerField(editable=False,default=0)
    deleted_workloads = models.PositiveIntegerField(editable=False,default=0)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    refreshed = models.DateTimeField(null=True,editable=False)
    succeed_resources = models.PositiveIntegerField(editable=False,default=0)
    failed_resources = models.PositiveIntegerField(editable=False,default=0)
    refresh_message = models.TextField(null=True,blank=True,editable=False)

    @classmethod
    def populate_workloads_4_all(cls):
        for cluster in cls.objects.all():
            cluster.populate_workloads()

    def populate_workloads(self):
        """
        Populate the worklods and deleted_workloads
        """
        active_workloads = Workload.objects.filter(cluster=self,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(cluster=self,deleted__isnull=False).count()
        update_fields = []
        if self.active_workloads != active_workloads:
            self.active_workloads = active_workloads
            update_fields.append("active_workloads")

        if self.deleted_workloads != deleted_workloads:
            self.deleted_workloads = deleted_workloads
            update_fields.append("deleted_workloads")

        if update_fields:
            self.save(update_fields=update_fields)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Project(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='projects',editable=False)
    name = models.CharField(max_length=64,null=True,blank=True,editable=True)
    projectid = models.CharField(max_length=64)
    active_workloads = models.PositiveIntegerField(editable=False,default=0)
    deleted_workloads = models.PositiveIntegerField(editable=False,default=0)

    @classmethod
    def populate_workloads_4_all(cls):
        for project in cls.objects.all():
            project.populate_workloads()

    def populate_workloads(self):
        """
        Populate the worklods and deleted_workloads
        """
        active_workloads = Workload.objects.filter(project=self,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(project=self,deleted__isnull=False).count()
        update_fields = []
        if self.active_workloads != active_workloads:
            self.active_workloads = active_workloads
            update_fields.append("active_workloads")

        if self.deleted_workloads != deleted_workloads:
            self.deleted_workloads = deleted_workloads
            update_fields.append("deleted_workloads")

        if update_fields:
            self.save(update_fields=update_fields)

    @property
    def managementurl(self):
        return "{0}/p/{1}:{2}/workloads".format(settings.GET_CLUSTER_MANAGEMENT_URL(self.cluster.name),self.cluster.clusterid,self.projectid)

    def __str__(self):
        if self.name:
            return "{}:{}".format(self.cluster.name,self.name)
        else:
            return "{}:{}".format(self.cluster.name,self.projectid)

    class Meta:
        unique_together = [["cluster","projectid"]]
        ordering = ["cluster__name",'name']

class DeletedMixin(models.Model):
    deleted = models.DateTimeField(editable=False,null=True)

    @property
    def is_deleted(self):
        return True if self.deleted else False

    def logically_delete(self):
        self.deleted = timezone.now()
        self.save(update_fields=["deleted"])
    

    class Meta:
        abstract = True

class Namespace(DeletedMixin,models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='namespaces',editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='namespaces',editable=False,null=True)
    name = models.CharField(max_length=64,editable=False)
    added_by_log = models.BooleanField(editable=False,default=False)
    active_workloads = models.PositiveIntegerField(editable=False,default=0)
    deleted_workloads = models.PositiveIntegerField(editable=False,default=0)
    api_version = models.CharField(max_length=64,editable=False,null=True)
    modified = models.DateTimeField(editable=False,null=True)
    refreshed = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(editable=False,null=True)

    @classmethod
    def populate_workloads_4_all(cls):
        for namespace in cls.objects.all():
            namespace.populate_workloads()

    def populate_workloads(self):
        """
        Populate the worklods and deleted_workloads
        """
        active_workloads = Workload.objects.filter(namespace=self,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(namespace=self,deleted__isnull=False).count()
        update_fields = []
        if self.active_workloads != active_workloads:
            self.active_workloads = active_workloads
            update_fields.append("active_workloads")

        if self.deleted_workloads != deleted_workloads:
            self.deleted_workloads = deleted_workloads
            update_fields.append("deleted_workloads")

        if update_fields:
            self.save(update_fields=update_fields)

    def save(self,*args,**kwargs):
        with transaction.atomic():
            return super().save(*args,**kwargs)

    def __str__(self):
        return "{}:{}".format(self.cluster.name,self.name)

    class Meta:
        unique_together = [["cluster","name"]]
        ordering = ["cluster__name",'name']


class PersistentVolume(DeletedMixin,models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='volumes',editable=False)
    name = models.CharField(max_length=128,editable=False)
    kind = models.CharField(max_length=64,editable=False)
    storage_class_name = models.CharField(max_length=64,editable=False)
    volume_mode = models.CharField(max_length=64,editable=False)
    uuid = models.CharField(max_length=128,editable=False)
    volumepath = models.CharField(max_length=256,editable=False,null=True)
    capacity = models.PositiveIntegerField(editable=False,null=True)
    writable = models.BooleanField(default=False,editable=False)
    reclaim_policy = models.CharField(max_length=64,editable=False,null=True)
    node_affinity = models.TextField(null=True,editable=False)
    api_version = models.CharField(max_length=64,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}:{}".format(self.cluster.name,self.name)

    class Meta:
        unique_together = [["cluster","name"],["cluster","volumepath"],["cluster","uuid"]]
        ordering = ["cluster__name",'name']

class ConfigMap(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='configmaps',editable=False)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='configmaps',editable=False)
    name = models.CharField(max_length=128,editable=False)
    api_version = models.CharField(max_length=64,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}:{}".format(self.namespace,self.name)

    class Meta:
        unique_together = [["cluster","namespace","name"]]
        ordering = ["cluster__name","namespace__name",'name']

class ConfigMapItem(models.Model):
    configmap = models.ForeignKey(ConfigMap, on_delete=models.CASCADE, related_name='items',editable=False)
    name = models.CharField(max_length=128,editable=False)
    value = models.TextField(max_length=1024,editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}.{}".format(self.configmap,self.name)

    class Meta:
        unique_together = [["configmap","name"]]
        ordering = ["configmap",'name']


class PersistentVolumeClaim(DeletedMixin,models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='volumeclaims',editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='volumeclaims',editable=False,null=True)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='volumeclaims',editable=False,null=True)
    volume = models.ForeignKey(PersistentVolume, on_delete=models.PROTECT, related_name='volumeclaims',editable=False,null=True)
    name = models.CharField(max_length=128,editable=False)
    writable = models.BooleanField(default=False,editable=False)
    api_version = models.CharField(max_length=64,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.volume:
            return "{}.{}".format(self.volume.name,self.name)
        else:
            return self.name

    class Meta:
        unique_together = [["volume","name"],["cluster","namespace","name"]]


class Ingress(DeletedMixin,models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='ingresses',editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='ingresses',editable=False,null=True)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='ingresses',editable=False,null=True)
    name = models.CharField(max_length=128,editable=False)

    api_version = models.CharField(max_length=64,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}.{}".format(self.namespace,self.name)

    class Meta:
        unique_together = [["cluster","namespace","name"]]
        ordering = ["cluster__name",'name']


class IngressRule(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='ingresserules',editable=False)
    ingress = models.ForeignKey(Ingress, on_delete=models.CASCADE, related_name='rules',editable=False)

    protocol = models.CharField(max_length=128,editable=False)
    hostname = models.CharField(max_length=128,editable=False)
    port = models.PositiveIntegerField(editable=False,null=True)
    path = models.CharField(max_length=256,editable=False,default="")

    servicename = models.CharField(max_length=256,editable=False)
    serviceport = models.PositiveIntegerField(editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    @property
    def is_deleted(self):
        return self.ingress.is_deleted

    @property
    def deleted(self):
        return self.ingress.deleted

    @property
    def listen(self):
        if self.path:
            return "{}://{}:{}/{}".format(self.protocol,self.hostname,self.port,self.path)
        else:
            return "{}://{}:{}".format(self.protocol,self.hostname,self.port)

    def __str__(self):
        if self.path:
            return "{}> {}://{}/{}".format(self.ingress,self.protocol,self.hostname,self.path)
        else:
            return "{}> {}://{}".format(self.ingress,self.protocol,self.hostname)

    class Meta:
        unique_together = [["ingress","protocol","hostname","path"],["ingress","servicename"]]
        index_together = [["cluster","servicename"]]


class Workload(DeletedMixin,models.Model):
    ERROR = 4
    WARNING = 2
    INFO = 1

    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='workloads', editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='workloads', editable=False,null=True)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='workloads', editable=False, null=True)
    name = models.CharField(max_length=512, editable=False)
    kind = models.CharField(max_length=64, editable=False)

    latest_containers = ArrayField(ArrayField(models.IntegerField(),size=3), editable=False,null=True)

    replicas = models.PositiveSmallIntegerField(editable=False, null=True)
    image = models.CharField(max_length=128, editable=False)
    image_pullpolicy = models.CharField(max_length=64, editable=False, null=True)
    image_scan_json = JSONField(default=dict, editable=False, blank=True)
    image_scan_timestamp = models.DateTimeField(editable=False, null=True, blank=True)
    cmd = models.CharField(max_length=2048, editable=False, null=True)
    schedule = models.CharField(max_length=128, editable=False, null=True)
    suspend = models.NullBooleanField(editable=False)
    failedjobshistorylimit = models.PositiveSmallIntegerField(null=True, editable=False)
    successfuljobshistorylimit = models.PositiveSmallIntegerField(null=True, editable=False)
    concurrency_policy = models.CharField(max_length=128, editable=False, null=True)

    api_version = models.CharField(max_length=64, editable=False)

    added_by_log = models.BooleanField(editable=False,default=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return reverse('workload_detail', kwargs={'pk': self.pk})

    @property
    def viewurl(self):
        if self.added_by_log or not self.project:
            return None
        else:
            return "{0}/p/{1}:{2}/workload/{3}:{4}:{5}".format(settings.GET_CLUSTER_MANAGEMENT_URL(self.cluster.name),self.cluster.clusterid,self.project.projectid,self.kind.lower(),self.namespace.name,self.name)

    @property
    def managementurl(self):
        if self.added_by_log or not self.project:
            return None
        else:
            return "{0}/p/{1}:{2}/workloads/run?group=namespace&namespaceId={4}&upgrade=true&workloadId={3}:{4}:{5}".format(settings.GET_CLUSTER_MANAGEMENT_URL(self.cluster.name),self.cluster.clusterid,self.project.projectid,self.kind.lower(),self.namespace.name,self.name)

    @property
    def webapps(self):
        from nginx.models import WebAppLocationServer
        apps = set()
        for location_server in WebAppLocationServer.objects.filter(rancher_workload=self):
            apps.add(location_server.location.app)

        return apps

    def save(self,*args,**kwargs):
        with transaction.atomic():
            return super().save(*args,**kwargs)

    def __str__(self):
        return "{}.{}.{}".format(self.cluster.name, self.namespace.name, self.name)

    def image_scan(self):
        """Runs trivy locally and saves the scan result.
        """
        if not self.image:
            return (False, None)

        try:
            cmd = 'trivy --quiet image --no-progress --format json {}'.format(self.image)
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            return (False, e.output)

        # trivy should return JSON, being a single-element list containing a dict of the scan results.
        out = json.loads(out)

        if not out:
            return (False, None)  # If the scan fails, trivy returns 'null'.
        self.image_scan_json = out[0]
        self.image_scan_timestamp = timezone.now()
        self.save()
        return (True, out)

    def get_image_scan_vulns(self):
        vulns = {}
        if self.image_scan_json and 'Vulnerabilities' in self.image_scan_json and self.image_scan_json['Vulnerabilities']:
            for v in self.image_scan_json['Vulnerabilities']:
                if v['Severity'] not in vulns:
                    vulns[v['Severity']] = 1
                else:
                    vulns[v['Severity']] += 1
        return vulns

    def _image_vulns_str(self):
        if not self.image_scan_json:
            return ''
        return ', '.join(['{}: {}'.format(k.capitalize(), v) for (k, v) in self.get_image_scan_vulns().items()])
    _image_vulns_str.short_description = 'Image vulnerabilities'

    def get_image_scan_os(self):
        if self.image_scan_json and 'Target' in self.image_scan_json and self.image_scan_json['Target']:
            pattern = '\\((.*?)\\)'
            match = re.search(pattern, self.image_scan_json['Target'])
            if match:
                return match.groups()[0].capitalize()
            else:
                return ''

    class Meta:
        unique_together = [["cluster", "namespace", "name","kind"]]
        ordering = ["cluster__name", 'namespace', 'name']


class WorkloadListening(models.Model):
    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='listenings',editable=False)
    servicename = models.CharField(max_length=128,editable=False)
    container_port = models.PositiveIntegerField(editable=False)
    protocol = models.CharField(max_length=16,editable=False)

    ingress_rule = models.ForeignKey(IngressRule, on_delete=models.CASCADE, related_name='listenings',editable=False,null=True)
    listen_port = models.PositiveIntegerField(editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    @property
    def is_deleted(self):
        return self.workload.is_deleted or (self.ingress_rule.is_deleted if self.ingress_rule else False)

    @property
    def deleted(self):
        return self.workload.deleted or (self.ingress_rule.deleted if self.ingress_rule else None)

    @property
    def listen(self):
        if self.ingress_rule:
            return self.ingress_rule.listen
        elif self.listen_port:
            return "{}://{}:{}".format(self.protocol,self.workload.cluster.name,self.listen_port)
        else:
            return ""

    def __str__(self):
        return "{}.{}".format(self.workload,self.servicename)

    class Meta:
        unique_together = [["workload","servicename","ingress_rule"]]


class WorkloadEnv(models.Model):
    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='envs',editable=False)
    configmap = models.ForeignKey(ConfigMap, on_delete=models.CASCADE, related_name='workloadenvs',editable=False,null=True)
    configmapitem = models.ForeignKey(ConfigMapItem, on_delete=models.CASCADE, related_name='workloadenvs',editable=False,null=True)

    name = models.CharField(max_length=128,editable=False)
    value = models.TextField(editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    @property
    def is_deleted(self):
        return self.workload.is_deleted

    @property
    def deleted(self):
        return self.workload.deleted

    def __str__(self):
        return "{}.{}".format(self.workload,self.name)

    class Meta:
        unique_together = [["workload","name"]]
        ordering = ["workload",'name']


class WorkloadVolume(models.Model):
    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='volumes',editable=False)
    name = models.CharField(max_length=128,editable=False)

    mountpath = models.CharField(max_length=128,editable=False)
    subpath = models.CharField(max_length=128,editable=False,null=True)

    volume_claim = models.ForeignKey(PersistentVolumeClaim, on_delete=models.CASCADE, related_name='+',editable=False,null=True)
    volume = models.ForeignKey(PersistentVolume, on_delete=models.CASCADE, related_name='+',editable=False,null=True)
    volumepath = models.CharField(max_length=612,editable=False,null=True)
    other_config = models.TextField(null=True)

    writable = models.BooleanField(default=False,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    @property
    def is_deleted(self):
        if self.workload.is_deleted:
            return True
        if self.volume_claim and self.volume_claim.is_deleted:
            return True
        if self.volume and self.volume.is_deleted:
            return True
        return False

    @property
    def deleted(self):
        if self.workload.deleted:
            return self.workload.deleted
        if self.volume_claim and self.volume_claim.deleted:
            return self.volume_claim.deleted
        if self.volume and self.volume.deleted:
            return self.volume.deleted
        return None

    def __str__(self):
        return "{}.{}".format(self.workload,self.name)

    class Meta:
        unique_together = [["workload","name"],["workload","mountpath"]]
        ordering = ["workload",'name']


class DatabaseServer(models.Model):
    POSTGRES = "posgres"
    MYSQL = "mysql"
    ORACLE = "oracle"
    SERVER_KINDS = (
        (POSTGRES,POSTGRES),
        (MYSQL,MYSQL),
        (ORACLE,ORACLE),
    )
    host = models.CharField(max_length=128,editable=False)
    ip = models.CharField(max_length=32,editable=False,null=True)
    port = models.PositiveIntegerField(editable=False,null=True)
    internal_name = models.CharField(max_length=128,editable=False,null=True)
    internal_port = models.PositiveIntegerField(editable=False,null=True)
    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='+',editable=False,null=True)
    other_names = ArrayField(models.CharField(max_length=128),editable=False,null=True)
    kind = models.CharField(max_length=16,choices=SERVER_KINDS,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.kind == "postgres" and self.port == 5432:
            return self.host
        else:
            return "{}:{}".format(self.host,self.port)

    class Meta:
        index_together = [["host","port"],["internal_name","internal_port"]]
        ordering = ['host','port']


class Database(models.Model):
    server = models.ForeignKey(DatabaseServer, on_delete=models.CASCADE, related_name='databases',editable=False)
    name = models.CharField(max_length=128,editable=False)

    created = models.DateTimeField(editable=False)

    def __str__(self):
        return "{}/{}".format(self.server,self.name)

    class Meta:
        ordering = ['server','name']


class DatabaseUser(models.Model):
    server = models.ForeignKey(DatabaseServer, on_delete=models.CASCADE, related_name='users',editable=False)
    user = models.CharField(max_length=128,editable=False)
    password = models.CharField(max_length=128,editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user

    class Meta:
        unique_together = [["server","user"]]
        ordering = ['server','user']


class WorkloadDatabase(models.Model):
    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='databases',editable=False)
    database = models.ForeignKey(Database, on_delete=models.PROTECT, related_name='+',editable=False)
    user = models.ForeignKey(DatabaseUser, on_delete=models.PROTECT, related_name='+',editable=False)

    password = models.CharField(max_length=128,editable=False,null=True)
    schema = models.CharField(max_length=128,editable=False,null=True)

    config_items = models.CharField(max_length=256,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    @property
    def is_deleted(self):
        return self.workload.is_deleted

    @property
    def deleted(self):
        return self.workload.deleted

    class Meta:
        unique_together = [["workload","database","config_items"]]
        ordering = ['workload','database']

class Container(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='containers',editable=False)
    namespace = models.ForeignKey(Namespace, on_delete=models.CASCADE, related_name='containers',editable=False)
    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='containers',editable=False)

    poduid = models.CharField(max_length=128,editable=False)
    containerid = models.CharField(max_length=128,editable=False)

    podip = models.CharField(max_length=24,editable=False,null=True)
    image = models.CharField(max_length=128, editable=False,null=True)
    exitcode = models.CharField(max_length=8,null=True,editable=False)
    ports = models.CharField(max_length=1024,null=True,editable=False)
    envs = models.TextField(null=True,editable=False)

    log = models.BooleanField(editable=False,default=False)
    warning = models.BooleanField(editable=False,default=False)
    error = models.BooleanField(editable=False,default=False)

    status = models.CharField(max_length=16,null=True,editable=False)

    pod_created = models.DateTimeField(editable=False,null=True)
    pod_started = models.DateTimeField(editable=False,null=True)
    container_created = models.DateTimeField(editable=False,null=True)
    container_started = models.DateTimeField(editable=False,null=True)
    container_terminated = models.DateTimeField(editable=False,null=True,db_index=True)
    last_checked = models.DateTimeField(editable=False)

    @property
    def started(self):
        return self.container_started or self.container_created or self.pod_started or self.pod_created

    class Meta:
        unique_together = [["cluster","namespace","workload","containerid"],["cluster","workload","containerid"],["cluster","containerid"],["workload","containerid"]]
        ordering = ["cluster","namespace","workload","container_created"]

class ContainerLog(models.Model):
    TRACE = 1
    DEBUG = 100
    INFO = 200
    WARNING = 300
    ERROR = 400
    LOG_LEVELS = [
        (TRACE,"Trace"),
        (DEBUG,"Debug"),
        (INFO,"Info"),
        (WARNING,"Warning"),
        (ERROR,"Error"),
    ]
    container = models.ForeignKey(Container, on_delete=models.CASCADE, related_name='logs',editable=False)
    logtime = models.DateTimeField(editable=False,db_index=True)
    level = models.PositiveSmallIntegerField(choices=LOG_LEVELS)
    source = models.CharField(max_length=32,null=True,editable=False)
    message = models.TextField(editable=False)

    archiveid = models.CharField(max_length=64,null=True,editable=False)

    class Meta:
        index_together = [["container","logtime","level"],["container","level"],["archiveid"]]
        ordering = ["container","logtime"]


class WorkloadListener(object):
    @staticmethod
    @receiver(pre_save,sender=Workload)
    def save_workload(sender,instance,update_fields=None,**kwargs):
        existing_obj = None
        if instance.pk:
            if update_fields:
                if "deleted" not in update_fields:
                    return
            existing_obj = Workload.objects.get(id=instance.id)
            if existing_obj.deleted is None and instance.deleted is None:
                return
            elif existing_obj.deleted is not None and instance.deleted is not None:
                return

        if instance.pk:
            #update
            if instance.deleted :
                def update_workloads(obj):
                    obj.__class__.objects.filter(pk=obj.pk).update(active_workloads=models.F("active_workloads") - 1,deleted_workloads=models.F("deleted_workloads") + 1)
            else:
                def update_workloads(obj):
                    obj.__class__.objects.filter(pk=obj.pk).update(active_workloads=models.F("active_workloads") + 1,deleted_workloads=models.F("deleted_workloads") - 1)

        else:
            #create
            if instance.deleted:
                def update_workloads(obj):
                    obj.__class__.objects.filter(pk=obj.pk).update(deleted_workloads=models.F("deleted_workloads") + 1)
            else:
                def update_workloads(obj):
                    obj.__class__.objects.filter(pk=obj.pk).update(active_workloads=models.F("active_workloads") + 1)

        for obj in [instance.namespace,instance.project,instance.cluster]:
            if not obj:
                continue
            update_workloads(obj)

    @staticmethod
    @receiver(pre_delete,sender=Workload)
    def delete_workload(sender,instance,**kwargs):
        if instance.deleted:
            def update_workloads(obj):
                obj.__class__.objects.filter(pk=obj.pk).update(deleted_workloads=models.F("deleted_workloads") - 1)
        else:
            def update_workloads(obj):
                obj.__class__.objects.filter(pk=obj.pk).update(active_workloads=models.F("active_workloads") - 1)

        for obj in [instance.namespace,instance.project,instance.cluster]:
            if not obj:
                continue
            update_workloads(obj)

class NamespaceListener(object):
    @staticmethod
    @receiver(pre_save,sender=Namespace)
    def save_namespace(sender,instance,update_fields=None,**kwargs):
        if not instance.pk:
            #new namespace
            return

        if update_fields:
            if "project" not in update_fields:
                #project is not changed
                return

        existing_obj = Namespace.objects.get(id=instance.id)
        if existing_obj.project == instance.project:
            return

        if existing_obj.project:
            Project.objects.filter(pk = existing_obj.project.pk).update(
                active_workloads=models.F("active_workloads") - instance.active_workloads,
                deleted_workloads=models.F("deleted_workloads") - instance.deleted_workloads
            )

        if instance.project:
            Project.objects.filter(pk = instance.project.pk).update(
                active_workloads=models.F("active_workloads") + instance.active_workloads,
                deleted_workloads=models.F("deleted_workloads") + instance.deleted_workloads
            )


def sync_project():
    """
    Synchronize namespace's project with the project of workload, ingress and PersistentVolumeClaim
    """
    #assign namespace's project to workload's project
    for obj in Workload.objects.filter(namespace__project__isnull=False).exclude(project=models.F("namespace__project")):
        obj.project = obj.namespace.project
        obj.save(update_fields=["project"])

    #set workload's project to None if namespace's project is none
    for obj in Workload.objects.filter(namespace__project__isnull=True).filter(project__isnull=False):
        obj.project = None
        obj.save(update_fields=["project"])

    #assign namespace's project to ingress's project
    for obj in Ingress.objects.filter(namespace__isnull=False,namespace__project__isnull=False).exclude(project=models.F("namespace__project")):
        obj.project = obj.namespace.project
        obj.save(update_fields=["project"])

    #set ingress's project to None if namespace's project is none
    for obj in Ingress.objects.filter(models.Q(namespace__isnull=True) | models.Q(namespace__project__isnull=True)).filter(project__isnull=False):
        obj.project = None
        obj.save(update_fields=["project"])

    #assign namespace's project to persistentvolumeclaim's project
    for obj in PersistentVolumeClaim.objects.filter(namespace__isnull=False,namespace__project__isnull=False).exclude(project=models.F("namespace__project")):
        obj.project = obj.namespace.project
        obj.save(update_fields=["project"])

    #set persistentvolumeclaim's project to None if namespace's project is none
    for obj in PersistentVolumeClaim.objects.filter(models.Q(namespace__isnull=True) | models.Q(namespace__project__isnull=True)).filter(project__isnull=False):
        obj.project = None
        obj.save(update_fields=["project"])

def check_project():
    """
    Check whether the namespace's project is the same as the project of workload, ingress and PersistentVolumeClaim, and print the result
    """
    objs = list(Workload.objects.filter(namespace__project__isnull=False).exclude(project=models.F("namespace__project")))
    objs += list(Workload.objects.filter(namespace__project__isnull=True).filter(project__isnull=False))
    if objs:
        print("The following workloads'project are not equal with namespace's project.{}\n".format(["{}({})".format(o,o.id) for o in objs]))

    objs = list(Ingress.objects.filter(namespace__isnull=False,namespace__project__isnull=False).exclude(project=models.F("namespace__project")))
    objs += list(Ingress.objects.filter(models.Q(namespace__isnull=True) | models.Q(namespace__project__isnull=True)).filter(project__isnull=False))
    if objs:
        print("The following ingresses'project are not equal with namespace's project.{}\n".format(["{}({})".format(o,o.id) for o in objs]))

    objs = list(PersistentVolumeClaim.objects.filter(namespace__isnull=False,namespace__project__isnull=False).exclude(project=models.F("namespace__project")))
    objs += list(PersistentVolumeClaim.objects.filter(models.Q(namespace__isnull=True) | models.Q(namespace__project__isnull=True)).filter(project__isnull=False))
    if objs:
        print("The following PersistentVolumeClaims'project are not equal with namespace's project.{}\n".format(["{}({})".format(o,o.id) for o in objs]))

def check_workloads():
    """
    Check whether the active and deleted workloads is the same as the value of column 'active_workloads' and 'deleted_workloads' in model 'Namespace','Project' and 'Cluster' and print the result
    """
    for obj in Namespace.objects.all():
        active_workloads = Workload.objects.filter(namespace=obj,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(namespace=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            print("Namespace({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))


    for obj in Project.objects.all():
        active_workloads = Workload.objects.filter(namespace__project=obj,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(namespace__project=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            print("Project({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))

    for obj in Cluster.objects.all():
        active_workloads = Workload.objects.filter(cluster=obj,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(cluster=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            print("Cluster({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))

def sync_workloads():
    """
    Update the column 'active_workoads' and 'deleted_workloads' in model 'Namespace', 'Project' and 'Cluster' to the active workloads and deleted workloads

    """
    for obj in Namespace.objects.all():
        active_workloads = Workload.objects.filter(namespace=obj,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(namespace=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            print("Namespace({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))
            obj.active_workloads = active_workloads
            obj.deleted_workloads = deleted_workloads
            obj.save(update_fields=["active_workloads","deleted_workloads"])


    for obj in Project.objects.all():
        active_workloads = Workload.objects.filter(namespace__project=obj,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(namespace__project=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            print("Project({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))
            obj.active_workloads = active_workloads
            obj.deleted_workloads = deleted_workloads
            obj.save(update_fields=["active_workloads","deleted_workloads"])

    for obj in Cluster.objects.all():
        active_workloads = Workload.objects.filter(cluster=obj,deleted__isnull=True).count()
        deleted_workloads = Workload.objects.filter(cluster=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            print("Cluster({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))
            obj.active_workloads = active_workloads
            obj.deleted_workloads = deleted_workloads
            obj.save(update_fields=["active_workloads","deleted_workloads"])

def clean_containers():
    """
    clean all containers and container logs,
    sync projects and workloads
    """
    sync_workloads()
    ContainerLog.objects.all().delete()
    Container.objects.all().delete()
    Workload.objects.filter(added_by_log=True).delete()
    Namespace.objects.filter(added_by_log=True).delete()
    Cluster.objects.filter(added_by_log=True).delete()
    Workload.objects.all().update(deleted=None,latest_containers=None)
    sync_project()
    sync_workloads()

def clean_containerlogs():
    """
    Clear all container logs
    """
    ContainerLog.objects.all().delete()
    Container.objects.all().update(log=False,warning=False,error=False)
    for workload in Workload.objects.all():
        if workload.latest_containers:
            for container in workload.latest_containers:
                container[2] = 0
            workload.save(update_fields=["latest_containers"])

def clean_added_by_log_data():
    """
    Clean all the data which is added by log
    """
    deleted_rows = ContainerLog.objects.filter(container__workload__added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Container.objects.filter(workload__added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = Ingress.objects.filter(namespace__added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = Workload.objects.filter(added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = PersistentVolume.objects.filter(cluster__added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = PersistentVolumeClaim.objects.filter(cluster__added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = ConfigMap.objects.filter(namespace__added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = Namespace.objects.filter(added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Project.objects.filter(cluster__added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Cluster.objects.filter(added_by_log=True).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def clean_expired_deleted_data():
    expired_time = timezone.now() - settings.DELETED_RANCHER_OBJECT_EXPIRED
    deleted_rows = ContainerLog.objects.filter(container__workload__deleted__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Container.objects.filter(workload__deleted__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = Ingress.objects.filter(deleted__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Workload.objects.filter(deleted__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


    deleted_rows = PersistentVolumeClaim.objects.filter(volume__deleted__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = PersistentVolume.objects.filter(deleted__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Namespace.objects.filter(deleted__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def clean_expired_containers():
    expired_time = timezone.now() - settings.RANCHER_CONTAINER_EXPIRED

    deleted_rows = ContainerLog.objects.filter(container__container_terminated__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Container.objects.filter(container_terminated__lt = expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def clean_expired_containerlogs():
    expired_time = timezone.now() - settings.RANCHER_CONTAINERLOG_EXPIRED
    
    deleted_rows = ContainerLog.objects.filter(logtime__lt=expired_time).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def delete_cluster(idorname):
    """
    delete cluster
    """
    try:
        cluster = Cluster.objects.get(id=int(idorname))
    except:
        cluster = Cluster.objects.get(name=str(idorname))

    deleted_rows = ContainerLog.objects.filter(container__cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Container.objects.filter(cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = Workload.objects.filter(cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = Ingress.objects.filter(cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = PersistentVolumeClaim.objects.filter(cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = PersistentVolume.objects.filter(cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = ConfigMap.objects.filter(cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = Namespace.objects.filter(cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = Project.objects.filter(cluster=cluster).delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = cluster.delete()
    print("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    

def sync_latestcontainers():
    """
    Reset the latest containers
    """
    Workload.objects.all().update(latest_containers=None)
    workloads = {}
    for container in Container.objects.all().order_by("id"):
        workload_key = (container.workload.cluster.id,container.workload.namespace.name,container.workload.name,container.workload.kind)
        if workload_key not in workloads:
            workload_update_fields = []
            workload = container.workload
            workloads[workload_key] = (workload,workload_update_fields)
        else:
            workload,workload_update_fields = workloads[workload_key]

        log_status = (Workload.INFO if container.log else 0) | (Workload.WARNING if container.warning else 0) | (Workload.ERROR if container.error else 0)
        if workload.kind in ("Deployment",'DaemonSet','StatefulSet','service?'):
            if container.status in ("Waiting","Running"):
                if workload.latest_containers is None:
                    workload.latest_containers=[[container.id,1,log_status]]
                    if "latest_containers" not in workload_update_fields:
                        workload_update_fields.append("latest_containers")
                elif any(obj for obj in workload.latest_containers if obj[0] == container.id):
                    pass
                else:
                    workload.latest_containers.append([container.id,1,log_status])
                    if "latest_containers" not in workload_update_fields:
                        workload_update_fields.append("latest_containers")
            elif workload.latest_containers :
                index = len(workload.latest_containers) - 1
                while index >= 0:
                    if workload.latest_containers[index][0] == container.id:
                        del workload.latest_containers[index]
                        if "latest_containers" not in workload_update_fields:
                            workload_update_fields.append("latest_containers")
                        break
                    else:
                        index -= 1
        else:
            if workload.latest_containers is None or len(workload.latest_containers) != 1 or workload.latest_containers[0][0] != container.id:
                if container.status in ("Waiting","Running"):
                    workload.latest_containers=[[container.id,1,log_status]]
                else:
                    workload.latest_containers=[[container.id,0,log_status]]
                if "latest_containers" not in workload_update_fields:
                    workload_update_fields.append("latest_containers")
            else:
                if container.status in ("Waiting","Running"):
                    workload.latest_containers[0][1]=1
                else:
                    workload.latest_containers[0][1]=0
                if "latest_containers" not in workload_update_fields:
                    workload_update_fields.append("latest_containers")


    for workload,workload_update_fields in workloads.values():
        if not workload_update_fields:
            continue

        logger.debug("Workload({}<{}>):update latest_containers to {}".format(workload,workload.id,workload.latest_containers))
        workload.save(update_fields=workload_update_fields)



