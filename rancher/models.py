import subprocess
import json
import logging
import re
from django.db import models,transaction
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.urls import reverse
from django.utils import timezone
from django.db.models.signals import pre_save,pre_delete,m2m_changed
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
        verbose_name_plural = "{}{}".format(" " * 10,"Clusters")


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
        verbose_name_plural = "{}{}".format(" " * 9,"Projects")

class DeletedMixin(models.Model):
    deleted = models.DateTimeField(editable=False,null=True,db_index=True)

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
        verbose_name_plural = "{}{}".format(" " * 8,"Namespaces")


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
        verbose_name_plural = "{}{}".format(" " * 6,"Persistent volumes")

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
        verbose_name_plural = "{}{}".format(" " * 7,"Config maps")

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

class OperatingSystem(models.Model):
    name = models.CharField(max_length=64,editable=False)
    version = models.CharField(max_length=64,editable=False,null=True)
    images = models.SmallIntegerField(editable=False,default=0)
    criticals = models.SmallIntegerField(editable=False,default=0)
    highs = models.SmallIntegerField(editable=False,default=0)
    mediums = models.SmallIntegerField(editable=False,default=0)
    lows = models.SmallIntegerField(editable=False,default=0)
    unknowns = models.SmallIntegerField(editable=False,default=0)


    target_re = re.compile("^\s*(?P<image>[^\s]+)\s+\(\s*(?P<osname>[^\s]+)\s+(?P<osversion>[^\s]+)\s*\)\s*$")
    @classmethod
    def parse_scan_result(cls,scan_result):
        if not scan_result:
            raise Exception("Failed to detect the operating system")

        osname = None
        osversion = None
        if scan_result.get("Target"):
            m = cls.target_re.search(scan_result.get("Target"))
            if m:
                osname = m.group("osname").lower()
                osversion = m.group("osversion") or None
        if not osname:
            osname = scan_result.get("Type").lower()

        if osname:
            imageos,created = cls.objects.get_or_create(name=osname,version=osversion)
            return imageos

        raise Exception("Failed to detect the operating system")


    def __str__(self):
        if self.version:
            return "{} {}".format(self.name,self.version)
        else:
            return self.name

    class Meta:
        unique_together = [["name","version"]]
        ordering = ['name','version']
        verbose_name_plural = "{}{}".format(" " * 3,"OperatingSystems")

class Vulnerability(models.Model):
    LOW = 2
    MEDIUM = 4
    HIGH = 8
    CRITICAL = 16
    UNKNOWN = 32

    SEVERITIES = (
        (LOW,"Low"),
        (MEDIUM,"Medium"),
        (HIGH,"High"),
        (CRITICAL,"Critical"),
        (UNKNOWN,"Unknown"),
    )

    vulnerabilityid = models.CharField(max_length=128, editable=False)
    pkgname = models.CharField(max_length=128, editable=False)
    installedversion = models.CharField(max_length=128, editable=False)
    vulnerabilityid = models.CharField(max_length=128, editable=False)
    severity = models.SmallIntegerField(choices=SEVERITIES,editable=False,db_index=True)
    severitysource = models.CharField(max_length=64, editable=False,null=True)
    affected_images = models.SmallIntegerField(editable=False,default=0)
    affected_oss = models.SmallIntegerField(editable=False,default=0)
    description = models.TextField(editable=False,null=True)
    fixedversion = models.CharField(max_length=128, editable=False,null=True)
    publisheddate = models.CharField(max_length=64, editable=False,null=True)
    lastmodifieddate = models.CharField(max_length=64, editable=False,null=True)
    scan_result = JSONField(null=True,editable=False)
    oss= models.ManyToManyField(OperatingSystem,editable=False)

    @classmethod
    def get_severity(cls,severityname):
        for k,v in cls.SEVERITIES:
            if v.lower() == severityname:
                return k

        raise Exception("Unknown severity name '{}'".format(severityname))

    @classmethod
    def parse_scan_result(cls,os,scan_result):
        obj = Vulnerability.objects.get_or_create(
            vulnerabilityid=scan_result["VulnerabilityID"],
            pkgname=scan_result["PkgName"],
            installedversion=scan_result["InstalledVersion"],
            defaults = {
                "severity":cls.get_severity(scan_result["Severity"].lower()),
                "severitysource":scan_result.get("SeveritySource"),
                "description": scan_result.get("Description"),
                "fixedversion":scan_result.get("FixedVersion"),
                "publisheddate":scan_result.get("PublishedDate"),
                "lastmodifieddate":scan_result.get("LastModifiedDate"),
                "scan_result":scan_result
            }
        )[0]
        if not obj.oss.filter(id=os.id).exists():
            obj.oss.add(os)

        return obj


    def __str__(self):
        if self.installedversion:
            return "{} {}".format(self.pkgname,self.installedversion)
        else:
            return self.pkgname


    class Meta:
        unique_together = [["vulnerabilityid","pkgname","installedversion"]]
        index_together = [["pkgname","installedversion"],["severity","pkgname","installedversion"]]
        ordering = ['severity','pkgname','installedversion','vulnerabilityid']
        verbose_name_plural = "{}{}".format(" " * 2,"Vulnerabilities")



