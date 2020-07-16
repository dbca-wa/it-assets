import subprocess
import json
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.utils import timezone


class Cluster(models.Model):
    name = models.CharField(max_length=64,unique=True)
    clusterid = models.CharField(max_length=64,null=True,editable=False)
    ip = models.CharField(max_length=128,null=True,editable=False)
    comments = models.TextField(null=True,blank=True)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    refreshed = models.DateTimeField(null=True,editable=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Project(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='projects',editable=False)
    name = models.CharField(max_length=64,null=True,blank=True,editable=True)
    projectid = models.CharField(max_length=64)

    def __str__(self):
        if self.name:
            return "{}.{}".format(self.cluster.name,self.name)
        else:
            return "{}.{}".format(self.cluster.name,self.projectid)

    class Meta:
        unique_together = [["cluster","projectid"]]
        ordering = ["cluster__name",'name']


class Namespace(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='namespaces',editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='namespaces',editable=False)
    name = models.CharField(max_length=64,editable=False)
    api_version = models.CharField(max_length=64,editable=False)
    modified = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(editable=False)

    def __str__(self):
        return "{}.{}".format(self.cluster.name,self.name)

    class Meta:
        unique_together = [["cluster","name"]]
        ordering = ["cluster__name",'name']


class PersistentVolume(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='volumes',editable=False)
    name = models.CharField(max_length=128,editable=False)
    kind = models.CharField(max_length=64,editable=False)
    storage_class_name = models.CharField(max_length=64,editable=False)
    volume_mode = models.CharField(max_length=64,editable=False)
    uuid = models.CharField(max_length=128,unique=True,editable=False)
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
        unique_together = [["cluster","name"],["cluster","volumepath"]]
        ordering = ["cluster__name",'name']


class PersistentVolumeClaim(models.Model):
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


class Ingress(models.Model):
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


class Workload(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='workloads', editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='workloads', editable=False)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='workloads', editable=False, null=True)
    name = models.CharField(max_length=128, editable=False)
    kind = models.CharField(max_length=64, editable=False)

    replicas = models.PositiveSmallIntegerField(editable=False, null=True)
    image = models.CharField(max_length=128, editable=False)
    image_pullpolicy = models.CharField(max_length=64, editable=False, null=True)
    image_scan_json = JSONField(default=dict, editable=False, blank=True)
    image_scan_timestamp = models.DateTimeField(editable=False, null=True, blank=True)
    cmd = models.CharField(max_length=512, editable=False, null=True)
    schedule = models.CharField(max_length=32, editable=False, null=True)
    suspend = models.NullBooleanField(editable=False)
    failedjobshistorylimit = models.PositiveSmallIntegerField(null=True, editable=False)
    successfuljobshistorylimit = models.PositiveSmallIntegerField(null=True, editable=False)
    concurrency_policy = models.CharField(max_length=128, editable=False, null=True)

    api_version = models.CharField(max_length=64, editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    refreshed = models.DateTimeField(auto_now=True)

    @property
    def viewurl(self):
        return "{0}/p/{1}:{2}/workload/{3}:{4}:{5}".format(settings.RANCHER_MANAGEMENT_URL,self.cluster.clusterid,self.project.projectid,self.kind.lower(),self.namespace.name,self.name)

    @property
    def managementurl(self):
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

    def image_scan_vulns(self):
        vulns = {}
        if self.image_scan_json and 'Vulnerabilities' in self.image_scan_json and self.image_scan_json['Vulnerabilities']:
            for v in self.image_scan_json['Vulnerabilities']:
                if 'Severity' not in vulns:
                    vulns[v['Severity']] = 1
                else:
                    vulns[v['Severity']] += 1
        return vulns

    class Meta:
        unique_together = [["cluster", "namespace", "name"]]
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

    class Meta:
        unique_together = [["workload","database","config_items"]]
        ordering = ['workload','database']
