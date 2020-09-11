import subprocess
import json
import re
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.urls import reverse
from django.utils import timezone
from django.db.models.signals import pre_save,pre_delete
from django.dispatch import receiver


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
        return "{0}/p/{1}:{2}/workloads".format(settings.RANCHER_MANAGEMENT_URL,self.cluster.clusterid,self.projectid)

    def __str__(self):
        if self.name:
            return "{}.{}".format(self.cluster.name,self.name)
        else:
            return "{}.{}".format(self.cluster.name,self.projectid)

    class Meta:
        unique_together = [["cluster","projectid"]]
        ordering = ["cluster__name",'name']

class DeletedMixin(models.Model):
    deleted = models.DateTimeField(editable=False,null=True)

    @property
    def is_deleted(self):
        return True if self.deleted else False

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

    def __str__(self):
        return "{}.{}".format(self.cluster.name,self.name)

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


class PersistentVolumeClaim(DeletedMixin,models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='volumeclaims',editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='volumeclaims',editable=False)
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
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='ingresses',editable=False)
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
        unique_together = [["ingress","protocol","hostname","path"],["cluster","servicename"]]


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
    schedule = models.CharField(max_length=32, editable=False, null=True)
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
        if self.added_by_log:
            return None
        else:
            return "{0}/p/{1}:{2}/workload/{3}:{4}:{5}".format(settings.RANCHER_MANAGEMENT_URL,self.cluster.clusterid,self.project.projectid,self.kind.lower(),self.namespace.name,self.name)

    @property
    def managementurl(self):
        if self.added_by_log:
            return None
        else:
            return "{0}/p/{1}:{2}/workloads/run?group=namespace&namespaceId={4}&upgrade=true&workloadId={3}:{4}:{5}".format(settings.RANCHER_MANAGEMENT_URL,self.cluster.clusterid,self.project.projectid,self.kind.lower(),self.namespace.name,self.name)

    @property
    def webapps(self):
        from nginx.models import WebAppLocationServer
        apps = set()
        for location_server in WebAppLocationServer.objects.filter(rancher_workload=self):
            apps.add(location_server.location.app)

        return apps

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
        unique_together = [["workload","servicename"]]


class WorkloadEnv(models.Model):
    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='envs',editable=False)
    name = models.CharField(max_length=128,editable=False)
    value = models.CharField(max_length=1024,editable=False,null=True)

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

    volume_claim = models.ForeignKey(PersistentVolumeClaim, on_delete=models.PROTECT, related_name='+',editable=False,null=True)
    volume = models.ForeignKey(PersistentVolume, on_delete=models.PROTECT, related_name='+',editable=False,null=True)
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
    container_terminated = models.DateTimeField(editable=False,null=True)
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
    logtime = models.DateTimeField(editable=False)
    level = models.PositiveSmallIntegerField(choices=LOG_LEVELS)
    source = models.CharField(max_length=32,null=True,editable=False)
    message = models.TextField(editable=False)

    archiveid = models.CharField(max_length=64,null=True,editable=False)

    class Meta:
        unique_together = [["container","logtime","level"]]
        index_together = [["container","level"],["archiveid"]]
        ordering = ["container","logtime"]


class WorkloadListener(object):
    @staticmethod
    @receiver(pre_save,sender=Workload)
    def save_workload(sender,instance,update_fields=None,**kwargs):
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
                    obj.active_workloads -= 1
                    obj.deleted_workloads += 1
                    return ["active_workloads","deleted_workloads"]
            else:
                def update_workloads(obj):
                    obj.active_workloads += 1
                    obj.deleted_workloads -= 1
                    return ["active_workloads","deleted_workloads"]

        else:
            #create
            if instance.deleted:
                def update_workloads(obj):
                    obj.deleted_workloads += 1
                    return ["deleted_workloads"]
            else:
                def update_workloads(obj):
                    obj.active_workloads += 1
                    return ["active_workloads"]
        
        for obj in [instance.namespace,instance.project,instance.cluster]:
            if not obj:
                continue
            update_fields = update_workloads(obj)
            obj.save(update_fields=update_fields)

    @staticmethod
    @receiver(pre_delete,sender=Workload)
    def delete_workload(sender,instance,**kwargs):
        if instance.deleted:
            def update_workloads(obj):
                obj.deleted_workloads -= 1
                return ["deleted_workloads"]
        else:
            def update_workloads(obj):
                obj.active_workloads -= 1
                return ["active_workloads"]

        for obj in [instance.namespace,instance.project,instance.cluster]:
            if not obj:
                continue
            update_fields = update_workloads(obj)
            obj.save(update_fields=update_fields)

        
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
            existing_obj.project.active_workloads -= instance.project.active_workloads
            existing_obj.project.deleted_workloads -= instance.project.deleted_workloads
            existing_obj.project.save(update_fields=["active_workloads","deleted_workloads"])

        if instance.project:
            instance.project.active_workloads += instance.project.active_workloads
            instance.project.deleted_workloads += instance.project.deleted_workloads
            instance.project.save(update_fields=["active_workloads","deleted_workloads"])

