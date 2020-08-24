import yaml
import itertools
import re
import logging
import json
from datetime import date,datetime,timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone
from django.db import transaction

from data_storage import ResourceConsumeClient, AzureBlobStorage,exceptions
from .models import (Cluster,Namespace,Project,
        PersistentVolume,PersistentVolumeClaim,
        Workload,WorkloadEnv,Ingress,IngressRule,WorkloadListening,WorkloadVolume,
        DatabaseServer,Database,DatabaseUser,WorkloadDatabase)
from data_storage.utils import get_property
from nginx.models import WebAppLocationServer

logger = logging.getLogger(__name__)

RANCHER_FILE_RE=re.compile("(^|/)(ingress-|cronjob-|deployment-|persistentvolumeclaim-|persistentvolume-|namespace-|statefulset-).+\.(yaml|yml)$")


VOLUMN_RE=re.compile("(^|/)persistentvolume-.+\.(yaml|yml)$")
VOLUMN_CLAIM_RE=re.compile("(^|/)persistentvolumeclaim.+\.(yaml|yml)$")
DEPLOYMENT_RE=re.compile("(^|/)deployment-.+\.(yaml|yml)$")
CRONJOB_RE=re.compile("(^|/)cronjob-.+\.(yaml|yml)$")
NAMESPACE_RE=re.compile("(^|/)namespace-.+\.(yaml|yml)$")
INGRESS_RE=re.compile("(^|/)ingress-.+\.(yaml|yml)$")
STATEFULSET_RE=re.compile("(^|/)statefulset-.+\.(yaml|yml)$")

class JSONEncoder(json.JSONEncoder):
    """
    A JSON encoder to support encode datetime
    """
    def default(self,obj):
        from data_storage.settings import TZ
        if isinstance(obj,datetime):
            return obj.astimezone(tz=TZ).strftime("%Y-%m-%d %H:%M:%S.%f")
        elif isinstance(obj,date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj,models.Model):
            return str(obj)

        return json.JSONEncoder.default(self,obj)

_consume_clients = {}
def get_consume_client(cluster):
    """
    Return the blob resource client
    """
    if cluster not in _consume_clients:
        _consume_clients[cluster] = ResourceConsumeClient(
            AzureBlobStorage(settings.RANCHER_STORAGE_CONNECTION_STRING,settings.RANCHER_CONTAINER),
            settings.RANCHER_RESOURCE_NAME,
            settings.RANCHER_RESOURCE_CLIENTID,
            resource_base_path="{}/{}".format(settings.RANCHER_RESOURCE_NAME,cluster)

        )
    return _consume_clients[cluster]

def set_fields(obj,config,fields):
    update_fields = None if obj.pk is None else []
    for field,prop,get_func in fields:
        val = get_property(config,prop,get_func)
        if obj.pk is None:
            setattr(obj,field,val)
        elif getattr(obj,field) != val:
            setattr(obj,field,val)
            update_fields.append(field)

    return update_fields


def set_field(obj,field,val,update_fields):
    if obj.pk is None:
        setattr(obj,field,val)
    elif getattr(obj,field) != val:
        setattr(obj,field,val)
        update_fields.append(field)


def update_namespace(cluster,status,metadata,config):
    namespace_id = get_property(config,("metadata","annotations","field.cattle.io/projectId"))

    name = config["metadata"]["name"]
    try:
        obj = Namespace.objects.get(cluster=cluster,name=name)
    except ObjectDoesNotExist as ex:
        obj = Namespace(cluster=cluster,name=name)

    update_fields = set_fields(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("project",("metadata","labels","field.cattle.io/projectId"),lambda val:Project.objects.get_or_create(cluster=cluster,projectid=val)[0]),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) )
    ])

    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        logger.debug("Create namespace({})".format(obj))
    elif update_fields:
        update_fields.append("refreshed")
        obj.save(update_fields=update_fields)
        logger.debug("Update namespace({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The namespace({}) is not changed".format(obj))


    #try to update the clusterid if it is empty or not match
    if namespace_id and ":" in namespace_id:
        cluster_id,project_id = namespace_id.split(':',1)
        if project_id == obj.project.projectid:
            if cluster.clusterid != cluster_id:
                cluster.clusterid = cluster_id
                cluster.save(update_fields=["clusterid"])

def delete_namespace(cluster,status,metadata,config):
    name = config["metadata"]["name"]
    
    del_rows = Namespace.objects.filter(cluster=cluster,name=name).update(deleted=timezone.now())
    if del_rows:
        logger.info("Logically delete namespace({}.{})".format(cluster,name))

    """
    del_objs = Namespace.objects.filter(cluster=cluster,name=name).delete()
    if del_objs[0]:
        logger.info("Delete namespace({}),deleted objects = {}".format(name,del_objs))
    """

def _get_ingress_protocol(val):
    if "http" in val:
        return "http"
    else:
        raise Exception("Failed to extract ingress protocol from {}".format(val))


def update_ingress_rules(ingress,configs):
    if not configs:
        del_objs = IngressRule.objects.filter(ingress=ingress).delete()
        if del_objs[0]:
            logger.debug("Delete the rules for Ingress({}),deleted objects = {}".format(ingress,del_objs))
        return

    name = None
    rule_ids = []
    for config in configs:
        hostname = config["host"]
        protocol = _get_ingress_protocol(config)
        for backend in get_property(config,(protocol,"paths")):
            path = backend.get("path","")
            try:
                obj = IngressRule.objects.get(ingress=ingress,protocol=protocol,hostname=hostname,path=path)
            except ObjectDoesNotExist as ex:
                obj = IngressRule(ingress=ingress,protocol=protocol,hostname=hostname,path=path,cluster=ingress.cluster)
            update_fields = set_fields(obj,backend,[
                ("servicename",("backend","serviceName"),lambda val: "{}:{}".format(ingress.namespace.name,val)),
                ("serviceport",("backend","servicePort"),lambda val:int(val))
            ])

            if obj.pk is None:
                obj.modified = ingress.modified
                obj.created = ingress.modified
                obj.save()
                rule_ids.append(obj.pk)
                logger.debug("Create deployment workload env({})".format(obj))
            elif update_fields:
                obj.modified = ingress.modified
                update_fields.append("modified")
                update_fields.append("refreshed")
                obj.save(update_fields=update_fields)
                rule_ids.append(obj.pk)
                logger.debug("Update the deployment workload env({}),update_fields={}".format(obj,update_fields))
            else:
                rule_ids.append(obj.pk)
                logger.debug("The deployment workload env({}) is not changed".format(obj))

    del_objs = IngressRule.objects.filter(ingress=ingress).exclude(pk__in=rule_ids).delete()
    if del_objs[0]:
        logger.debug("Delete the rules for Ingress({}),deleted objects = {}".format(ingress,del_objs))