class ContainerImage(DeletedMixin,models.Model):
    NOT_SCANED = 0
    SCAN_FAILED = -1
    PARSE_FAILED = -2
    NO_RISK = 1
    LOW_RISK = 2
    MEDIUM_RISK = 4
    HIGH_RISK = 8
    CRITICAL_RISK = 16
    UNKNOWN_RISK = 32

    STATUSES = (
        (NOT_SCANED,"Not Scan"),
        (SCAN_FAILED,"Scan Failed"),
        (PARSE_FAILED,"Parse Failed"),
        (NO_RISK,"No Risk"),
        (LOW_RISK,"Low Risk"),
        (MEDIUM_RISK,"Medium Risk"),
        (HIGH_RISK,"High Risk"),
        (CRITICAL_RISK,"Critical Risk"),
        (UNKNOWN_RISK,"Unknown Risk")
    )
    account = models.CharField(max_length=64,null=True,db_index=True,editable=False)
    name = models.CharField(max_length=128, editable=False)
    tag = models.CharField(max_length=64, editable=False,null=True)
    os = models.ForeignKey(OperatingSystem, on_delete=models.PROTECT, related_name='containerimages', editable=False,null=True)
    workloads = models.PositiveSmallIntegerField(default=0,editable=False)
    scan_status = models.SmallIntegerField(choices=STATUSES,editable=False,db_index=True,default=NOT_SCANED)
    scaned = models.DateTimeField(editable=False,null=True)
    scan_result = JSONField(editable=False, null=True)
    scan_message = models.TextField(null=True,editable=False)
    criticals = models.SmallIntegerField(editable=False,default=0)
    highs = models.SmallIntegerField(editable=False,default=0)
    mediums = models.SmallIntegerField(editable=False,default=0)
    lows = models.SmallIntegerField(editable=False,default=0)
    unknowns = models.SmallIntegerField(editable=False,default=0)
    added = models.DateTimeField(auto_now=True)
    vulnerabilities = models.ManyToManyField(Vulnerability,editable=False)


    @classmethod
    def parse_imageid(cls,imageid,scan=False):
        """
        Return image
        """
        imageid = imageid.strip() if imageid else None
        if not imageid :
            return None
        if ":" in imageid:
            image_without_tag,image_tag = imageid.rsplit(":",1)
        else:
            image_tag = None
            image_without_tag = imageid

        if "/" in image_without_tag:
            account,image_name = image_without_tag.rsplit("/",1)
        else:
            account = None
            image_name = image_without_tag


        image,created = ContainerImage.objects.get_or_create(account=account,name=image_name,tag=image_tag)
        if image.scan_status == cls.NOT_SCANED  and scan:
            image.scan()
        return image

    def parse_vulnerabilities(self):
        self.scan_status = self.NO_RISK
        self.lows = 0
        self.mediums = 0
        self.highs = 0
        self.highs = 0
        self.criticals = 0
        self.unknowns = 0
        if not self.scan_result or not self.scan_result.get("Vulnerabilities"):
            return

        if not self.os:
            self.os = OperatingSystem.parse_scan_result(self.scan_result)

        vulns = []
        for vuln in  self.scan_result['Vulnerabilities']:
            vulns.append(Vulnerability.parse_scan_result(self.os,vuln))

        vulns.sort(key=lambda o:o.severity,reverse=True)
        existed_vulns = set()
        #remove deleted vulns
        for vul in list(self.vulnerabilities.all()):
            found = False
            for o in vulns:
                if vul == o:
                    found = True
                    existed_vulns.add(o.id)
                    break
            if not found:
                self.vulnerabilities.remove(vul)

        summary = {}
        for vuln in vulns:
            if vuln.id not in existed_vulns:
                self.vulnerabilities.add(vuln)
            summary[vuln.severity] = summary.get(vuln.severity,0) + 1

        for severity,field_name,status in (
            (Vulnerability.UNKNOWN,"unknowns",self.CRITICAL_RISK),
            (Vulnerability.CRITICAL,"criticals",self.CRITICAL_RISK),
            (Vulnerability.HIGH,"highs",self.HIGH_RISK),
            (Vulnerability.MEDIUM,"mediums",self.MEDIUM_RISK),
            (Vulnerability.LOW,"lows",self.LOW_RISK)
        ):
            if summary.get(severity):
                if self.scan_status == self.NO_RISK:
                    self.scan_status = status
                setattr(self,field_name,summary.get(severity))


    def scan(self,rescan=False,reparse=False):
        """Runs trivy locally and saves the scan result.

        """
        with transaction.atomic():
            if rescan or not self.scan_result:
                try:
                    rescan = True
                    reparse = True
                    cmd = 'trivy --quiet image --no-progress --format json {}'.format(self.imageid)
                    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)

                    # trivy should return JSON, being a single-element list containing a dict of the scan results.
                    out = json.loads(out)

                    if out and out[0]:
                        self.scan_result = out[0]
                    else:
                        # If the scan fails, trivy returns 'null'
                        raise Exception("No results is returned from trivy")
                except subprocess.CalledProcessError as e:
                    try:
                        output = e.output.decode()
                    except:
                        output = e.output

                    logger.error("Failed to scan container image.CalledProcessError({})".format(output))
                    self.scan_status = self.SCAN_FAILED
                    self.scan_result = None
                    self.scan_message = "CalledProcessError({})".format(output or "Unknown Error")
                    self.lows = 0
                    self.mediums = 0
                    self.highs = 0
                    self.criticals = 0
                    self.unknowns = 0
                    if self.pk:
                        self.vulnerabilities.clear()
                except Exception as e:
                    logger.error("Failed to scan container image.{}({})".format(e.__class__.__name__,str(e)))
                    self.scan_status = self.SCAN_FAILED
                    self.scan_result = None
                    self.scan_message = "{}({})".format(e.__class__.__name__,str(e))
                    self.lows = 0
                    self.mediums = 0
                    self.highs = 0
                    self.criticals = 0
                    self.unknowns = 0
                    if self.pk:
                        self.vulnerabilities.clear()
                finally:
                    self.scaned = timezone.now()

            if self.scan_result and (reparse or self.scan_status in (self.NOT_SCANED,self.SCAN_FAILED,self.PARSE_FAILED)):
                try:
                    reparse = True
                    self.os = OperatingSystem.parse_scan_result(self.scan_result)
                    self.parse_vulnerabilities()
                    self.scan_message = None
                except Exception as e:
                    logger.error("Failed to parse the scan result of the container image.{}({})".format(e.__class__.__name__,str(e)))
                    self.scan_status = self.PARSE_FAILED
                    self.scan_message = "{}({})".format(e.__class__.__name__,str(e))
                    self.lows = 0
                    self.mediums = 0
                    self.highs = 0
                    self.criticals = 0
                    self.unknowns = 0
                    self.vulnerabilities.clear()

            if self.pk:
                if rescan:
                    self.save(update_fields=["scan_result","scan_status","unknowns","criticals","highs","mediums","lows","scan_message","scaned","os"])
                elif reparse:
                    self.save(update_fields=["scan_status","unknowns","criticals","highs","mediums","lows","scan_message","os"])
            else:
                self.save()

    @property
    def imageid(self):
        if self.account:
            if self.tag:
                return "{}/{}:{}".format(self.account,self.name, self.tag)
            else:
                return "{}/{}".format(self.account,self.name)
        elif self.tag:
            return "{}:{}".format(self.name,self.tag)
        else:
            return self.name

    def __str__(self):
        return self.imageid

    class Meta:
        unique_together = [["account","name","tag"]]
        ordering = ['account','name','tag']
        verbose_name_plural = "{}{}".format(" " * 1,"Images")



