import subprocess
import sys
import imp
import json
import logging
import re
import itertools
import traceback

from django.db import models,transaction
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError,FieldDoesNotExist
from django.db.models.signals import pre_save,pre_delete,m2m_changed,post_save,post_delete
from django.dispatch import receiver

from registers.models import ITSystem
from . import utils
from .utils import set_field

logger = logging.getLogger(__name__)

class DbObjectMixin(object):
    """
    A mixin class to provide property "db_obj" which is the object with same id in database
    Return None if the object is a new instance.
    
    """
    _db_obj = None

    _editable_columns = []

    @property
    def db_obj(self):
        if not self.id:
            return None

        if not self._db_obj:
            self._db_obj = self.__class__.objects.get(id=self.id)
        return self._db_obj

    def save(self,update_fields=None,*args,**kwargs):
        if not self.changed_columns(update_fields):
            return

        logger.debug("Try to save the changed {}({})".format(self.__class__.__name__,self))
        with transaction.atomic():
            super().save(update_fields=update_fields,*args,**kwargs)

    def changed_columns(self,update_fields=None):
        if self.id is None:
            return self._editable_columns

        changed_columns = []
        for name in self._editable_columns:
            if update_fields and name not in update_fields:
                continue
            if getattr(self,name) != getattr(self.db_obj,name):
                changed_columns.append(name)

        return changed_columns


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
        verbose_name_plural = "{}{}".format(" " * 13,"Clusters")


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
        verbose_name_plural = "{}{}".format(" " * 12,"Projects")

class DeletedMixin(models.Model):
    deleted = models.DateTimeField(editable=False,null=True,db_index=True)

    has_updated_field = None

    @property
    def is_deleted(self):
        return True if self.deleted else False

    def logically_delete(self):
        if self.deleted:
            #already deleted
            return

        self.deleted = timezone.now()
        if self.__class__.has_updated_field is None:
            try:
                field = self._meta.get_field("updated")
                self.__class__.has_updated_field = True
            except FieldDoesNotExist as ex:
                self.__class__.has_updated_field = False
        if self.__class__.has_updated_field:
            self.save(update_fields=["deleted","updated"])
        else:
            self.save(update_fields=["deleted"])


    class Meta:
        abstract = True

class Namespace(DeletedMixin,models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='namespaces',editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='namespaces',editable=False,null=True)
    name = models.CharField(max_length=64,editable=False)
    system_namespace = models.BooleanField(editable=False,default=False)
    added_by_log = models.BooleanField(editable=False,default=False)
    active_workloads = models.PositiveIntegerField(editable=False,default=0)
    deleted_workloads = models.PositiveIntegerField(editable=False,default=0)
    api_version = models.CharField(max_length=64,editable=False,null=True)
    modified = models.DateTimeField(editable=False,null=True)
    updated = models.DateTimeField(auto_now=True)
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
        verbose_name_plural = "{}{}".format(" " * 11,"Namespaces")


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
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}:{}".format(self.cluster.name,self.name)

    class Meta:
        unique_together = [["cluster","name"],["cluster","volumepath"],["cluster","uuid"]]
        ordering = ["cluster__name",'name']
        verbose_name_plural = "{}{}".format(" " * 8,"Persistent volumes")

class Secret(DeletedMixin,models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='secrets',editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='secrets',editable=False,null=True)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='secrets',editable=False,null=True)
    name = models.CharField(max_length=128,editable=False)
    api_version = models.CharField(max_length=64,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}:{}".format(self.namespace,self.name)

    class Meta:
        unique_together = [["cluster","project","name"]]
        ordering = ["cluster__name","project",'name']
        verbose_name_plural = "{}{}".format(" " * 10,"Secrets")

class SecretItem(models.Model):
    secret = models.ForeignKey(Secret, on_delete=models.CASCADE, related_name='items',editable=False)
    name = models.CharField(max_length=128,editable=False)
    value = models.TextField(max_length=1024,editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}.{}".format(self.secret,self.name)

    class Meta:
        unique_together = [["secret","name"]]
        ordering = ["secret",'name']

class ConfigMap(DeletedMixin,models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='configmaps',editable=False)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='configmaps',editable=False)
    name = models.CharField(max_length=128,editable=False)
    api_version = models.CharField(max_length=64,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}:{}".format(self.namespace,self.name)

    class Meta:
        unique_together = [["cluster","namespace","name"]]
        ordering = ["cluster__name","namespace__name",'name']
        verbose_name_plural = "{}{}".format(" " * 9,"Config maps")