def update_ingress(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.get(cluster=cluster,name=namespace)
    name = config["metadata"]["name"]
    try:
        obj = Ingress.objects.get(cluster=cluster,namespace=namespace,name=name)
    except ObjectDoesNotExist as ex:
        obj = Ingress(cluster=cluster,namespace=namespace,name=name,project=namespace.project)
    update_fields = set_fields(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
    ])

    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        logger.debug("Create Ingress({})".format(obj))
    elif update_fields:
        update_fields.append("refreshed")
        obj.save(update_fields=update_fields)
        logger.debug("Update Ingress({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The Ingress({}) is not changed".format(obj))

    #update rules
    update_ingress_rules(obj,get_property(config,("spec","rules")))

def delete_ingress(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.filter(cluster=cluster,name=namespace).first()
    if not namespace:
        return
    name = config["metadata"]["name"]
    del_rows = Ingress.objects.filter(cluster=cluster,namespace=namespace,name=name).update(deleted=timezone.now())
    if del_rows:
        logger.info("Logically delete Ingress({}.{})".format(namespace,name))
    """
    del_objs = Ingress.objects.filter(cluster=cluster,namespace=namespace,name=name).delete()
    if del_objs[0]:
        logger.info("Delete Ingress({}),deleted objects = {}".format(name,del_objs))
    """

def _get_volume_uuid(val):
    if val.startswith("pvc-"):
        return val[4:]
    else:
        return val

def _get_volume_capacity(val):
    """
    Return the capacith with unit 'M'
    """
    if val.lower().endswith("gi"):
        return int(val[:-2]) * 1024
    elif val.lower().endswith("mi"):
        return int(val[:-2]) * 1024
    else:
        raise Exception("Parse storage capacity({}) failed".format(val))

def _get_volume_storage_class_name(val):
    storage_class = get_property(val,("spec","storageClassName"))
    if not storage_class:
        if get_property(val,("spec","nfs")):
            storage_class = "nfs-client"
    
        if get_property(val,("spec","volumeMode")) == "Filesystem":
            storage_class = "local-path"

    return storage_class


def _get_volume_path(val):
    storage_class = _get_volume_storage_class_name(val)
    if storage_class == "local-path":
        return get_property(val,("spec","hostPath","path"))
    elif storage_class == "nfs-client":
        return "{}:{}".format(get_property(val,("spec","nfs","server")),get_property(val,("spec","nfs","path")))
    elif storage_class == "default":
        return get_property(val,("spec","azureDisk","diskURI"))
    else:
        return "Storage class({}) Not support".format(storage_class)

def update_volume(cluster,status,metadata,config):
    name = config["metadata"]["name"]
    try:
        obj = PersistentVolume.objects.get(cluster=cluster,name=name)
    except ObjectDoesNotExist as ex:
        obj = PersistentVolume(cluster=cluster,name=name)
    update_fields = set_fields(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("kind","kind",None),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("writable",("spec","accessModes"),lambda val:True if next((v for v in val if "write" in v.lower()),None) else False),
        ("storage_class_name",None,_get_volume_storage_class_name),
        ("volume_mode",("spec","volumeMode"),None),
        ("uuid",("metadata","name"),_get_volume_uuid),
        ("volumepath",None,_get_volume_path),
        ("capacity",("spec","capacity","storage"),_get_volume_capacity),
        ("reclaim_policy",("spec","persistentVolumeReclaimPolicy"),None),
        ("node_affinity",("spec","nodeAffinity"),lambda val:yaml.dump(val)),
    ])

    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        logger.debug("Create PersistentVolume({})".format(obj))
    elif update_fields:
        update_fields.append("refreshed")
        obj.save(update_fields=update_fields)
        logger.debug("Update PersistentVolume({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The PersistentVolume({}) is not changed".format(obj))


def delete_volume(cluster,status,metadata,config):
    name = config["metadata"]["name"]
    del_rows = PersistentVolume.objects.filter(cluster=cluster,name=name).update(deleted=timezone.now())
    if del_rows:
        logger.info("Logically Delete PersistentVolume({}.{})".format(cluster,name))
    """
    del_objs = PersistentVolume.objects.filter(cluster=cluster,name=name).delete()
    if del_objs[0]:
        logger.info("Delete PersistentVolume({}),deleted objects = {}".format(name,del_objs))
    """

def update_volume_claim(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.get(cluster=cluster,name=namespace)
    name = config["metadata"]["name"]
    try:
        obj = PersistentVolumeClaim.objects.get(cluster=cluster,namespace=namespace,name=name)
    except ObjectDoesNotExist as ex:
        obj = PersistentVolumeClaim(cluster=cluster,namespace=namespace,name=name,project=namespace.project)
    update_fields = set_fields(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("writable",("spec","accessModes"),lambda val:True if next((v for v in val if "write" in v.lower()),None) else False),
        ("volume",("spec","volumeName"),lambda val: PersistentVolume.objects.get(cluster=cluster,name=val) if val else None),
    ])

    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        logger.debug("Create PersistentVolumeClaim({})".format(obj))
    elif update_fields:
        update_fields.append("refreshed")
        obj.save(update_fields=update_fields)
        logger.debug("Update PersistentVolumeClaim({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The PersistentVolumeClaim({}) is not changed".format(obj))