class Workload(DeletedMixin,models.Model):
    ERROR = 4
    WARNING = 2
    INFO = 1

    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='workloads', editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='workloads', editable=False,null=True)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='workloads', editable=False, null=True)
    name = models.CharField(max_length=512, editable=False)
    kind = models.CharField(max_length=64, editable=False)

    # a array  of three elements array (container_id, running status(1:running,0 terminated) ,log level(0 no log,1 INFO, 2 WARNING 2,4 ERROR)
    latest_containers = ArrayField(ArrayField(models.IntegerField(),size=3), editable=False,null=True)

    replicas = models.PositiveSmallIntegerField(editable=False, null=True)
    containerimage = models.ForeignKey(ContainerImage, on_delete=models.PROTECT, related_name='workloadset', editable=False,null=True)
    image = models.CharField(max_length=128, editable=False)
    image_pullpolicy = models.CharField(max_length=64, editable=False, null=True)
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
        if self.namespace:
            return "{}.{}.{}".format(self.cluster.name, self.namespace.name, self.name)
        else:
            return "{}.NA.{}".format(self.cluster.name, self.name)

    class Meta:
        unique_together = [["cluster", "namespace", "name","kind"]]
        ordering = ["cluster__name", 'namespace', 'name']
        verbose_name_plural = "{}{}".format(" " * 5,"Workloads")


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
        verbose_name_plural = "{}{}".format(" " * 4,"Databases")


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

    status = models.CharField(max_length=32,null=True,editable=False)

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
        index_together = [["cluster","workload","pod_created"]]

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