class ConfigMapItem(models.Model):
    configmap = models.ForeignKey(ConfigMap, on_delete=models.CASCADE, related_name='items',editable=False)
    name = models.CharField(max_length=128,editable=False)
    value = models.TextField(max_length=1024,editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(auto_now=True)

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
    updated = models.DateTimeField(auto_now=True)

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
    updated = models.DateTimeField(auto_now=True)

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
    updated = models.DateTimeField(auto_now=True)

    @property
    def is_deleted(self):
        return self.ingress.is_deleted

    @property
    def deleted(self):
        return self.ingress.deleted

    @property
    def listen(self):
        if (self.protocol == 'http' and self.port == 80) or (self.protocol == 'https' and self.port == 443):
            if self.path:
                return "{}://{}/{}".format(self.protocol,self.hostname,self.path)
            else:
                return "{}://{}".format(self.protocol,self.hostname)
        else:
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
        verbose_name_plural = "{}{}".format(" " * 6,"OperatingSystems")

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
        verbose_name_plural = "{}{}".format(" " * 5,"Vulnerabilities")

class ContainerImageFamily(DeletedMixin,models.Model):
    account = models.CharField(max_length=64,null=True,db_index=True,editable=False)
    name = models.CharField(max_length=128, editable=False)
    config = JSONField(null=False,default=dict)
    added = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def scan_resource(self,rescan=True,scan_modules=None):
        """
        Return workloads which resource has been changed ;otherwise return []
        """
        logger.debug("Scan resources for image family '{}'.".format(self))
        if not scan_modules: 
            scan_modules = list(EnvScanModule.objects.filter(active=True).order_by("-priority"))

        resource_changed_wls = []
        for workload in Workload.objects.filter(containerimage__imagefamily=self):
            if workload.scan_resource(rescan=rescan,scan_modules=scan_modules):
                resource_changed_wls.append(workload)

        return resource_changed_wls

    def __str__(self):
        if self.account:
            return "{}/{}".format(self.account,self.name)  
        else:
            return self.name

    class Meta:
        unique_together = [["account","name"]]
        ordering = ['account','name']
        verbose_name_plural = "{}{}".format(" " * 4,"Image Families")


class EnvScanModule(DbObjectMixin,models.Model):
    FILESYSTEM = 1
    BLOBSTORAGE = 2
    RESTAPI = 3
    EMAILSERVER = 4

    MEMORYCACHES = 10
    MEMCACHED = 11
    REDIS = 12

    DATABASES = 20
    POSTGRES = 21
    ORACLE = 22
    MYSQL = 23

    CREDENTIAL = 30
    DB_CREDENTIAL = 31
    APP_CREDENTIAL = 32
    AZURE_CREDENTIAL = 33
    BLOB_CREDENTIAL =34

    SERVICES = 999
    
    RESOURCE_TYPES = (
        (POSTGRES,"Postgres"),
        (ORACLE,"Oracle"),
        (MYSQL,"MySQL"),
        (FILESYSTEM,"File System"),
        (BLOBSTORAGE,"Blob Storage"),
        (RESTAPI,"REST Api"),
        (EMAILSERVER,"Email Server"),
        (MEMCACHED,"Memcached"),
        (REDIS,"Redis"),

        (CREDENTIAL,"Credential",),
        (DB_CREDENTIAL,"Database Credential"),
        (APP_CREDENTIAL,"App Credential"),
        (AZURE_CREDENTIAL,"Azure Credential"),
        (BLOB_CREDENTIAL,"Blob Credential")
    )

    MODULE_RESOURCE_TYPES = (
        (DATABASES,"Databases"),
        (POSTGRES,"Postgres"),
        (ORACLE,"Oracle"),
        (MYSQL,"MySQL"),
        (FILESYSTEM,"File System"),
        (BLOBSTORAGE,"Blob Storage"),
        (RESTAPI,"REST Api"),
        (EMAILSERVER,"Email Server"),
        (MEMCACHED,"Memcached"),
        (REDIS,"Redis"),

        (CREDENTIAL,"Credential",),
        (DB_CREDENTIAL,"Database Credential"),
        (APP_CREDENTIAL,"App Credential"),
        (AZURE_CREDENTIAL,"Azure Credential"),
        (BLOB_CREDENTIAL,"Blob Credential"),

        (SERVICES,"Services")
    )

    _pattern_re = None
    _scan_func = None
    _scan_module = None
    _module_id = 1

    _editable_columns = ["resource_type","priority","multi","sourcecode","active"]

    resource_type = models.PositiveSmallIntegerField(choices=MODULE_RESOURCE_TYPES)
    priority = models.PositiveSmallIntegerField(default=0)
    multi = models.BooleanField(default=False,help_text="Apply to single env variable if False; otherwise apply to all env variables")
    sourcecode = models.TextField(help_text="""The source code of a python module.
    This module must declare a method 'scan' with the following requirements.
    Parameters:
        1. multi is False, module must contain a function 'scan(env_name,env_value)'
        2. multi is True, module must contain a function 'scan(envs)' envs is a list of tuple(env_name,env_value)
    Return:
        If succeed
            1. if multi is False, return a dictionary with key 'resource_type'
            2. if multi is True, return a list of dictionary with keys 'resource_type' and 'env_items'
        If failed, return None
""")
    active = models.BooleanField(default=True)
    modified = models.DateTimeField(auto_now=True)
    added = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        #validate scan_func
        scan_function = self.scan_function

    def scan(self,*args):

        try:
            return self.scan_function(*args)
        except :
            logger.error("Failed to execute the scan module({})".format(self))
            raise

    @property
    def scan_function(self):
        if not self.sourcecode:
            return None
        if not self._scan_module:
            try:
                if self.pk:
                    module_name = "envscan_{}".format(self.pk)
                else:
                    self.__class__._module_id += 1
                    module_name = "envscan__{}".format(self.__class__._module_id)
                scan_module = imp.new_module(module_name)
                exec(self.sourcecode,scan_module.__dict__)
                self._scan_module = scan_module
            except Exception as ex:
                raise ValidationError("Scan module is invalid.{}".format(str(ex)))

        return self._scan_module.scan

    class Meta:
        ordering = ['-priority']
        verbose_name_plural = "{}{}".format(" " * 14,"Env Scan Modules")

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
    tag = models.CharField(max_length=64, editable=False,null=True)
    imagefamily = models.ForeignKey(ContainerImageFamily, on_delete=models.PROTECT, related_name='containerimages', editable=False,null=False)
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
    resource_scaned = models.DateTimeField(null=True)


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


        imagefamily,created = ContainerImageFamily.objects.get_or_create(account=account,name=image_name)

        image,created = ContainerImage.objects.update_or_create(imagefamily=imagefamily,tag=image_tag)
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
        if self.tag:
            return "{}:{}".format(str(self.imagefamily),self.tag)
        else:
            return str(self.imagefamily)

    def __str__(self):
        return self.imageid

    class Meta:
        unique_together = [["imagefamily","tag"]]
        ordering = ['imagefamily__account','imagefamily__name','tag']
        verbose_name_plural = "{}{}".format(" " * 3,"Images")



class Workload(DeletedMixin,models.Model):
    toggle_tree_js = False

    ERROR = 4
    WARNING = 2
    INFO = 1

    DEPLOYMENT = "Deployment"

    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='workloads', editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='workloads', editable=False,null=True)
    namespace = models.ForeignKey(Namespace, on_delete=models.PROTECT, related_name='workloads', editable=False, null=True)
    name = models.CharField(max_length=512, editable=False)
    kind = models.CharField(max_length=64, editable=False)

    itsystem = models.ForeignKey(ITSystem, on_delete=models.SET_NULL, related_name='workloads', editable=False,null=True)

    # a array  of three elements array (container_id, running status(1:running,0 terminated) ,log level(0 no log,1 INFO, 2 WARNING 2,4 ERROR)
    latest_containers = ArrayField(ArrayField(models.IntegerField(),size=3), editable=False,null=True)

    replicas = models.PositiveSmallIntegerField(editable=False, null=True)
    containerimage = models.ForeignKey(ContainerImage, on_delete=models.PROTECT, related_name='workloadset', editable=False,null=False)
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

    resource_scaned = models.DateTimeField(editable=False,null=True,db_index=True)
    resource_changed = models.DateTimeField(editable=False,null=True)
    dependency_scaned = models.DateTimeField(editable=False,null=True)
    dependency_changed = models.DateTimeField(editable=False,null=True)
    dependency_scan_requested = models.DateTimeField(editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(auto_now=True)

    def scan_resource(self,rescan=False,scan_modules=None,scan_time=timezone.now()):
        """
        Scan  the resource if required
        Return True if resource changed; otherwise return False
        """
        logger.debug("Scan resources for workload '{}'.".format(self))
        if not rescan and self.resource_scaned and self.resource_scaned >= self.updated and self.resource_scaned >= self.containerimage.imagefamily.modified:
            if scan_modules:
                if all(self.resource_scaned >= m.modified for m in scan_modules):
                    logger.debug("The resources for workload '{}' was already scaned,ignore!".format(self))
                    if not self.resource_changed:
                        self.resource_changed = self.resource_scaned
                        self.save(update_fields=["resource_changed"])
                    return False
            else:
                scan_module = EnvScanModule.objects.filter(active=True).order_by("-modified").first()
                if self.resource_scaned and self.resource_scaned >= scan_module.modified:
                    logger.debug("The resources for workload '{}' was already scaned,ignore.".format(self))
                    if not self.resource_changed:
                        self.resource_changed = self.resource_scaned
                        self.save(update_fields=["resource_changed"])
                    return False

        if not scan_modules: 
            scan_modules = list(EnvScanModule.objects.filter(active=True).order_by("-priority"))

        #get the default value from configuration
        envitems = {}
        imagefamily = self.containerimage.imagefamily
        if imagefamily.config and imagefamily.config.get("default_values"):
            for k,v in imagefamily.config.get("default_values").items():
                if imagefamily.config.get("ignored_envitems") and k in imagefamily.config.get("ignored_envitems"):
                    continue
                envitems[k] = v

        #load all env items of this workload
        qs = WorkloadEnv.objects.filter(workload=self)
        for envitem in qs:
            if imagefamily.config.get("ignored_envitems") and envitem.name in imagefamily.config.get("ignored_envitems"):
                continue
            envitems[envitem.name] = envitem.value

        resource_changed = False
        res_ids = set()

        def _update_or_create(resource_type,config_items,resource_id,config_source,properties):
            resobj,created = WorkloadResource.objects.get_or_create(workload=self,resource_type=resource_type,config_items=config_items,resource_id=resource_id,defaults={
                "imagefamily":self.containerimage.imagefamily,
                "config_source":config_source,
                "properties":properties
            })
            res_ids.add(resobj.id)
            if created:
                return True

            update_fields = []
            set_field(resobj,"imagefamily",self.containerimage.imagefamily,update_fields)
            set_field(resobj,"config_source",config_source,update_fields)
            set_field(resobj,"properties",properties,update_fields)
            if update_fields:
                update_fields.append("updated")
                resobj.save(update_fields=update_fields)
                return True
            else:
                return False

        #scan the predeclared resource items.
        if imagefamily.config.get("resources"):
            for res in imagefamily.config.get("resources"):
                if isinstance(res["config_items"],(list,tuple)):
                    config_items = res["config_items"]
                else:
                    config_items = [res["config_items"]]

                if not all(item in envitems for item in config_items):
                    #some env item is not declared 
                    continue
                config_values = [envitems[item] for item in config_items]

                resource_id = (res.get("resource_id") or ",".join("{}" for item in config_items)).format(*config_values)
                if res.get("config_source"):
                    config_source = getattr(WorkloadResource,res.get("config_source").upper())
                else:
                    config_source = WorkloadResource.ENV

                resource_type = getattr(EnvScanModule,res.get("resource_type").upper())
                properties = {}
                for key,value in (res.get("properties") or {}):
                    properties[key] = value.format(*config_values)
                resource_changed = _update_or_create(resource_type,config_items,resource_id,config_source,properties) or resource_changed

            #remove declared env items from envitems
            for res in imagefamily.config.get("resources"):
                if isinstance(res["config_items"],(list,tuple)):
                    config_items = res["config_items"]
                else:
                    config_items = [res["config_items"]]
                for item in config_items:
                    if item in envitems:
                        del envitems[item]

        processed_envs = set()
        resource_configs = imagefamily.config.get("resource_configs",{})

        for name,value in envitems.items():
            for m in scan_modules:
                if m.multi:
                    continue
                scan_result = m.scan(name,value,resource_configs.get(name))
                if not scan_result:
                    continue


                if isinstance(scan_result,(list,tuple)):
                    for result in scan_result:
                        resource_changed = _update_or_create(result["resource_type"],[name],result["resource_id"],result.get("config_source",WorkloadResource.ENV),result.get("properties") or {}) or resource_changed
                else:
                    resource_changed = _update_or_create(scan_result["resource_type"],[name],scan_result["resource_id"],scan_result.get("config_source",WorkloadResource.ENV),scan_result.get("properties") or {}) or resource_changed

                processed_envs.add(name)
        #remove processed env items from envitems
        for name in processed_envs:
            del envitems[name]
        processed_envs.clear()

        #scan all env items using scan modules with multi is True
        for m in scan_modules:
            if not m.multi:
                continue
            scan_result = m.scan(self,envitems.items(),resource_configs )
            if not scan_result:
                continue

            for result in scan_result:
                resource_changed = _update_or_create(result["resource_type"],result["config_items"],result["resource_id"],result.get("config_source",WorkloadResource.ENV),result.get("properties") or {}) or resource_changed
                for item in result["config_items"]:
                    processed_envs.add(item)

        #remove processed env items from envitems
        for name in processed_envs:
            del envitems[name]
        processed_envs.clear()

        del_objs = WorkloadResource.objects.filter(workload=self).exclude(id__in=res_ids).delete()
        if del_objs[0]:
            resource_changed = True

        self.resource_scaned = scan_time
        if resource_changed or not self.resource_changed:
            self.resource_changed = self.resource_scaned
            self.save(update_fields=["resource_scaned","resource_changed"])
            return True
        else:
            self.save(update_fields=["resource_scaned"])
            return False

    def scan_dependency(self,rescan=False,scan_time=timezone.now(),f_renew_lock=None):
        """
        Scan workload's dependency, and also scan the related workload's dependency
        Return True if scaned otherwise return False
        """
        tasks=set()
        tasks.add(self)
        processed_ids = set()
        def _update_or_create(workload,dependency_type,dependency_pk,dependency_id,dependency_display,dependent_workloads,del_dependent_workloads,update_by_request):
            with transaction.atomic():
                if dependent_workloads:
                    dependent_workloads.sort()
                elif dependent_workloads is None:
                    dependent_workloads = []
    
                if del_dependent_workloads:
                    del_dependent_workloads.sort()
                elif del_dependent_workloads is None:
                    del_dependent_workloads = []
    
                dependency_id = str(dependency_id)
                dependency_display = str(dependency_display)
    
                dependency,created = WorkloadDependency.objects.get_or_create(
                    workload=workload,
                    dependency_type=dependency_type,
                    dependency_pk=dependency_pk,
                    defaults = {
                        "imagefamily":workload.containerimage.imagefamily,
                        "dependency_id":dependency_id,
                        "dependency_display":dependency_display,
                        "dependent_workloads" : dependent_workloads,
                        "del_dependent_workloads" : del_dependent_workloads
                    }
                )
                if created:
                    #trigger related workloads to rescan dependency
                    if not update_by_request:
                        affected_workloads = set()
                        for i in dependent_workloads:
                            affected_workloads.add(i)
                        for i in del_dependent_workloads:
                            affected_workloads.add(i)
                        for obj in Workload.objects.filter(id__in=affected_workloads,dependency_scaned__lt=workload.resource_changed):
                            obj.dependency_scan_requested = workload.resource_changed
                            obj.save(update_fields=["dependency_scan_requested"])
                            if obj.id not in processed_ids:
                                tasks.add(obj)
                    return (dependency,True)
    
                update_fields = []
                previous_workloads = dependency.dependent_workloads
                previous_del_workloads = dependency.del_dependent_workloads
                set_field(dependency,"imagefamily",workload.containerimage.imagefamily,update_fields)
                set_field(dependency,"dependency_id",dependency_id,update_fields)
                set_field(dependency,"dependency_display",dependency_display,update_fields)
                set_field(dependency,"dependent_workloads",dependent_workloads,update_fields)
                set_field(dependency,"del_dependent_workloads",del_dependent_workloads,update_fields)
                if update_fields:
                    update_fields.append("updated")
                    dependency.save(update_fields=update_fields)
                    #trigger related workloads to rescan dependency
                    if not update_by_request:
                        affected_workloads = set()
                        for i in previous_workloads:
                            affected_workloads.add(i)
                        for i in previous_del_workloads:
                            affected_workloads.add(i)
                        for i in dependent_workloads:
                            affected_workloads.add(i)
                        for i in del_dependent_workloads:
                            affected_workloads.add(i)
                        for obj in Workload.objects.filter(id__in=affected_workloads,dependency_scaned__lt=workload.resource_changed):
                            obj.dependency_scan_requested = workload.resource_changed
                            obj.save(update_fields=["dependency_scan_requested"])
                            if obj.id not in processed_ids:
                                tasks.add(obj)
                    return (dependency,True)
                else:
                    return (dependency,False)

        def _scan(workload):
            logger.debug("Scan dependency for workload '{}'.".format(workload))
            if not workload.resource_changed:
                return False
    
            if workload.dependency_scaned and (workload.dependency_scaned >= scan_time or (not rescan and workload.dependency_scaned >= workload.resource_changed and (not workload.dependency_scan_requested or workload.dependency_scan_requested < workload.dependency_scaned))):
                #already scaned, no need to scan again
                update_fields = []
                if workload.dependency_scan_requested :
                    workload.dependency_scan_requested = None
                    update_fields.append("dependency_scan_requested")
                if not workload.dependency_changed:
                    workload.dependency_changed = workload.dependency_scaned
                    update_fields.append("dependency_changed")
                if update_fields:
                    workload.save(update_fields=update_fields)
                return False
    
            if workload.dependency_scaned and workload.dependency_scaned >= workload.resource_changed and (workload.dependency_scan_requested and workload.dependency_scan_requested > workload.dependency_scaned):
                update_by_request = True
            else:
                update_by_request = False
    
            #find all dependencies through imagefamily
            dependency_ids = set()
            dependency_changed = False
            del_workload_ids = []
            workload_ids = []
            for w in Workload.objects.filter(containerimage__imagefamily=workload.containerimage.imagefamily).exclude(id=workload.id).only("id","deleted"):
                if w.deleted:
                    del_workload_ids.append(w.id)
                else:
                    workload_ids.append(w.id)

            dependency,dep_changed =_update_or_create(
                workload,
                WorkloadDependency.IMAGEFAMILY,
                workload.containerimage.imagefamily.id,
                workload.containerimage.imagefamily,
                workload.containerimage.imagefamily,
                workload_ids,
                del_workload_ids,
                update_by_request
            )
            dependency_ids.add(dependency.id)
            dependency_changed = dependency_changed or dep_changed
    
            #find all resource dependencies
            dependency = None
            for resource in WorkloadResource.objects.filter(workload=workload).order_by("resource_type","resource_id"):
                if dependency and dependency.dependency_type == resource.resource_type and dependency.dependency_id == resource.resource_id:
                    #already processed
                    continue
                workload_ids.clear()
                del_workload_ids.clear()
                if resource.resource_type == EnvScanModule.FILESYSTEM:
                    for dep_resource in WorkloadResource.objects.filter(resource_type=resource.resource_type,resource_id__startswith=resource.properties["root_path"]).exclude(workload=workload):
                        if dep_resource.resource_id.startswith(resource.resource_id) or resource.resource_id.startswith(dep_resource.resource_id):
                            if dep_resource.workload.deleted:
                                if dep_resource.workload.id not in del_workload_ids:
                                    del_workload_ids.append(dep_resource.workload.id)
                            else:
                                if dep_resource.workload.id not in workload_ids:
                                    workload_ids.append(dep_resource.workload.id)
                elif (
                    (resource.resource_type in [EnvScanModule.REDIS] ) or
                    (resource.resource_type > EnvScanModule.DATABASES and resource.resource_type < (EnvScanModule.DATABASES + 10))
                ):
                    if resource.config_source == WorkloadResource.SERVICE:
                        if "." in resource.resource_id:
                            #resource_id contains workspace name
                            qs = WorkloadResource.objects.filter(resource_type=resource.resource_type,resource_id__startswith=resource.resource_id).exclude(config_source = WorkloadResource.SERVICE)
                        else:
                            #resource_id does not contain workspace name, must in the same workspace
                            qs = WorkloadResource.objects.filter(
                                workload__namespace=resource.workload.namespace,
                                resource_type=resource.resource_type,
                                resource_id__startswith=resource.resource_id
                            ).exclude(config_source = WorkloadResource.SERVICE)
    
                        for dep_resource in qs:
                            if dep_resource.workload.deleted:
                                if dep_resource.workload.id not in del_workload_ids:
                                    del_workload_ids.append(dep_resource.workload.id)
                            else:
                                if dep_resource.workload.id not in workload_ids:
                                    workload_ids.append(dep_resource.workload.id)
    
    
                    else:
                        resource_id,db_name = resource.resource_id.rsplit("/",1)
                        resource_id = "{}/".format(resource_id)
                        if "." in resource.resource_id:
                            #resource_id contains workspace name
                            qs = WorkloadResource.objects.filter(config_source = WorkloadResource.SERVICE,resource_type=resource.resource_type,resource_id=resource_id).exclude(workload=workload)
                        else:
                            #resource_id does not contain workspace name, must in the same workspace
                            qs = WorkloadResource.objects.filter(
                                workload__namespace=resource.workload.namespace,
                                config_source = WorkloadResource.SERVICE,
                                resource_type=resource.resource_type,resource_id=resource_id
                            ).exclude(workload=workload)
                        is_local_db = False
                        #assume the database is local database
                        for dep_resource in qs:
                            is_local_db = True
                            if dep_resource.workload.deleted:
                                if dep_resource.workload.id not in del_workload_ids:
                                    del_workload_ids.append(dep_resource.workload.id)
                            else:
                                if dep_resource.workload.id not in workload_ids:
                                    workload_ids.append(dep_resource.workload.id)
                            if "." in dep_resource.resource_id:
                                qs2 = WorkloadResource.objects.filter(
                                    resource_type=dep_resource.resource_type,
                                    resource_id="{}{}".format(dep_resource.resource_id,db_name)
                                ).exclude(config_source=WorkloadResource.SERVICE).exclude(workload=self)
                            else:
                                qs2 = WorkloadResource.objects.filter(
                                    workload__namespace=dep_resource.workload.namespace,
                                    resource_type=dep_resource.resource_type,
                                    resource_id="{}{}".format(dep_resource.resource_id,db_name)
                                ).exclude(config_source=WorkloadResource.SERVICE).exclude(workload=self)

                            for dep_res2 in qs2:
                                if dep_res2.workload.deleted:
                                    if dep_res2.workload.id not in del_workload_ids:
                                        del_workload_ids.append(dep_res2.workload.id)
                                else:
                                    if dep_res2.workload.id not in workload_ids:
                                        workload_ids.append(dep_res2.workload.id)
                        if not is_local_db:
                            #it is a shared database.
                            for dep_resource in WorkloadResource.objects.filter(resource_type=resource.resource_type,resource_id=resource.resource_id).exclude(workload=workload):
                                if dep_resource.workload.deleted:
                                    if dep_resource.workload.id not in del_workload_ids:
                                        del_workload_ids.append(dep_resource.workload.id)
                                else:
                                    if dep_resource.workload.id not in workload_ids:
                                        workload_ids.append(dep_resource.workload.id)
                else:
                    for dep_resource in WorkloadResource.objects.filter(resource_type=resource.resource_type,resource_id=resource.resource_id).exclude(workload=workload):
                        if dep_resource.workload.deleted:
                            if dep_resource.workload.id not in del_workload_ids:
                                del_workload_ids.append(dep_resource.workload.id)
                        else:
                            if dep_resource.workload.id not in workload_ids:
                                workload_ids.append(dep_resource.workload.id)
    
    
                dependency,dep_changed = _update_or_create(
                    workload,
                    resource.resource_type,
                    resource.id,
                    resource.resource_id,
                    "{1}({0})".format(resource.resource_id,(resource.properties or {}).get("name")) if resource.resource_type == EnvScanModule.FILESYSTEM else resource.resource_id,
                    workload_ids,
                    del_workload_ids,
                    update_by_request
                )
                dependency_ids.add(dependency.id)
                dependency_changed = dependency_changed or dep_changed

    
            #delete the removed dependencies
            for obj in WorkloadDependency.objects.filter(workload=workload).exclude(id__in=dependency_ids):
                with transaction.atomic():
                    obj.delete()
                    affected_workloads = set()
                    for i in obj.dependent_workloads:
                        affected_workloads.add(i)
                    for i in obj.del_dependent_workloads:
                        affected_workloads.add(i)
                    for obj in Workload.objects.filter(id__in=affected_workloads,dependency_scaned__lt=workload.resource_changed):
                        obj.dependency_scan_requested = workload.resource_changed
                        obj.save(update_fields=["dependency_scan_requested"])
                        if obj.id not in processed_ids:
                            tasks.add(obj)
                dependency_changed = True
    
            workload.dependency_scaned = scan_time
            workload.dependency_scan_requested = None
            if dependency_changed or not workload.dependency_changed:
                workload.dependency_changed = workload.dependency_scaned
                workload.save(update_fields=["dependency_scaned","dependency_scan_requested","dependency_changed"])
                return True
            else:
                workload.save(update_fields=["dependency_scaned","dependency_scan_requested"])
                return False

        changed = False
        while tasks:
            workload = tasks.pop()
            processed_ids.add(workload.id)
            if workload == self:
                changed = _scan(workload) or changed
            else:
                _scan(workload)

            if f_renew_lock:
                f_renew_lock()

        return changed




    def populate_workload_dependent_tree(self,depth=None,workload_cache={},dependency_cache={},tree=None,populate_time=timezone.now()):
        """
        Tree data structure
        [workload's id, workload's name,active?,[
            ([(dependent type,dependent type name,dependent_pk,dependent_display),...],sub workload dependent tree),
            ...
        ]
        """
        tree = tree or WorkloadDependentTree.objects.filter(workload=self).defer("restree","restree_wls","restree_created","restree_updated","wltree").first()
        if not tree:
            tree = WorkloadDependentTree(workload=self,imagefamily=self.containerimage.imagefamily)

        dep_tree = [self.id,str(self),False if self.deleted else True,None]
        resolved_workloads = set()
        new_resolved_workloads = set()
        workloadids = set()

        tasks = [(self,[],dep_tree)]

        def _run(task):
            workload = task[0]
            tree_path = task[1]
            dep_tree = task[2]
            workloadids.add(workload.id)
            if depth and len(tree_path) >= depth:
                dep_tree[3] = []
                return

            tree_path = list(tree_path)

            dep_datas = dependency_cache.get(workload.id)
            if not dep_datas:
                dep_datas = list(WorkloadDependency.objects.filter(workload=workload).order_by("dependency_type","dependency_id"))
                dependency_cache[workload.id] = dep_datas

            tree_path.append((workload.id,workload.containerimage.imagefamily.id))

            workload_dep_trees = {}
            for dep in dep_datas:
                if dep.dependency_type == WorkloadDependency.IMAGEFAMILY and workload.containerimage.imagefamily != self.containerimage.imagefamily:
                    continue

                for dep_workload_id in itertools.chain(dep.dependent_workloads,dep.del_dependent_workloads):
                    if (workload.id,dep_workload_id) in resolved_workloads:
                        continue

                    new_resolved_workloads.add((workload.id,dep_workload_id))
                    new_resolved_workloads.add((dep_workload_id,workload.id))

                    dep_workload = workload_cache.get(dep_workload_id)
                    if not dep_workload:
                        dep_workload = Workload.objects.get(id=dep_workload_id)
                        workload_cache[dep_workload_id] = dep_workload

                    if dep_workload_id not in workload_dep_trees:
                        sub_dep_tree = [dep_workload_id,str(dep_workload),False if dep_workload.deleted else True,None]
                        workload_dep_trees[dep_workload_id] = (
                            [(dep.dependency_type,dep.get_dependency_type_display(),dep.dependency_pk,dep.dependency_display)],
                            sub_dep_tree
                        )
                        tasks.append((dep_workload,tree_path,sub_dep_tree))
                    else:
                        workload_dep_trees[dep_workload_id][0].append((dep.dependency_type,dep.get_dependency_type_display(),dep.dependency_pk,dep.dependency_display))

            dep_tree[3] = list(workload_dep_trees.values())
            dep_tree[3].sort(key=lambda o:"{1}-{0}".format(o[1][1],0 if o[1][2] else 1))
        tree_path_len = 0
        while tasks:
            task = tasks.pop(0)
            if len(task[1]) != tree_path_len:
                if new_resolved_workloads:
                    for o in new_resolved_workloads:
                        resolved_workloads.add(o)
                    new_resolved_workloads.clear()
                tree_path_len = len(task[1])

            _run(task)

        
        tree.wltree = dep_tree
        tree.wltree_wls = list(workloadids)
        tree.wltree_wls.sort()
        tree.wltree_created = tree.wltree_created or populate_time
        tree.wltree_updated = populate_time
        tree.wltree_update_requested = None
        if tree.pk:
            tree.save(update_fields=["wltree","wltree_wls","wltree_created","wltree_updated","wltree_update_requested"])
        else:
            tree.save()

        return tree
            
    def populate_resource_dependent_tree(self,depth=None,workload_cache={},dependency_cache={},tree=None,populate_time=timezone.now()):
        """
        Tree data structure
        [workload's id, workload's name,active?,[
            [dependent type,dependent type name,[
                [dependent_pk,dependent_id, [
                    [sub dependent tree]
                    ... #more dependent tree of workloads which are dpendent on the same resource
                ]]

                ... #more dependent tree of workloads which are dependent on the same resource type
            ]] 
            ... #more dependent tree of workloads which are dependent on the different resource type
        ]]
        """
        tree = tree or WorkloadDependentTree.objects.filter(workload=self).defer("wltree","wltree_wls","wltree_created","wltree_updated","restree").first()
        if not tree:
            tree = WorkloadDependentTree(workload=self,imagefamily=self.containerimage.imagefamily)

        dep_tree = [self.id,str(self),False if self.deleted else True,None]
        resolved_dependencies = set()
        new_resolved_dependencies = set()
        workloadids = set()

        tasks = [(self,[],dep_tree)]

        def _run(task):
            workload = task[0]
            tree_path = task[1]
            dep_tree = task[2]
            workloadids.add(workload.id)
            if depth and len(tree_path) >= depth:
                dep_tree[3] = []
                return

            tree_path = list(tree_path)

            dep_datas = dependency_cache.get(workload.id)
            if not dep_datas:
                dep_datas = list(WorkloadDependency.objects.filter(workload=workload).order_by("dependency_type","dependency_id"))
                dependency_cache[workload.id] = dep_datas

            tree_path.append((workload.id,workload.containerimage.imagefamily.id))

            dependencies = []
            dep_tree[3] = dependencies
            workload_dep_trees = {}
            sub_dep_trees = None
            for dep in dep_datas:
                if dep.dependency_type == WorkloadDependency.IMAGEFAMILY and workload.containerimage.imagefamily != self.containerimage.imagefamily:
                    continue

                if (dep.dependency_type,dep.dependency_id) in resolved_dependencies:
                    #already resolved
                    continue
                new_resolved_dependencies.add((dep.dependency_type,dep.dependency_id))

                if not dependencies or dependencies[-1][0] != dep.dependency_type:
                    if sub_dep_trees:
                        sub_dep_trees.sort(key=lambda o:"{1}-{0}".format(o[1],0 if o[2] else 1))
                    sub_dep_trees = []
                    dependencies.append((dep.dependency_type,dep.get_dependency_type_display(),[(dep.dependency_pk,dep.dependency_display,sub_dep_trees)]))
                    for dep_workload_id in itertools.chain(dep.dependent_workloads,dep.del_dependent_workloads):
                        dep_workload = workload_cache.get(dep_workload_id)
                        if not dep_workload:
                            dep_workload = Workload.objects.get(id=dep_workload_id)
                            workload_cache[dep_workload_id] = dep_workload

                        if dep.dependency_type == WorkloadDependency.IMAGEFAMILY:
                            dep_workload_name = "{}({})".format(str(dep_workload),dep_workload.containerimage.tag)
                        else:
                            dep_workload_name = str(dep_workload)

                        sub_dep_tree = [dep_workload_id,dep_workload_name,False if dep_workload.deleted else True,None]
                        tasks.append((dep_workload,tree_path,sub_dep_tree))
                        sub_dep_trees.append(sub_dep_tree)
                elif dependencies[-1][2][-1][0] != dep.dependency_pk:
                    if sub_dep_trees:
                        sub_dep_trees.sort(key=lambda o:"{1}-{0}".format(o[1],0 if o[2] else 1))
                    sub_dep_trees = []
                    dependencies[-1][2].append((dep.dependency_pk,dep.dependency_display,sub_dep_trees))
                    for dep_workload_id in itertools.chain(dep.dependent_workloads,dep.del_dependent_workloads):
                        dep_workload = workload_cache.get(dep_workload_id)
                        if not dep_workload:
                            dep_workload = Workload.objects.get(id=dep_workload_id)
                            workload_cache[dep_workload_id] = dep_workload

                        if dep.dependency_type == WorkloadDependency.IMAGEFAMILY:
                            dep_workload_name = "{}({})".format(str(dep_workload),dep_workload.containerimage.tag)
                        else:
                            dep_workload_name = str(dep_workload)

                        sub_dep_tree = [dep_workload_id,dep_workload_name,False if dep_workload.deleted else True,None]
                        tasks.append((dep_workload,tree_path,sub_dep_tree))
                        sub_dep_trees.append(sub_dep_tree)
                else:
                    sub_dep_trees = dependencies[-1][2][-1][2]
                    for dep_workload_id in itertools.chain(dep.dependent_workloads,dep.del_dependent_workloads):
                        if any(dep_workload_id == o[0] for o in sub_dep_trees):
                            #already included
                            continue

                        dep_workload = workload_cache.get(dep_workload_id)
                        if not dep_workload:
                            dep_workload = Workload.objects.get(id=dep_workload_id)
                            workload_cache[dep_workload_id] = dep_workload

                        if dep.dependency_type == WorkloadDependency.IMAGEFAMILY:
                            dep_workload_name = "{}({})".format(str(dep_workload),dep_workload.containerimage.tag)
                        else:
                            dep_workload_name = str(dep_workload)

                        sub_dep_tree = [dep_workload_id,dep_workload_name,False if dep_workload.deleted else True,None]
                        tasks.append((dep_workload,tree_path,sub_dep_tree))
                        sub_dep_trees.append(sub_dep_tree)

            if sub_dep_trees:
                sub_dep_trees.sort(key=lambda o:"{1}-{0}".format(o[1],0 if o[2] else 1))


        tree_path_len = 0
        while tasks:
            task = tasks.pop(0)
            if len(task[1]) != tree_path_len:
                if new_resolved_dependencies:
                    for o in new_resolved_dependencies:
                        resolved_dependencies.add(o)
                    new_resolved_dependencies.clear()
                tree_path_len = len(task[1])

            _run(task)

        tree.restree = dep_tree
        tree.restree_wls = list(workloadids)
        tree.restree_wls.sort()
        tree.restree_created = tree.restree_created or populate_time
        tree.restree_updated = populate_time
        tree.restree_update_requested = None
        if tree.pk:
            tree.save(update_fields=["restree","restree_wls","restree_created","restree_updated","restree_update_requested"])
        else:
            tree.save()
        return tree
            
            
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
        verbose_name_plural = "{}{}".format(" " * 7,"Workloads")

class WorkloadResource(models.Model):
    ENV = 1
    WORKLOADVOLUME = 2
    SERVICE = 4

    CONFIG_SOURCES = (
        (ENV,"Env"),
        (WORKLOADVOLUME,"Workload Volume"),
        (ENV | WORKLOADVOLUME,"Env & Workload Volume"),
        (SERVICE,"Service")
    )

    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='resources',editable=False)
    imagefamily = models.ForeignKey(ContainerImageFamily,on_delete=models.PROTECT,related_name="resources",editable=False)
    config_items = ArrayField(models.CharField(max_length=128,editable=False))
    resource_type = models.PositiveSmallIntegerField(choices=EnvScanModule.RESOURCE_TYPES,editable=False)
    resource_id = models.CharField(max_length=512,editable=False,db_index=True)
    config_source = models.PositiveSmallIntegerField(choices=CONFIG_SOURCES,editable=False)
    properties = JSONField(null=False,default=dict)
    scan_module = models.ForeignKey(EnvScanModule, on_delete=models.PROTECT, related_name='resources', editable=False,null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{0}.{1} is {2}:{3}".format(self.workload,self.config_items,self.get_resource_type_display(),self.resource_id)

    class Meta:
        unique_together = [["workload","resource_type","config_items","resource_id"]]
        ordering = ['imagefamily','workload','resource_type','config_items']
        verbose_name_plural = "{}{}".format(" " * 2,"Workload Resources")

class WorkloadDependency(models.Model):
    IMAGEFAMILY  = 999

    DEPENDENCY_TYPES = tuple(list(EnvScanModule.RESOURCE_TYPES) + [(IMAGEFAMILY,"Image Family")])

    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='dependencies',editable=False)
    imagefamily = models.ForeignKey(ContainerImageFamily,on_delete=models.PROTECT,related_name="dependencies",editable=False)
    dependency_type = models.PositiveSmallIntegerField(choices=DEPENDENCY_TYPES,editable=False)
    dependency_pk = models.IntegerField(editable=False)
    dependency_id = models.CharField(max_length=512,editable=False)
    dependency_display = models.CharField(max_length=512,editable=False)
    dependent_workloads = ArrayField(models.IntegerField(editable=False),db_index=True)
    del_dependent_workloads = ArrayField(models.IntegerField(editable=False),db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["workload","dependency_type","dependency_pk"]]
        ordering = ["workload","dependency_type","dependency_id"]
        verbose_name_plural = "{}{}".format(" " * 1,"Workload Dependencies")