def delete_volume_claim(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.filter(cluster=cluster,name=namespace).first()
    if not namespace:
        return
    name = config["metadata"]["name"]
    del_rows = PersistentVolumeClaim.objects.filter(cluster=cluster,namespace=namespace,name=name).update(deleted=timezone.now())
    if del_rows:
        logger.info("Logically delete PersistentVolumeClaim({}.{})".format(namespace,name))
    """
    del_objs = PersistentVolumeClaim.objects.filter(cluster=cluster,namespace=namespace,name=name).delete()
    if del_objs[0]:
        logger.info("Delete PersistentVolumeClaim({}),deleted objects = {}".format(name,del_objs))
    """

def update_workload_envs(workload,config,env_configs):
    """
    Return True if some env is updated;otherwise return False
    """
    if not env_configs:
        del_objs = WorkloadEnv.objects.filter(workload=workload).delete()
        if del_objs[0]:
            logger.debug("Delete the envs for workload({}),deleted objects = {}".format(workload,del_objs))
            return True
        else:
            return False

    def _get_env_value(env_config):
        if "value" in env_config:
            return env_config["value"]
        elif "valueFrom" in env_config and "fieldRef" in env_config["valueFrom"]:
            val = get_property(config,tuple(env_config["valueFrom"]["fieldRef"]["fieldPath"].split(".")))
            if val is None:
                return yaml.dump(env_config["valueFrom"])
            else:
                return val
        elif len(env_config) == 1:
            return None
        else:
            return yaml.dump(env_config)

    updated = False
    name = None
    del_objs = WorkloadEnv.objects.filter(workload=workload).exclude(name__in=[c["name"] for c in env_configs]).delete()
    if del_objs[0]:
        logger.debug("Delete the envs for workload({}),deleted objects = {}".format(workload,del_objs))
        updated = True
    for env_config in env_configs:
        name = env_config["name"]
        try:
            obj = WorkloadEnv.objects.get(workload=workload,name=name)
        except ObjectDoesNotExist as ex:
            obj = WorkloadEnv(workload=workload,name=name)
        update_fields = set_fields(obj,env_config,[
            ("value",None,_get_env_value)
        ])

        if obj.pk is None:
            obj.modified = workload.modified
            obj.created = workload.modified
            obj.save()
            updated = True
            logger.debug("Create deployment workload env({})".format(obj))
        elif update_fields:
            obj.modified = workload.modified
            update_fields.append("modified")
            update_fields.append("refreshed")
            obj.save(update_fields=update_fields)
            updated = True
            logger.debug("Update the deployment workload env({}),update_fields={}".format(obj,update_fields))
        else:
            logger.debug("The deployment workload env({}) is not changed".format(obj))
    return updated

def update_workload_listenings(workload,config):
    """
    Return True if some env is updated;otherwise return False
    """
    listen_configs = get_property(config,("metadata","annotations","field.cattle.io/publicEndpoints"),lambda val: json.loads(val) if val else None)
    if not listen_configs:
        del_objs = WorkloadListening.objects.filter(workload=workload).delete()
        if del_objs[0]:
            logger.debug("Delete the listenings for workload({}),deleted objects = {}".format(workload,del_objs))
            return True
        else:
            return False

    updated = False
    name = None
    del_objs = WorkloadListening.objects.filter(workload=workload).exclude(servicename__in=[c["serviceName"] for c in listen_configs]).delete()
    if del_objs[0]:
        logger.debug("Delete the listenings for workload({}),deleted objects = {}".format(workload,del_objs))
        updated = True

    for listen_config in listen_configs:
        servicename = listen_config["serviceName"]
        try:
            obj = WorkloadListening.objects.get(workload=workload,servicename=servicename)
        except ObjectDoesNotExist as ex:
            obj = WorkloadListening(workload=workload,servicename=servicename)

        update_fields = set_fields(obj,listen_config,[
            ("servicename","serviceName",None),
            ("listen_port","port",lambda val:int(val)),
            ("protocol","protocol",lambda val: val.lower() if val else None),
        ])

        if "ingressName" in listen_config:
            #ingress router
            ingress_rule = IngressRule.objects.get(cluster=workload.cluster,servicename=listen_config["serviceName"])
            set_field(obj,"ingress_rule", ingress_rule,update_fields)
            set_field(obj,"container_port", ingress_rule.serviceport,update_fields)
            #try to update the ingressrule's port if not match
            if ingress_rule.port != obj.listen_port:
                ingress_rule.port = obj.listen_port
                ingress_rule.save(update_fields=["port"])
            if ingress_rule.cluster.ip:
                if listen_config["addresses"] and ingress_rule.cluster.ip not in listen_config["addresses"]:
                    ingress_rule.cluster.ip = listen_config["addresses"][0]
                    ingress_rule.cluster.save(update_fields=["ip"])
            elif listen_config["addresses"]:
                ingress_rule.cluster.ip = listen_config["addresses"][0]
                ingress_rule.cluster.save(update_fields=["ip"])
        else:
            #port mapping
            set_field(obj,"ingress_rule", None,update_fields)
            container_port = None
            dns_name = obj.servicename.split(':',1)[1]
            for ports_config in json.loads(get_property(config,("spec","template","metadata","annotations","field.cattle.io/ports")) or "[]"):
                for port_config in ports_config:
                    if port_config["dnsName"] == dns_name:
                        container_port = int(port_config["containerPort"])
                        break
                if container_port:
                    break
            if not container_port:
                for port_config in get_property(config,("spec","template","spec",'containers',0,"ports")) or []:
                    if int(port_config.get("containerPort",0)) == obj.listen_port and port_config.get("protocol","").lower() == obj.protocol:
                        container_port = obj.listen_port
                        break

            if not container_port:
                raise Exception("Failed to find the container port for the public port({})".format(obj.listen_port))
            set_field(obj,"container_port", container_port,update_fields)

        if obj.pk is None:
            obj.modified = workload.modified
            obj.created = workload.modified
            obj.save()
            updated = True
            logger.debug("Create workload listening({})".format(obj))
        elif update_fields:
            obj.modified = workload.modified
            update_fields.append("modified")
            update_fields.append("refreshed")
            obj.save(update_fields=update_fields)
            updated = True
            logger.debug("Update the workload listening({}),update_fields={}".format(obj,update_fields))
        else:
            logger.debug("The workload listening({}) is not changed".format(obj))
    return updated


def update_workload_volumes(workload,config,spec_config):
    """
    Return True if some env is updated;otherwise return False
    """
    volumemount_configs = get_property(spec_config,("containers",0,"volumeMounts"))
    if not volumemount_configs:
        del_objs = WorkloadVolume.objects.filter(workload=workload).delete()
        if del_objs[0]:
            logger.debug("Delete the volumes for workload({}),deleted objects = {}".format(workload,del_objs))
            return True
        else:
            return False

    updated = False
    name = None
    del_objs = WorkloadVolume.objects.filter(workload=workload).exclude(name__in=[c["name"] for c in volumemount_configs]).delete()
    if del_objs[0]:
        logger.debug("Delete the volumes for workload({}),deleted objects = {}".format(workload,del_objs))
        updated = True

    #exact all volumes from yaml file
    volume_configs = {}
    for volume_config in get_property(spec_config,"volumes") or []:
        volume_configs[volume_config["name"]] = volume_config

    for volumemount_config in volumemount_configs:
        name = volumemount_config["name"]
        try:
            obj = WorkloadVolume.objects.get(workload=workload,name=name)
        except ObjectDoesNotExist as ex:
            obj = WorkloadVolume(workload=workload,name=name)

        writable = get_property(volumemount_config,"readOnly",lambda val: False if val else True)
        update_fields = set_fields(obj,volumemount_config,[
            ("mountpath","mountPath",None),
            ("subpath","subPath",None)
        ])
        volume_config = volume_configs[name]
        if "persistentVolumeClaim" in volume_config:
            #reference the volume from volume claim
            claimname = volume_config["persistentVolumeClaim"]["claimName"]
            set_field(obj,"volume_claim", PersistentVolumeClaim.objects.get(cluster=workload.cluster,namespace=workload.namespace,name=claimname),update_fields)
            set_field(obj,"volume", obj.volume_claim.volume,update_fields)
            set_field(obj,"volumepath", obj.volume_claim.volume.volumepath,update_fields)
            set_field(obj,"other_config", None,update_fields)
            if writable:
                writable = obj.volume_claim.writable
        elif "hostPath" in volume_config:
            hostpath = volume_config["hostPath"]["path"]
            set_field(obj,"volume_claim", None,update_fields)
            set_field(obj,"volumepath", hostpath,update_fields)
            set_field(obj,"volume", PersistentVolume.objects.filter(cluster=workload.cluster,volumepath=hostpath).first(),update_fields)
            set_field(obj,"other_config", None,update_fields)
            if writable and obj.volume:
                writable = obj.volume.writable
        else:
            set_field(obj,"other_config", yaml.dump(volume_config),update_fields)

        set_field(obj,"writable",writable,update_fields)

        if obj.pk is None:
            obj.modified = workload.modified
            obj.created = workload.modified
            obj.save()
            updated = True
            logger.debug("Create deployment workload volume({})".format(obj))
        elif update_fields:
            obj.modified = workload.modified
            update_fields.append("modified")
            update_fields.append("refreshed")
            obj.save(update_fields=update_fields)
            updated = True
            logger.debug("Update the deployment workload volume({}),update_fields={}".format(obj,update_fields))
        else:
            logger.debug("The deployment workload volume({}) is not changed".format(obj))
    return updated


def update_deployment(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.get(cluster=cluster,name=namespace)
    name = config["metadata"]["name"]
    try:
        obj = Workload.objects.get(cluster=cluster,namespace=namespace,name=name)
    except ObjectDoesNotExist as ex:
        obj = Workload(cluster=cluster,namespace=namespace,name=name,project=namespace.project)
    update_fields = set_fields(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("kind","kind",None),
        ("modified",[("spec","template","metadata","annotations","cattle.io/timestamp"),("metadata","creationTimestamp")],lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("replicas",("spec","replicas"),lambda val:int(val) if val else 0),
        ("image",("spec","template","spec","containers",0,"image"),None),
        ("image_pullpolicy",("spec","template","spec","containers",0,"imagePullPolicy"),None),
        ("cmd",("spec","template","spec","containers",0,"args"), lambda val:json.dumps(val) if val else None),
        ("schedule",None,lambda val: None),
        ("failedjobshistorylimit", None,lambda val:None),
        ("successfuljobshistorylimit", None,lambda val:None),
        ("suspend", None,lambda val:None),
        ("concurrency_policy", None,lambda val:None)
    ])
    created = False
    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        created = True
        logger.debug("Create deployment workload({})".format(obj))

    #update envs
    updated = update_workload_envs(obj,config,get_property(config,("spec","template","spec","containers",0,"env")))

    #update listenings
    updated = update_workload_listenings(obj,config) or updated

    #update volumes
    updated = update_workload_volumes(obj,config,get_property(config,("spec","template","spec"))) or updated

    if created:
        pass
    elif update_fields or updated:
        update_fields.append("refreshed")
        obj.save(update_fields=update_fields)
        logger.debug("Update the deployment workload({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The deployment workload({}) is not changed".format(obj))

def delete_deployment(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.filter(cluster=cluster,name=namespace).first()
    if not namespace:
        return
    name = config["metadata"]["name"]
    kind = config["kind"]
    del_rows = Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).update(deleted=timezone.now())
    if del_rows:
        logger.info("Logically delete the deployment workload({2}:{0}.{1})".format(namespace,name,kind))
    """
    del_objs = Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).delete()
    if del_objs[0]:
        logger.info("Delete the deployment workload({}),deleted objects = {}".format(name,del_objs))
    """

def update_cronjob(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.get(cluster=cluster,name=namespace)
    name = config["metadata"]["name"]
    try:
        obj = Workload.objects.get(cluster=cluster,namespace=namespace,name=name)
    except ObjectDoesNotExist as ex:
        obj = Workload(cluster=cluster,namespace=namespace,name=name,project=namespace.project)

    update_fields = set_fields(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("kind","kind",None),
        ("modified",[("spec","jobTemplate","spec","template","metadata","annotations","cattle.io/timestamp"),("metadata","creationTimestamp")],lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("image",("spec","jobTemplate","spec","template","spec","containers",0,"image"),None),
        ("image_pullpolicy",("spec","jobTemplate","spec","template","spec","containers",0,"imagePullPolicy"),None),
        ("replicas",None,lambda val:0),
        ("cmd",("spec","jobTemplate","spec","template","spec","containers",0,"args"), lambda val:json.dumps(val) if val else None),
        ("schedule",("spec","jobTemplate","schedule"), None),
        ("failedjobshistorylimit", ("spec","failedJobsHistoryLimit"),lambda val:int(val) if val else 0),
        ("successfuljobshistorylimit", ("spec","failedJobsHistoryLimit"),lambda val:int(val) if val else 0),
        ("suspend", ("spec","suspend"),lambda val:True if val else False),
        ("concurrency_policy", ("spec","concurrencyPolicy"),None)
    ])

    created = False
    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        created = True
        logger.debug("Create cronjob workload({})".format(obj))

    #update envs
    updated = update_workload_envs(obj,config,get_property(config,("spec","jobTemplate","spec","template","spec","containers",0,"env")))

    #delete all listening objects
    updated = update_workload_listenings(obj,config) or updated

    #update volumes
    updated = update_workload_volumes(obj,config,get_property(config,("spec","jobTemplate","spec","template","spec"))) or updated

    if created:
        pass
    elif update_fields or updated:
        update_fields.append("refreshed")
        obj.save(update_fields=update_fields)
        logger.debug("Update the cronjob workload({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The cronjob workload({}) is not changed".format(obj))

def delete_cronjob(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.filter(cluster=cluster,name=namespace).first()
    if not namespace:
        return
    name = config["metadata"]["name"]
    kind = config["kind"]
    del_rows = Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).update(deleted=timezone.now())
    if del_rows:
        logger.info("Logically delete the cronjob workload({2}:{0}.{1})".format(namespace,name,kind))
    """
    del_objs = Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).delete()
    if del_objs[0]:
        logger.info("Delete the cronjob workload({}),deleted objects = {}".format(name,del_objs))
    """

def update_statefulset(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.get(cluster=cluster,name=namespace)
    name = config["metadata"]["name"]
    try:
        obj = Workload.objects.get(cluster=cluster,namespace=namespace,name=name)
    except ObjectDoesNotExist as ex:
        obj = Workload(cluster=cluster,namespace=namespace,name=name,project=namespace.project)

    update_fields = set_fields(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("kind","kind",None),
        ("modified",[("spec","template","metadata","annotations","cattle.io/timestamp"),("metadata","creationTimestamp")],lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("image",("spec","template","spec","containers",0,"image"),None),
        ("image_pullpolicy",("spec","template","spec","containers",0,"imagePullPolicy"),None),
        ("replicas",None,lambda val:0),
        ("cmd",("spec","template","spec","containers",0,"args"), lambda val:json.dumps(val) if val else None),
        ("schedule",None, lambda val: None),
        ("failedjobshistorylimit", None,lambda val:None),
        ("successfuljobshistorylimit", None,lambda val:None),
        ("suspend", None,lambda val:None),
        ("concurrency_policy", None,lambda val:None)
    ])

    created = False
    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        created = True
        logger.debug("Create statefulset workload({})".format(obj))

    #update envs
    updated = update_workload_envs(obj,config,get_property(config,("spec","template","spec","containers",0,"env")))

    #update listenings
    updated = update_workload_listenings(obj,config) or updated

    #update volumes
    updated = update_workload_volumes(obj,config,get_property(config,("spec","template","spec"))) or updated

    #update database server if it is a database server
    image_name_lower = obj.image.lower()
    for key,dbtype,default_port in (
        ("postgis",DatabaseServer.POSTGRES,5432),
        ("postgres",DatabaseServer.POSTGRES,5432),
        ("mysql",DatabaseServer.MYSQL,3306),
        ("oracle",DatabaseServer.ORACLE,1521)
    ):
        if key not in image_name_lower:
            continue

        #postgres related image
        listening =  obj.listenings.first()
        if listening:
            listen_port = listening.listen_port
            internal_port = listening.container_port
        elif "admin" in obj.name:
            #is a database admin
            continue
        else:
            listen_port = None
            internal_port = default_port
        #it is a postgres server
        database_server = update_databaseserver(obj.cluster.name,dbtype,listen_port,obj.modified,
            ip=obj.cluster.ip,
            internal_name="{}/{}".format(obj.namespace.name,obj.name),
            internal_port=internal_port,
            workload=obj
        )
        break
    if created:
        pass
    elif update_fields or updated:
        update_fields.append("refreshed")
        obj.save(update_fields=update_fields)
        logger.debug("Update the statefulset workload({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The statefulset workload({}) is not changed".format(obj))

def delete_statefulset(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    namespace = Namespace.objects.filter(cluster=cluster,name=namespace).first()
    if not namespace:
        return
    name = config["metadata"]["name"]
    kind = config["kind"]
    del_rows = Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).update(deleted=timezone.now())
    if del_rows:
        logger.info("Logically delete the statefulset workload({2}:{0}.{1})".format(namespace,name,kind))
    """
    del_objs = Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).delete()
    if del_objs[0]:
        logger.info("Delete the statefulset workload({}),deleted objects = {}".format(name,del_objs))
    """

def update_databaseserver(hostname,kind,port,modified,host=None,ip=None,internal_name=None,internal_port=None,workload=None):
    if not port:
        port = None
    else:
        port = int(port)
    try:
        if port:
            server = DatabaseServer.objects.get(host=hostname,port=port)
        elif internal_name:
            server = DatabaseServer.objects.get(host=hostname,internal_name=internal_name)
        else:
            server = DatabaseServer.objects.get(host=hostname)
    except ObjectDoesNotExist as ex:
        server = DatabaseServer(host=hostname,port=port,modified=modified)
    update_fields = []
    set_field(server,"ip", ip,update_fields)
    set_field(server,"kind", kind,update_fields)
    set_field(server,"workload", workload,update_fields)
    if internal_name:
        set_field(server,"internal_name",internal_name,update_fields)
    if internal_port:
        set_field(server,"internal_port",internal_port,update_fields)
    if host and host != hostname and (not server.other_names or host not in server.other_names):
        if server.other_names:
            server.other_names.append(host)
        else:
            server.other_names = [host]
        update_fields.append("other_names")

    if server.pk is None:
        server.created = server.modified
        server.save()
        logger.debug("Create database server({})".format(server))
    elif update_fields:
        update_fields.append("refreshed")
        server.save(update_fields=update_fields)
        logger.debug("Update database server({}),update_fields={}".format(server,update_fields))
    else:
        logger.debug("The database server({}) is not changed".format(server))

    return server


def update_database(server,name,modified):
    try:
        database = Database.objects.get(server=server,name=name)
    except ObjectDoesNotExist as ex:
        database = Database(server=server,name=name,created=modified)
        database.save()

    return database

def update_databaseuser(server,user,password,modified):
    try:
        database_user = DatabaseUser.objects.get(server=server,user=user)
    except ObjectDoesNotExist as ex:
        database_user = DatabaseUser(server=server,user=user,modified=modified)
    update_fields = []
    set_field(database_user,"password", password,update_fields)
    if database_user.pk is None:
        database_user.created = database_user.modified
        database_user.save()
        logger.debug("Create database user({})".format(database_user))
    elif update_fields:
        update_fields.append("refreshed")
        database_user.save(update_fields=update_fields)
        logger.debug("Update database user({}),update_fields={}".format(database_user,update_fields))
    else:
        logger.debug("The database user({}) is not changed".format(database_user))

    return database_user

def update_workloaddatabase(workload,database,user,password,config_items,modified,schema=None):
    """
    Return the workloaddatabase object
    """
    try:
        workload_database = WorkloadDatabase.objects.get(workload=workload,database=database,config_items=config_items)
    except ObjectDoesNotExist as ex:
        workload_database = WorkloadDatabase(workload=workload,database=database,modified=modified,config_items=config_items)
    update_fields = []
    set_field(workload_database,"user", user,update_fields)
    set_field(workload_database,"password", password,update_fields)
    set_field(workload_database,"schema", schema,update_fields)
    if workload_database.pk is None:
        workload_database.created = workload_database.modified
        workload_database.save()
        logger.debug("Create database({1}) for workload({0})".format(workload,database))
    elif update_fields:
        update_fields.append("refreshed")
        workload_database.save(update_fields=update_fields)
        logger.debug("Update database({1}) for workload({0}),update_fields={2}".format(workload,database,update_fields))
    else:
        logger.debug("The database({1}) for workload({0}) is not changed".format(workload,database))

    return workload_database


ip_re = re.compile("^[0-9]{1,3}(\.[0-9]{1,3}){3,3}$")
postgres_connection_string_re = re.compile('^\s*(?P<database>(postgis)|(postgres))://(?P<user>[a-zA-Z0-9@\-_\.]+)(:(?P<password>[0-9a-zA-Z]+))?@(?P<host>[a-zA-Z0-9\-\_\.@]+)(:(?P<port>[1-9][0-9]*))?/(?P<dbname>[0-9a-zA-Z\-_]+)?\s*$')

database_env_re = re.compile("(db|database|host|server)",re.IGNORECASE)
database_user_re = re.compile("[_\-]?(user[_\-]?name|user[_\-]?account|user|account)[_\-]?",re.IGNORECASE)
database_password_re = re.compile("[_\-]?(password|passwd|pass)[_\-]?",re.IGNORECASE)
database_dbname_re = re.compile("[_\-]?(name)[_\-]?",re.IGNORECASE)
database_schema_re = re.compile("[_\-]?(schema)[_\-]?",re.IGNORECASE)
database_port_re = re.compile("[_\-]?port[_\-]?",re.IGNORECASE)
database_server_re = re.compile("[_\-]?(host|server)[_\-]?",re.IGNORECASE)

oracle_connection_re = re.compile("^(?P<host>[a-zA-Z0-9_\-\.\@]+)(:(?P<port>[0-9]+))?/(?P<dbname>[a-zA-Z0-9_\-]+)$")


def parse_host(host):
    """
    Return hostname and ip if have
    """
    ip = None
    if ip_re.search(host):
        #ip address
        hostname = host
        ip = host
        domain = None
    elif "." in host:
        hostname,domain = host.split(".",1)
    else:
        hostname = host
        domain = None

    return (hostname,ip)

def analysis_workloadenv(cluster=None,refresh_time=None):
    #parse pgsql connection string
    qs =  WorkloadEnv.objects.all()
    if cluster:
        qs = qs.filter(workload__cluster = cluster)

    if refresh_time:
        qs = qs.filter(workload__refreshed__gte = refresh_time)

    qs = qs.order_by("workload","name")
    processed_envs = {}
    for env_obj in qs:
        if not env_obj.value:
            continue
        m = postgres_connection_string_re.search(env_obj.value)
        if not m:
            #not a postgres connection string
            continue
        user = m.group("user")
        password = m.group("password")
        host = m.group("host")
        port = int(m.group("port") or 5432)
        dbname = m.group("dbname")
        #get or create the database server
        #check whether the database is a internal database
        server = DatabaseServer.objects.filter(internal_name="{}/{}".format(env_obj.workload.namespace.name,host)).first()
        if not server:
            #not a internal database
            hostname,ip = parse_host(host)
            server = update_databaseserver(hostname,DatabaseServer.POSTGRES,port,env_obj.modified,host=host,ip=ip)

        #get or create the database
        database = update_database(server,dbname,env_obj.modified)

        #get or create the database user
        database_user = update_databaseuser(server,user,password,env_obj.modified)

        #creata workloaddatabase
        workload_database = update_workloaddatabase(env_obj.workload,database,database_user,password,env_obj.name,env_obj.modified)
        processed_envs[env_obj.id] = workload_database.id

    previous_workload = None
    databases = [[],[],[],[],[],[],[]]
    config_values = [None,None,None,None,None,None,None]
    config_items = [None,None,None,None,None,None]
    existing_workload_databases = []

    for env_obj in itertools.chain(qs,[WorkloadEnv(workload=Workload(id=-1),name='test',value=None)]):
        if not previous_workload:
            previous_workload = env_obj.workload
        elif previous_workload != env_obj.workload:
            if databases[4]:
                config_databases = []
                run_times = 0
                while run_times < 2:
                    run_times += 1
                    for user_config in databases[4]:
                        if user_config[3]:
                            continue
                        kind = None
                        config_values[4] = user_config[0].value
                        config_items[4] = user_config[0].name
                        config_values[6] = user_config[0].modified

                        config_values[0] = config_values[1] = config_values[2] = config_values[3] = config_values[5] = None
                        config_items[0]  = config_items[1]  = config_items[2]  = config_items[3]  = config_items[5]  = None
                        #try to find the host
                        if len(databases[0]) == 1 and len(databases[4]) == 1:
                            #has only one configration,use it directly
                            config_values[0] = databases[0][0][0].value
                            config_items[0] = databases[0][0][0].name
                            if config_values[6] < databases[0][0][0].modified:
                                config_values[6] = databases[0][0][0].modified
                        elif len(databases[0]) > 0:
                            for server_config in databases[0]:
                                if server_config[3]:
                                    continue
                                #check whether name pattern is matched or not
                                if (
                                    (user_config[1] and server_config[1] and (user_config[1].startswith(server_config[1]) or server_config[1].startswith(user_config[1])))
                                    or (user_config[2] and server_config[2] and (user_config[2].startswith(server_config[2]) or server_config[2].startswith(user_config[2])))
                                ):
                                    config_values[0] = server_config[0].value
                                    config_items[0] = server_config[0].name
                                    if config_values[6] < server_config[0].modified:
                                        config_values[6] = server_config[0].modified
                                    server_config[3] = True
                                    break
                            if not config_values[0]:
                                #can't locate the server
                                if run_times == 1:
                                    #the first round only locates the server through name pattern
                                    continue
                                else:
                                    #try to use the unused configured server host as its host
                                    for server_config in databases[0]:
                                        if server_config[3]:
                                            continue
                                        config_values[0] = server_config[0].value
                                        config_items[0] = server_config[0].name
                                        if config_values[6] < server_config[0].modified:
                                            config_values[6] = server_config[0].modified
                                        server_config[3] = True
                                        break
                                    if not config_values[0]:
                                        #try to find a host configuration from more database configrations
                                        for server_config in databases[6]:
                                            if server_config[3]:
                                                continue
                                            matched = False
                                            if oracle_connection_re.search(server_config[0].value):
                                                #is a oracle connection
                                                matched = True
                                            if not matched:
                                                hostname,ip = parse_host(server_config[0].value)
                                                if DatabaseServer.objects.filter(host=hostname).exists():
                                                    #is a database host
                                                    matched = True
                                            if not matched:
                                                 try:
                                                     if socket.gethostbyname(server_config[0].value):
                                                         #is a host
                                                        matched = True
                                                 except:
                                                    pass
                                            if not matched:
                                                continue
                                            config_values[0] = server_config[0].value
                                            config_items[0] = server_config[0].name
                                            if config_values[6] < server_config[0].modified:
                                                config_values[6] = server_config[0].modified
                                            server_config[3] = True
                                            break

                        m = oracle_connection_re.search(config_values[0])
                        if m:
                            kind = DatabaseServer.ORACLE
                            config_values[1] = int(m.group("port") or 1521)
                            config_items[1] = None
                            config_values[2] = m.group("dbname")
                            config_items[2] = None
                            config_values[0] = m.group("host")


                        #try to find the schema
                        if config_values[3]:
                            pass
                        elif len(databases[3]) == 1 and len(databases[4]) == 1:
                            #has only one configration,use it directly
                            config_values[3] = databases[3][0][0].value
                            config_items[3] = databases[3][0][0].name
                            if config_values[6] < databases[3][0][0].modified:
                                config_values[6] = databases[3][0][0].modified
                        elif len(databases[3]) > 0:
                            for schema_config in databases[3]:
                                if schema_config[3]:
                                    continue
                                #check whether name pattern is matched or not
                                if (
                                    (user_config[1] and schema_config[1] and (user_config[1].startswith(schema_config[1]) or schema_config[1].startswith(user_config[1])))
                                    or (user_config[2] and schema_config[2] and (user_config[2].startswith(schema_config[2]) or schema_config[2].startswith(user_config[2])))
                                ):
                                    config_values[3] = schema_config[0].value
                                    config_items[3] = schema_config[0].name
                                    if config_values[6] < schema_config[0].modified:
                                        config_values[6] = schema_config[0].modified
                                    schema_config[3] = True
                                    break

                        #try to find the password
                        if config_values[5]:
                            pass
                        elif len(databases[5]) == 1 and len(databases[4]) == 1:
                            #has only one configration,use it directly
                            config_values[5] = databases[5][0][0].value
                            config_items[5] = databases[5][0][0].name
                            if config_values[6] < databases[5][0][0].modified:
                                config_values[6] = databases[5][0][0].modified
                        elif len(databases[5]) > 0:
                            for pass_config in databases[5]:
                                if pass_config[3]:
                                    continue
                                #check whether name pattern is matched or not
                                if (
                                    (user_config[1] and pass_config[1] and (user_config[1].startswith(pass_config[1]) or pass_config[1].startswith(user_config[1])))
                                    or (user_config[2] and pass_config[2] and (user_config[2].startswith(pass_config[2]) or pass_config[2].startswith(user_config[2])))
                                ):
                                    config_values[5] = pass_config[0].value
                                    config_items[5] = pass_config[0].name
                                    if config_values[6] < pass_config[0].modified:
                                        config_values[6] = pass_config[0].modified
                                    pass_config[3] = True
                                    break
                        #try to find the dbname
                        if config_values[2]:
                            pass
                        elif len(databases[2]) == 1 and len(databases[4]) == 1:
                            #has only one configration,use it directly
                            config_values[2] = databases[2][0][0].value
                            config_items[2] = databases[2][0][0].name
                            if config_values[6] < databases[2][0][0].modified:
                                config_values[6] = databases[2][0][0].modified
                        elif len(databases[2]) > 0:
                            for dbname_config in databases[2]:
                                if dbname_config[3]:
                                    continue
                                #check whether name pattern is matched or not
                                if (
                                    (user_config[1] and dbname_config[1] and (user_config[1].startswith(dbname_config[1]) or dbname_config[1].startswith(user_config[1])))
                                    or (user_config[2] and dbname_config[2] and (user_config[2].startswith(dbname_config[2]) or dbname_config[2].startswith(user_config[2])))
                                ):
                                    config_values[2] = dbname_config[0].value
                                    config_items[2] = dbname_config[0].name
                                    if config_values[6] < dbname_config[0].modified:
                                        config_values[6] = dbname_config[0].modified
                                    dbname_config[3] = True
                                    break

                            if not config_values[2]:
                                logger.warning("Can't find the dbname for dbuser({}={})".format(user_config[0].name,user_config[0].value))
                                continue

                        #try to find the port
                        if config_values[1]:
                            pass
                        elif len(databases[1]) == 1 and len(databases[4]) == 1:
                            #has only one configration,use it directly
                            config_values[1] = int(databases[1][0][0].value) if databases[1][0][0].value else None
                            config_items[1] = databases[1][0][0].name
                            if config_values[6] < databases[1][0][0].modified:
                                config_values[6] = databases[1][0][0].modified
                        elif len(databases[1]) > 0:
                            for port_config in databases[1]:
                                if port_config[3]:
                                    continue
                                #check whether name pattern is matched or not
                                if (
                                    (user_config[1] and port_config[1] and (user_config[1].startswith(port_config[1]) or port_config[1].startswith(user_config[1])))
                                    or (user_config[2] and port_config[2] and (user_config[2].startswith(port_config[2]) or port_config[2].startswith(user_config[2])))
                                ):
                                    config_values[1] = int(port_config[0].value) if port_config[0].value else None
                                    config_items[1] = port_config[0].name
                                    if config_values[6] < port_config[0].modified:
                                        config_values[6] = port_config[0].modified
                                    port_config[3] = True
                                    break

                        hostname,ip = parse_host(config_values[0])
                        if config_values[1]:
                            server = DatabaseServer.objects.filter(host=hostname,port=config_values[1]).first()
                        elif DatabaseServer.objects.filter(host=hostname).count() == 1:
                            server = DatabaseServer.objects.filter(host=hostname).first()
                        if server:
                            kind = server.kind
                            if not config_values[1]:
                                config_values[1] = server.port
                        elif not kind:
                            if any(name in hostname for name in ("pgsql","postgres","postgis","pg")):
                                kind = DatabaseServer.POSTGRES
                                if not config_values[1]:
                                    config_values[1] = 5432
                            elif any(name in hostname for name in ("mysql","my")):
                                kind = DatabaseServer.MYSQL
                                if not config_values[1]:
                                    config_values[1] = 3306
                            elif any(name in hostname for name in ("oracle","ora")):
                                kind = DatabaseServer.ORACLE
                                if not config_values[1]:
                                    config_values[1] = 1521

                        user_config[3] = True

                        if not config_values[2]:
                            logger.warning("Can't find the dbname ,workload({})={} ,related envs = {}".format( previous_workload.id,previous_workload.name,[i for i in config_items if i]))
                            config_values[2] = "_default_"

                        server = DatabaseServer.objects.filter(internal_name="{}/{}".format(previous_workload.namespace.name,hostname)).first()
                        if not server:
                            #not a internal database
                            server = update_databaseserver(hostname,kind,config_values[1],config_values[6],host=config_values[0],ip=ip)

                        #get or create the database
                        database = update_database(server,config_values[2],config_values[6])

                        #get or create the database user
                        database_user = update_databaseuser(server,config_values[4],config_values[5],config_values[6])

                        #creata workloaddatabase
                        workload_database = update_workloaddatabase(previous_workload,database,database_user,config_values[5],",".join(name for name in config_items if name),config_values[6],schema=config_values[3])
                        existing_workload_databases.append(workload_database.id)

            #delete non-existing workload databases
            del_objs = WorkloadDatabase.objects.filter(workload=previous_workload).exclude(id__in=existing_workload_databases).delete()
            if del_objs[0]:
                logger.debug("Delete the databases for workload({}),deleted objects = {}".format(previous_workload,del_objs))

            #clean the existing workload databases
            existing_workload_databases.clear()

            #clean previous data
            for field_list in databases:
                field_list.clear()
            previous_workload = env_obj.workload

        if not env_obj.value:
            continue
        if env_obj.id not in processed_envs and not database_env_re.search(env_obj.name):
            continue

        if env_obj.id in processed_envs:
            existing_workload_databases.append(processed_envs[env_obj.id])
            continue

        for field_re,field_list  in (
            (database_server_re,databases[0]),
            (database_port_re,databases[1]),
            (database_user_re,databases[4]),
            (database_dbname_re,databases[2]),
            (database_schema_re,databases[3]),
            (database_password_re,databases[5]),
            (database_env_re,databases[6])
        ):
            m = field_re.search(env_obj.name)
            if not m:
                continue
            prefix,suffix = env_obj.name.split(m.group(),1)
            field_list.append([env_obj,prefix.lower(),suffix.lower(),False])
            break

process_func_map = {
    10:update_namespace,
    20:update_volume,
    30:update_volume_claim,
    40:update_ingress,
    50:update_statefulset,
    60:update_deployment,
    70:update_cronjob,
    80:delete_cronjob,
    90:delete_deployment,
    100:delete_statefulset,
    110:delete_ingress,
    120:delete_volume_claim,
    130:delete_volume,
    140:delete_namespace
}

def resource_type(status,resource_id):
    if status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and NAMESPACE_RE.search(resource_id):
        return 10
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and VOLUMN_RE.search(resource_id):
        return 20
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and VOLUMN_CLAIM_RE.search(resource_id):
        return 30
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and INGRESS_RE.search(resource_id):
        return 40
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and STATEFULSET_RE.search(resource_id):
        return 50
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and DEPLOYMENT_RE.search(resource_id):
        return 60
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and CRONJOB_RE.search(resource_id):
        return 70
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and CRONJOB_RE.search(resource_id):
        return 80
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and DEPLOYMENT_RE.search(resource_id):
        return 90
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and STATEFULSET_RE.search(resource_id):
        return 100
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and INGRESS_RE.search(resource_id):
        return 110
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and VOLUMN_CLAIM_RE.search(resource_id):
        return 120
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and VOLUMN_RE.search(resource_id):
        return 130
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and NAMESPACE_RE.search(resource_id):
        return 140
    else:
        raise Exception("Not Support. status={}, resource_id={}".format(status,resource_id))

def sort_key(val):
    return resource_type(val[0],val[1][0])


def process_rancher(cluster):
    def _func(status,metadata,config_file):
        process_func = process_func_map[resource_type(status,metadata["resource_id"])]
        if config_file:
            with open(config_file) as f:
                config = yaml.load(f.read())
            with transaction.atomic():
                process_func(cluster,status,metadata,config)

    return _func

def resource_filter(resource_id):
    return True if RANCHER_FILE_RE.search(resource_id) else False

def harvest(cluster,reconsume=False):
    renew_lock_time = None
    try:
        cluster = Cluster.objects.get(name=cluster)
        
        try:
            renew_lock_time = get_consume_client(cluster.name).acquire_lock(expired=3000)
        except exceptions.AlreadyLocked as ex: 
            msg = "The previous harvest process is still running.{}".format(str(ex))
            logger.info(msg)
            return ([],[(None,None,None,msg)])
        
        now = timezone.now()
        result = get_consume_client(cluster.name).consume(process_rancher(cluster),reconsume=reconsume,resources=resource_filter,sortkey_func=sort_key,stop_if_failed=False)
        #analysis the workload env.
        analysis_workloadenv(cluster,None)
        cluster.refreshed = timezone.now()
        cluster.succeed_resources = len(result[0])
        cluster.failed_resources = len(result[1])
        if result[1]:
            if result[0]:
                message = """Failed to refresh cluster({}),
{} configuration files were consumed successfully.
{}
{} configuration files were consumed failed
{}"""
                message = message.format(
                    cluster.name,
                    len(result[0]),
                    "\n        ".join(["Succeed to harvest {} resource '{}'".format(resource_status_name,resource_ids) for resource_status,resource_status_name,resource_ids in result[0]]),
                    len(result[1]),
                    "\n        ".join(["Failed to harvest {} resource '{}'.{}".format(resource_status_name,resource_ids,msg) for resource_status,resource_status_name,resource_ids,msg in result[1]])
                )
            else:
                message = """Failed to refresh cluster({}),{} configuration files were consumed failed
{}"""
                message = message.format(
                    cluster.name,
                    len(result[1]),
                    "\n        ".join(["Failed to harvest {} resource '{}'.{}".format(resource_status_name,resource_ids,msg) for resource_status,resource_status_name,resource_ids,msg in result[1]])
                )
        elif result[0]:
            message = """Succeed to refresh cluster({}), {} configuration files were consumed successfully.
{}"""
            message = message.format(
                cluster.name,
                len(result[0]),
                "\n        ".join(["Succeed to harvest {} resource '{}'".format(resource_status_name,resource_ids) for resource_status,resource_status_name,resource_ids in result[0]])
            )
        else:
            message = "Succeed to refresh cluster({}), no configuration files was changed since last consuming".format(cluster.name)

        cluster.refresh_message = message
        cluster.save(update_fields=["refreshed","succeed_resources","failed_resources","refresh_message"])

        return result
    finally:
        WebAppLocationServer.refresh_rancher_workload(cluster)
        if renew_lock_time:
            get_consume_client(cluster.name).release_lock()

def harvest_all(reconsume=False):
    consume_results = []
    for cluster in Cluster.objects.all():
        consume_results.append((cluster,harvest(cluster,reconsume=reconsume)))

    return consume_results