class Harvester(models.Model):
    RUNNING = 1
    SUCCEED = 10
    SKIPPED = 11
    FAILED = -1
    ABORTED = -2
    STATUSES = [
        (RUNNING,"Running"),
        (FAILED,"Failed"),
        (SUCCEED,"Succeed"),
        (SKIPPED,"Skipped"),
        (ABORTED,"Aborted")
    ]
    name = models.CharField(max_length=64,editable=False,db_index=True)
    starttime = models.DateTimeField(auto_now=False,editable=False,null=False,db_index=True)
    last_heartbeat = models.DateTimeField(auto_now=False,editable=False,null=False,db_index=True)
    endtime = models.DateTimeField(auto_now=False,editable=False,null=True)
    status = models.SmallIntegerField(choices=STATUSES,db_index=True)
    message = models.TextField(editable=False,null=True)

    class Meta:
        index_together = [["name","starttime"],["name","status","starttime"],["status","starttime"]]
        ordering = ["name","starttime"]
        verbose_name_plural = "{}{}".format(" " * 0,"Harvesting jobs")

class WorkloadListener(object):
    @staticmethod
    def update_workloads(instance,update_fields,existing_obj):
        if existing_obj:
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
    def update_image_workloads(instance,update_fields,existing_obj):
        if not existing_obj or instance.containerimage != existing_obj.containerimage:
            #new workload or image changed
            if instance.containerimage:
                ContainerImage.objects.filter(pk=instance.containerimage.pk).update(workloads=models.F("workloads") + 1)

        if existing_obj and instance.containerimage != existing_obj.containerimage:
            if existing_obj.containerimage:
                ContainerImage.objects.filter(pk=existing_obj.containerimage.pk).update(workloads=models.F("workloads") - 1)

    @staticmethod
    @receiver(pre_save,sender=Workload)
    def pre_save(sender,instance,update_fields=None,**kwargs):
        existing_obj = None
        if instance.pk:
            existing_obj = Workload.objects.get(id=instance.id)

        WorkloadListener.update_workloads(instance,update_fields,existing_obj)
        WorkloadListener.update_image_workloads(instance,update_fields,existing_obj)

    @staticmethod
    def delete_workloads(instance):
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

    @staticmethod
    def delete_image_workloads(instance):
        if instance.containerimage:
            ContainerImage.objects.filter(pk=instance.containerimage.pk).update(workloads=models.F("workloads") - 1)

    @staticmethod
    @receiver(pre_delete,sender=Workload)
    def pre_delete(sender,instance,**kwargs):
        WorkloadListener.delete_workloads(instance)
        WorkloadListener.delete_image_workloads(instance)

class ContainerImageListener(object):
    @staticmethod
    def update_os_images(instance,update_fields,existing_obj):
        if not existing_obj or instance.os != existing_obj.os:
            #new workload or image changed
            if instance.os:
                OperatingSystem.objects.filter(pk=instance.os.pk).update(images=models.F("images") + 1)

        if existing_obj and instance.os != existing_obj.os:
            if existing_obj.os:
                OperatingSystem.objects.filter(pk=existing_obj.os.pk).update(images=models.F("images") - 1)


    @staticmethod
    @receiver(pre_save,sender=ContainerImage)
    def pre_save(sender,instance,update_fields=None,**kwargs):
        existing_obj = None
        if instance.pk:
            existing_obj = ContainerImage.objects.get(id=instance.id)

        ContainerImageListener.update_os_images(instance,update_fields,existing_obj)

    @staticmethod
    def delete_os_images(instance):
        if instance.os:
            OperatingSystem.objects.filter(pk=instance.os.pk).update(images=models.F("images") - 1)

    @staticmethod
    @receiver(pre_delete,sender=ContainerImage)
    def pre_delete(sender,instance,**kwargs):
        ContainerImageListener.delete_os_images(instance)

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