class WorkloadDependentTree(models.Model):
    workload = models.OneToOneField(Workload, on_delete=models.CASCADE, related_name='dependenttree',editable=False)
    imagefamily = models.ForeignKey(ContainerImageFamily,on_delete=models.PROTECT,related_name="dependenttrees",editable=False)

    restree = JSONField(editable=False,null=True)
    restree_wls = ArrayField(models.IntegerField(null=False),editable=False,null=True)
    restree_created = models.DateTimeField(editable=False,null=True)
    restree_updated = models.DateTimeField(editable=False,null=True)
    restree_update_requested = models.DateTimeField(editable=False,null=True)

    wltree = JSONField(editable=False,null=True)
    wltree_wls = ArrayField(models.IntegerField(null=False),editable=False,null=True)
    wltree_created = models.DateTimeField(editable=False,null=True)
    wltree_updated = models.DateTimeField(editable=False,null=True)
    wltree_update_requested = models.DateTimeField(editable=False,null=True)

class WorkloadListening(models.Model):
    workload = models.ForeignKey(Workload, on_delete=models.CASCADE, related_name='listenings',editable=False)
    servicename = models.CharField(max_length=128,editable=False)
    container_port = models.PositiveIntegerField(editable=False)
    protocol = models.CharField(max_length=16,editable=False)

    ingress_rule = models.ForeignKey(IngressRule, on_delete=models.CASCADE, related_name='listenings',editable=False,null=True)
    listen_port = models.PositiveIntegerField(editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(auto_now=True)

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

    secret = models.ForeignKey(Secret, on_delete=models.CASCADE, related_name='workloadenvs',editable=False,null=True)
    secretitem = models.ForeignKey(SecretItem, on_delete=models.CASCADE, related_name='workloadenvs',editable=False,null=True)

    name = models.CharField(max_length=128,editable=False)
    value = models.TextField(editable=False,null=True)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(auto_now=True)

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
    other_config = JSONField(null=True)

    writable = models.BooleanField(default=False,editable=False)

    modified = models.DateTimeField(editable=False)
    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(auto_now=True)

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

        if instance.pk and (True if instance.deleted else False) != (True if existing_obj.deleted else False):
            affected_workloads = set()
            for o in WorkloadDependency.objects.filter(models.Q(dependent_workloads__contains=[instance.id]) | models.Q(del_dependent_workloads__contains=[instance.id])):
                affected_workloads.add(o.workload)
            WorkloadDependentTree.objects.filter(workload__in=affected_workloads).update(wltree_update_requested=timezone.now(),restree_update_requested=timezone.now())

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

        affected_workloads = set()
        for o in WorkloadDependency.objects.filter(models.Q(dependent_workloads__contains=[instance.id]) | models.Q(del_dependent_workloads__contains=[instance.id])):
            affected_workloads.add(o.workload)
        WorkloadDependentTree.objects.filter(workload__in=affected_workloads).update(wltree_update_requested=timezone.now(),restree_update_requested=timezone.now())

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
class ITSystemListener(object):
    @staticmethod
    @receiver(pre_save,sender=ITSystem)
    def request_update_workload_itsystem(sender,instance,update_fields=None,**kwargs):
        if instance.pk and (update_fields is None or "extra_data" in update_fields or "acronym" in update_fields):
            db_obj = ITSystem.objects.get(id=instance.id)
            db_extra_data = utils.parse_json(db_obj.extra_data)
            extra_data = utils.parse_json(instance.extra_data)
            if (db_obj.acronym == instance.acronym
                and db_extra_data.get("url_synonyms") == extra_data.get("url_synonyms") 
                and db_extra_data.get("synonyms") ==  extra_data.get("synonyms")
            ):
                return

        instance.update_workload_itsystem = True


    @staticmethod
    @receiver(post_save,sender=ITSystem)
    def update_workload_itsystem(sender,instance,update_fields=None,**kwargs):
        if not hasattr(instance,"update_workload_itsystem") :
            return
        elif not instance.update_workload_itsystem:
            delattr(instance,"update_workload_itsystem")
            return

        #clean the itsystem of workloads whose itsystem is current itsystem to trigger a rescan of the itsystem in the future.
        Workload.objects.filter(itsystem=instance).update(itsystem=None)
        """
        #update the deployment first
        itsystems = [instance]
        for workload in Workload.objects.filter(itsystem__isnull=True,kind=Workload.DEPLOYMENT):
            if not WorkloadListening.objects.filter(workload=workload,ingress_rule__isnull=False).exists():
                continue
            if workload.update_itsystem(itsystems=itsystems):
                #deployment changed, find the related workloads and update.
                qs = Workload.objects.filter(itsystem__isnull=True)
                if workload.containerimage.account:
                    qs = qs.filter(containerimage__account=workload.containerimage.account)
                else:
                    qs = qs.filter(containerimage__account__isnull=True)

                qs = qs.filter(containerimage__name=workload.containerimage.name)
                
                for o in qs:
                    o.update_itsystem(itsystems=itsystems)

        """
        delattr(instance,"update_workload_itsystem")

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