class VulnerabilitiesListener(object):
    @staticmethod
    @receiver(m2m_changed,sender=ContainerImage.vulnerabilities.through)
    def m2m_changed(sender,instance,action,reverse,model,pk_set,**kwargs):
        if action == "post_add":
            Vulnerability.objects.filter(pk__in=pk_set).update(affected_images=models.F("affected_images") + 1)
        elif action == "post_remove":
            Vulnerability.objects.filter(pk__in=pk_set).update(affected_images=models.F("affected_images") - 1)
        elif action == "pre_clear":
            instance.cleared_vulns = [o.pk for o in instance.vulnerabilities.all()]
        elif action == "post_clear":
            if instance.cleared_vulns:
                Vulnerability.objects.filter(pk__in=instance.cleared_vulns).update(affected_images=models.F("affected_images") - 1)


class OssListener(object):
    @staticmethod
    @receiver(m2m_changed,sender=Vulnerability.oss.through)
    def m2m_changed(sender,instance,action,reverse,model,pk_set,**kwargs):
        if action == "post_add":
            Vulnerability.objects.filter(pk=instance.pk).update(affected_oss=models.F("affected_oss") + len(pk_set))
            if instance.severity == instance.LOW:
                OperatingSystem.objects.filter(pk__in=pk_set).update(lows=models.F("lows") + 1)
            elif instance.severity == instance.MEDIUM:
                OperatingSystem.objects.filter(pk__in=pk_set).update(mediums=models.F("mediums") + 1)
            elif instance.severity == instance.HIGH:
                OperatingSystem.objects.filter(pk__in=pk_set).update(highs=models.F("highs") + 1)
            elif instance.severity == instance.CRITICAL:
                OperatingSystem.objects.filter(pk__in=pk_set).update(criticals=models.F("criticals") + 1)
            elif instance.severity == instance.UNKNOWN:
                OperatingSystem.objects.filter(pk__in=pk_set).update(unknowns=models.F("unknowns") + 1)
        elif action == "post_remove":
            Vulnerability.objects.filter(pk=instance.pk).update(affected_oss=models.F("affected_oss") - len(pk_set))
            if instance.severity == instance.LOW:
                OperatingSystem.objects.filter(pk__in=pk_set).update(lows=models.F("lows") - 1)
            elif instance.severity == instance.MEDIUM:
                OperatingSystem.objects.filter(pk__in=pk_set).update(mediums=models.F("mediums") - 1)
            elif instance.severity == instance.HIGH:
                OperatingSystem.objects.filter(pk__in=pk_set).update(highs=models.F("highs") - 1)
            elif instance.severity == instance.CRITICAL:
                OperatingSystem.objects.filter(pk__in=pk_set).update(criticals=models.F("criticals") - 1)
            elif instance.severity == instance.UNKNOWN:
                OperatingSystem.objects.filter(pk__in=pk_set).update(unknowns=models.F("unknowns") - 1)
        elif action == "pre_clear":
            instance.cleared_oss = [o.pk for o in instance.oss.all()]
        elif action == "post_clear":
            Vulnerability.objects.filter(pk=instance.pk).update(affected_oss=0)
            if instance.severity == instance.LOW:
                OperatingSystem.objects.filter(pk__in=instance.cleared_oss).update(lows=models.F("lows") - 1)
            elif instance.severity == instance.MEDIUM:
                OperatingSystem.objects.filter(pk__in=instance.cleared_oss).update(mediums=models.F("mediums") - 1)
            elif instance.severity == instance.HIGH:
                OperatingSystem.objects.filter(pk__in=instance.cleared_oss).update(highs=models.F("highs") - 1)
            elif instance.severity == instance.CRITICAL:
                OperatingSystem.objects.filter(pk__in=instance.cleared_oss).update(criticals=models.F("criticals") - 1)
            elif instance.severity == instance.UNKNOWN:
                OperatingSystem.objects.filter(pk__in=instance.cleared_oss).update(unknowns=models.F("unknowns") - 1)
