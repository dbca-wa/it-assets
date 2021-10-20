import yaml
import base64
import re
import logging
import traceback
import json
from datetime import date,datetime,timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models as django_models
from django.utils import timezone
from django.db import transaction

from data_storage import ResourceConsumeClient, AzureBlobStorage,exceptions,LockSession
from . import models
from data_storage.utils import get_property
from .utils import set_fields,set_field,set_fields_from_config
from . import modeldata

logger = logging.getLogger(__name__)

RANCHER_FILE_RE=re.compile("(^|/)(ingress-|cronjob-|deployment-|daemonset-|persistentvolumeclaim-|persistentvolume-|namespace-|statefulset-|configmap-|secret-).+\.(yaml|yml)$")

VOLUMN_RE=re.compile("(^|/)persistentvolume-.+\.(yaml|yml)$")
VOLUMN_CLAIM_RE=re.compile("(^|/)persistentvolumeclaim.+\.(yaml|yml)$")
DEPLOYMENT_RE=re.compile("(^|/)deployment-.+\.(yaml|yml)$")
CRONJOB_RE=re.compile("(^|/)cronjob-.+\.(yaml|yml)$")
DAEMONSET_RE=re.compile("(^|/)daemonset-.+\.(yaml|yml)$")
NAMESPACE_RE=re.compile("(^|/)namespace-.+\.(yaml|yml)$")
INGRESS_RE=re.compile("(^|/)ingress-.+\.(yaml|yml)$")
STATEFULSET_RE=re.compile("(^|/)statefulset-.+\.(yaml|yml)$")
CONFIGMAP_RE=re.compile("(^|/)configmap-.+\.(yaml|yml)$")
SECRET_RE=re.compile("(^|/)secret-.+\.(yaml|yml)$")

harvestername = "clusterconfig({})"

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
        elif isinstance(obj,django_models.Model):
            return str(obj)

        return json.JSONEncoder.default(self,obj)

_consume_clients = {}
def get_client(cluster,cache=True):
    """
    Return the blob resource client
    """
    if cluster not in _consume_clients or not cache:
        client = ResourceConsumeClient(
            AzureBlobStorage(settings.RANCHER_STORAGE_CONNECTION_STRING,settings.RANCHER_CONTAINER),
            settings.RANCHER_RESOURCE_NAME,
            settings.RESOURCE_CLIENTID,
            resource_base_path="{}/{}".format(settings.RANCHER_RESOURCE_NAME,cluster)

        )
        if cache:
            _consume_clients[cluster] = client
        else:
            return client
    return _consume_clients[cluster]

def update_project(cluster,projectid):
    if not projectid:
        return None
    try:
        obj = models.Project.objects.get(cluster=cluster,projectid=projectid)
    except ObjectDoesNotExist as ex:
        obj = models.Project(cluster=cluster,projectid=projectid)

    update_fields = None

    if obj.pk is None:
        obj.save()
        logger.debug("Create project({})".format(obj))
    elif update_fields:
        obj.save(update_fields=update_fields)
        logger.debug("Update project({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The project({}) is not changed".format(obj))

    return obj

def update_namespace(cluster,status,metadata,config):
    project_name = get_property(config,("metadata","annotations","field.cattle.io/projectId"))
    name = get_property(config,("metadata","name"))
    if not name:
        return None

    """
    project_id = get_property(config,("metadata","labels","field.cattle.io/projectId"))
    if not project_id:
        #can't find the project id. it is not a valid namespace, ignore
        return
    """

    try:
        obj = models.Namespace.objects.get(cluster=cluster,name=name)
    except ObjectDoesNotExist as ex:
        obj = models.Namespace(cluster=cluster,name=name)

    update_fields = set_fields_from_config(obj,config,[
        ("deleted",None,lambda obj:None),
        ("added_by_log",None,lambda obj:False),
        ("api_version","apiVersion",None),
        ("system_namespace",("metadata","annotations","management.cattle.io/system-namespace"),lambda v: True if v and v.lower() == "true" else False),
        ("project",("metadata","labels","field.cattle.io/projectId"),lambda val:update_project(cluster,val)),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) )
    ])
    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        logger.debug("Create namespace({})".format(obj))
    elif update_fields:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update namespace({}),update_fields={}".format(obj,update_fields))
        if "project" in update_fields :
            #namespace's project is changed,
            #update models.PersistentVolumeClaim
            models.PersistentVolumeClaim.objects.filter(cluster=cluster,namespace=obj).update(project=obj.project)
            #update models.Ingress
            models.Ingress.objects.filter(cluster=cluster,namespace=obj).update(project=obj.project)
            #update models.Workload
            models.Workload.objects.filter(cluster=cluster,namespace=obj).update(project=obj.project)

    else:
        logger.debug("The namespace({}) is not changed".format(obj))


    #try to update the clusterid if it is empty or not match
    if project_name and ":" in project_name:
        cluster_id,project_id = project_name.split(':',1)
        if project_id == obj.project.projectid:
            if cluster.clusterid != cluster_id:
                cluster.clusterid = cluster_id
                cluster.save(update_fields=["clusterid"])

    return obj

def delete_namespace(cluster,status,metadata,config):
    name = config["metadata"]["name"]

    obj = models.Namespace.objects.filter(cluster=cluster,name=name).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically delete namespace({}.{})".format(cluster,name))

    return obj

def update_secret(cluster,status,metadata,config):
    project_id = get_property(config,("metadata","annotations","field.cattle.io/projectId"))
    namespace = get_property(config,("metadata","namespace"))
    if project_id and namespace:
        #project scope secret
        if project_id.endswith(namespace):
            try:
                project = models.Project.objects.get(cluster=cluster,projectid=namespace)
            except ObjectDoesNotExist as ex:
                logger.error("Project({}) does not exist".format(namespace))
                raise
            namespace = None
        else:
            #namespace-scope secret created by system from project-scope secret
            return None
    else:
        try:
            namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
        except ObjectDoesNotExist as ex:
            logger.error("Namespace({}) does not exist".format(namespace))
            raise
        project = None

    name = config["metadata"]["name"]
    try:
        if project:
            obj = models.Secret.objects.get(cluster=cluster,project=project,name=name)
        elif namespace.project:
            obj = models.Secret.objects.get(cluster=cluster,project=namespace.project,name=name)
        else:
            obj = models.Secret.objects.get(cluster=cluster,project__isnull=True,name=name)

    except ObjectDoesNotExist as ex:
        if project:
            obj = models.Secret(cluster=cluster,project=project,name=name)
        else:
            obj = models.Secret(cluster=cluster,project=namespace.project,name=name)

    update_fields = set_fields_from_config(obj,config,[
        ("api_version","apiVersion",None),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) )
    ])
    set_field(obj,"namespace",namespace,update_fields)

    created = False
    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        created = True
        logger.debug("Create secret({})".format(obj))

    items_changed = False
    #save secret items
    config_ids = []
    for key,value in config.get("data",{}).items():
        try:
            item = models.SecretItem.objects.get(secret=obj,name=key)
        except ObjectDoesNotExist as ex:
            item = models.SecretItem(secret=obj,name=key)
        try:
            value = base64.b64decode(value).decode()
        except:
            pass

        config_ids.append(item.id)

        item_update_fields = set_fields(item,[
            ("value",value)
        ])
        if item.pk is None:
            item.created = obj.modified
            item.modified = obj.modified
            item.save()
            items_changed = True
        elif item_update_fields:
            item_update_fields.append("updated")
            item_update_fields.append("modified")
            item.modified = obj.modified
            item.save(update_fields=item_update_fields)
            items_changed = True

    del_objs = models.SecretItem.objects.filter(secret=obj).exclude(id__in=config_ids).delete()
    if del_objs[0]:
        items_changed = True

    if created:
        pass
    elif update_fields or items_changed:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update secret({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The secret({}) is not changed".format(obj))

    return obj


def delete_secret(cluster,status,metadata,config):
    project_id = get_property(config,("metadata","annotations","field.cattle.io/projectId"))
    namespace = get_property(config,("metadata","namespace"))
    if project_id and namespace:
        #project scope secret
        if project_id.endswith(namespace):
            try:
                project = models.Project.objects.get(cluster=cluster,projectid=namespace)
            except ObjectDoesNotExist as ex:
                logger.error("Project({}) does not exist".format(namespace))
                raise
            namespace = None
        else:
            #namespace-scope secret created by system from project-scope secret
            return None
    else:
        try:
            namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
        except ObjectDoesNotExist as ex:
            logger.error("Namespace({}) does not exist".format(namespace))
            raise
        project = None

    name = config["metadata"]["name"]

    if project:
        obj = models.Secret.objects.filter(cluster=cluster,project=project,name=name).first()
    elif namespace.project:
        obj = models.Secret.objects.filter(cluster=cluster,project=namespace.project,name=name).first()
    else:
        obj = models.Secret.objects.filter(cluster=cluster,project__isnull=True,name=name).first()

    if obj:
        obj.logically_delete()
        logger.info("Logically delete secret({}.{})".format(cluster,obj))

    return obj

def update_configmap(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]

    try:
        obj = models.ConfigMap.objects.get(cluster=cluster,namespace=namespace,name=name)
    except ObjectDoesNotExist as ex:
        obj = models.ConfigMap(cluster=cluster,namespace=namespace,name=name)

    update_fields = set_fields_from_config(obj,config,[
        ("api_version","apiVersion",None),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) )
    ])
    created = False
    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        created = True
        logger.debug("Create configmap({})".format(obj))

    items_changed = False
    #save configmap items
    config_ids = []
    for key,value in config.get("data",{}).items():
        try:
            item = models.ConfigMapItem.objects.get(configmap=obj,name=key)
        except ObjectDoesNotExist as ex:
            item = models.ConfigMapItem(configmap=obj,name=key)

        config_ids.append(item.id)

        item_update_fields = set_fields(item,[
            ("value",value)
        ])
        if item.pk is None:
            item.created = obj.modified
            item.modified = obj.modified
            item.save()
            items_changed = True
        elif item_update_fields:
            item_update_fields.append("updated")
            item_update_fields.append("modified")
            item.modified = obj.modified
            item.save(update_fields=item_update_fields)
            items_changed = True

    del_objs = models.ConfigMapItem.objects.filter(configmap=obj).exclude(id__in=config_ids).delete()
    if del_objs[0]:
        items_changed = True

    if created:
        pass
    elif update_fields or items_changed:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update configmap({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The configmap({}) is not changed".format(obj))

    return obj


def delete_configmap(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    obj = models.ConfigMap.objects.filter(cluster=cluster,namespace=namespace,name=name).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically delete configmap({}.{})".format(cluster,obj))

    return obj

def _get_ingress_protocol(val):
    if "http" in val:
        return "http"
    else:
        raise Exception("Failed to extract ingress protocol from {}".format(val))


def update_ingress_rules(ingress,configs):
    """
    Return True if some rules have been changed/deleted ;otherwise return False
    """
    if not configs:
        del_objs = models.IngressRule.objects.filter(ingress=ingress).delete()
        if del_objs[0]:
            logger.debug("Delete the rules for models.Ingress({}),deleted objects = {}".format(ingress,del_objs))
            return True
        else:
            return False

    name = None
    rule_ids = []
    rules_changed = False
    for config in configs:
        hostname = config["host"]
        protocol = _get_ingress_protocol(config)
        for backend in get_property(config,(protocol,"paths")):
            path = backend.get("path","")
            try:
                obj = models.IngressRule.objects.get(ingress=ingress,protocol=protocol,hostname=hostname,path=path)
            except ObjectDoesNotExist as ex:
                obj = models.IngressRule(ingress=ingress,protocol=protocol,hostname=hostname,path=path,cluster=ingress.cluster)
            update_fields = set_fields_from_config(obj,backend,[
                ("servicename",("backend","serviceName"),lambda val: "{}:{}".format(ingress.namespace.name,val)),
                ("serviceport",("backend","servicePort"),lambda val:int(val))
            ])

            if obj.pk is None:
                obj.modified = ingress.modified
                obj.created = ingress.modified
                obj.save()
                rules_changed = True
                logger.debug("Create deployment workload env({})".format(obj))
            elif update_fields:
                obj.modified = ingress.modified
                update_fields.append("modified")
                update_fields.append("updated")
                obj.save(update_fields=update_fields)
                rules_changed = True
                logger.debug("Update the deployment workload env({}),update_fields={}".format(obj,update_fields))
            else:
                logger.debug("The deployment workload env({}) is not changed".format(obj))
            rule_ids.append(obj.pk)

    del_objs = models.IngressRule.objects.filter(ingress=ingress).exclude(pk__in=rule_ids).delete()
    if del_objs[0]:
        logger.debug("Delete the rules for models.Ingress({}),deleted objects = {}".format(ingress,del_objs))
        rules_changed = True

    return rules_changed


def update_ingress(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    try:
        obj = models.Ingress.objects.get(cluster=cluster,namespace=namespace,name=name)
    except ObjectDoesNotExist as ex:
        obj = models.Ingress(cluster=cluster,namespace=namespace,name=name)
    update_fields = set_fields_from_config(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("project",None,lambda val:namespace.project),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
    ])
    created = False
    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        created = True
        logger.debug("Create models.Ingress({})".format(obj))

    #update rules
    rules_changed = update_ingress_rules(obj,get_property(config,("spec","rules")))

    if created:
        pass
    elif update_fields or rules_changed:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update models.Ingress({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The models.Ingress({}) is not changed".format(obj))

    return obj

def delete_ingress(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    obj = models.Ingress.objects.filter(cluster=cluster,namespace=namespace,name=name).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically delete models.Ingress({}.{})".format(namespace,name))

    return obj

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
        obj = models.PersistentVolume.objects.get(cluster=cluster,name=name)
    except ObjectDoesNotExist as ex:
        obj = models.PersistentVolume(cluster=cluster,name=name)

    update_fields = set_fields_from_config(obj,config,[
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
        logger.debug("Create models.PersistentVolume({})".format(obj))
    elif update_fields:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update models.PersistentVolume({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The models.PersistentVolume({}) is not changed".format(obj))

    return obj


def delete_volume(cluster,status,metadata,config):
    name = config["metadata"]["name"]
    obj = models.PersistentVolume.objects.filter(cluster=cluster,name=name).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically Delete models.PersistentVolume({}.{})".format(cluster,name))

    return obj

def update_volume_claim(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    try:
        obj = models.PersistentVolumeClaim.objects.get(cluster=cluster,namespace=namespace,name=name)
    except ObjectDoesNotExist as ex:
        obj = models.PersistentVolumeClaim(cluster=cluster,namespace=namespace,name=name)
    update_fields = set_fields_from_config(obj,config,[
        ("deleted",None,lambda obj:None),
        ("api_version","apiVersion",None),
        ("project",None,lambda val:namespace.project),
        ("modified",("metadata","creationTimestamp"),lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("writable",("spec","accessModes"),lambda val:True if next((v for v in val if "write" in v.lower()),None) else False),
        ("volume",("spec","volumeName"),lambda val: models.PersistentVolume.objects.get(cluster=cluster,name=val) if val else None),
    ])

    if obj.pk is None:
        obj.created = obj.modified
        obj.save()
        logger.debug("Create models.PersistentVolumeClaim({})".format(obj))
    elif update_fields:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update models.PersistentVolumeClaim({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The models.PersistentVolumeClaim({}) is not changed".format(obj))

    return obj

def delete_volume_claim(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    obj = models.PersistentVolumeClaim.objects.filter(cluster=cluster,namespace=namespace,name=name).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically delete models.PersistentVolumeClaim({}.{})".format(namespace,name))

    return obj

env_var_re = re.compile("^[a-zA-Z0-9_\-\.]+$")
def update_workload_envs(workload,config,env_configs,envfrom_configs=None):
    """
    Return True if some env is updated;otherwise return False
    """
    if not env_configs and not envfrom_configs:
        del_objs = models.WorkloadEnv.objects.filter(workload=workload).delete()
        if del_objs[0]:
            logger.debug("Delete the envs for workload({}),deleted objects = {}".format(workload,del_objs))
            return True
        else:
            return False

    def _get_env_value(env_config):
        if "value" in env_config:
            return (env_config["value"],None,None)
        elif "valueFrom" in env_config:
            if "fieldRef" in env_config["valueFrom"]:
                val = get_property(config,tuple(env_config["valueFrom"]["fieldRef"]["fieldPath"].split(".")))
                if val is None:
                    return (yaml.dump(env_config["valueFrom"]),None,None)
                else:
                    return (val,None,None)
            elif "configMapKeyRef" in env_config["valueFrom"]:
                #env from configmap
                configmap_config = env_config["valueFrom"]["configMapKeyRef"]
                configmap_name = configmap_config["name"]
                configmap = models.ConfigMap.objects.get(cluster=workload.cluster,namespace=workload.namespace,name=configmap_name)
                configitem = models.ConfigMapItem.objects.filter(configmap=configmap,name=configmap_config["key"]).first()
                return (configitem.value if configitem else None,configmap,configitem)
        elif len(env_config) == 1:
            return (None,None,None)
        else:
            return (yaml.dump(env_config),None,None)

    env_ids = []
    env_names = []
    def _save_env(workload,k,v,ref,refitem):
        """
        Return True if env changed;otherwise return False
        """
        try:
            obj = models.WorkloadEnv.objects.get(workload=workload,name=k)
        except ObjectDoesNotExist as ex:
            obj = models.WorkloadEnv(workload=workload,name=k)

        update_fields = set_fields(obj,[
            ("value",v),
            ("configmap",ref if (ref and isinstance(ref,models.ConfigMap)) else None),
            ("configmapitem",refitem if (refitem and isinstance(refitem,models.ConfigMapItem)) else None),
            ("secret",ref if (ref and isinstance(ref,models.Secret)) else None),
            ("secretitem",refitem if (refitem and isinstance(refitem,models.SecretItem)) else None)
        ])

        changed = False
        if obj.pk is None:
            obj.modified = workload.modified
            obj.created = workload.modified
            obj.save()
            changed = True
            logger.debug("Create workload env({})".format(obj))
        elif update_fields:
            obj.modified = workload.modified
            update_fields.append("modified")
            update_fields.append("updated")
            obj.save(update_fields=update_fields)
            changed = True
            logger.debug("Update the workload env({}),update_fields={}".format(obj,update_fields))
        else:
            logger.debug("The workload env({}) is not changed".format(obj))
        env_ids.append(obj.id)

        return changed


    updated = False
    name = None
    #update env from env_configs
    for env_config in env_configs or []:
        name = env_config["name"]
        env_names.append(name)
        value,configmap,configitem = _get_env_value(env_config)
        updated = _save_env(workload,name,value,configmap,configitem) or updated

    #update env from envfrom_configs
    for envfrom_config in envfrom_configs or []:
        if "configMapRef" in envfrom_config:
            #env from configMap
            prefix = envfrom_config.get("prefix") or None
            configmap_name = envfrom_config["configMapRef"]["name"]
            configmap = models.ConfigMap.objects.get(cluster=workload.cluster,namespace=workload.namespace,name=configmap_name)
            configitem_qs = models.ConfigMapItem.objects.filter(configmap=configmap)
            if prefix:
                configitem_qs = configitem_qs.filter(name__startswith=prefix)
            for configitem in configitem_qs:
                if configitem.name in env_names:
                    #already declared in workload,ignore
                    continue
                updated = _save_env(workload,configitem.name,configitem.value,configmap,configitem) or updated

        if "secretRef" in envfrom_config:
            #env from secret
            prefix = envfrom_config.get("prefix") or None
            secret_name = envfrom_config["secretRef"]["name"]
            try:
                secret = models.Secret.objects.get(cluster=workload.cluster,project=workload.namespace.project,name=secret_name)
            except ObjectDoesNotExist as ex:
                if workload.namespace.project:
                    logger.error("Secret({}.{}>) doesnot exist".format(workload.namespace.project,secret_name))
                else:
                    logger.error("Secret({}.{}>) doesnot exist".format(workload.namespace.cluster,secret_name))
                raise
            secretitem_qs = models.SecretItem.objects.filter(secret=secret)
            if prefix:
                secretitem_qs = secretitem_qs.filter(name__startswith=prefix)
            for item in secretitem_qs:
                if item.name in env_names:
                    #already declared in workload,ignore
                    continue
                updated = _save_env(workload,item.name,item.value,secret,item) or updated

    #update env from configmap volume
    for volume in models.WorkloadVolume.objects.filter(volume_claim__isnull=True,volume__isnull=True,volumepath__isnull=True):
        if "configMap" not in volume.other_config or not volume.other_config["configMap"].get("name"):
            continue
        configmap = models.ConfigMap.objects.filter(cluster=workload.cluster,namespace=workload.namespace,name=volume.other_config["configMap"]["name"]).first()
        if not configmap:
            continue
        for configitem in models.ConfigMapItem.objects.filter(configmap=configmap):
            value = configitem.value
            if not value:
                continue
            value = value.strip()
            if not value:
                continue

            for line in value.splitlines():
                line = line.strip()
                if not line:
                    continue
                datas = line.split("=",1)
                if len(datas) != 2:
                    continue
                k,v = datas
                k = k.strip()
                v = v.strip()
                if not env_var_re.search(k):
                    continue

                updated = _save_env(workload,k,v,configmap,configitem) or updated

    del_objs = models.WorkloadEnv.objects.filter(workload=workload).exclude(id__in=env_ids).delete()
    if del_objs[0]:
        logger.debug("Delete the envs for workload({}),deleted objects = {}".format(workload,del_objs))
        updated = True
    return updated

def update_workload_listenings(workload,config):
    """
    Return True if some env is updated;otherwise return False
    """
    #get listen config from public endpoints
    listen_configs = get_property(config,("metadata","annotations","field.cattle.io/publicEndpoints"),lambda val: json.loads(val) if val else None)
    if listen_configs:
        #if serviceName is not provided(daemonset has not serviceName in its listen config), populate one.
        for listen_config in listen_configs:
            if "serviceName" not in listen_config:
                listen_config["serviceName"] = "{0}:{2}({1})".format(workload.namespace.name,listen_config["protocol"].lower(),listen_config["port"])
    else:
        #if can't get the listen config from public endpoints, try to find them in specification
        listen_configs = []
        for port_config in get_property(config,("spec","template","spec",'containers',0,"ports")) or []:
            listen_configs.append({
                "serviceName":"{0}:{2}({1})".format(workload.namespace.name,port_config.get("protocol","").lower(),port_config.get("containerPort",0)),
                "port":int(port_config.get("containerPort",0)),
                "protocol":port_config.get("protocol","").lower()
            })
        if not listen_configs:
            del_objs = models.WorkloadListening.objects.filter(workload=workload).delete()
            if del_objs[0]:
                logger.debug("Delete the listenings for workload({}),deleted objects = {}".format(workload,del_objs))
                return True
            else:
                return False

    updated = False
    name = None

    listen_ids = []
    for listen_config in listen_configs:
        servicename = listen_config["serviceName"]
        if "ingressName" in listen_config:
            #ingress router
            ingress_namespace,ingressname = listen_config["ingressName"].split(":")
            try:
                ingress_namespace = models.Namespace.objects.get(cluster=workload.cluster,name=ingress_namespace)
            except:
                logger.error("Namespace({}.{}) does not exist".format(workload.cluster,ingress_namespace))
                raise

            ingress = models.Ingress.objects.get(cluster=workload.cluster,namespace=ingress_namespace,name=ingressname)
            ingress_rule = models.IngressRule.objects.get(ingress=ingress,servicename=listen_config["serviceName"])
            try:
                obj = models.WorkloadListening.objects.get(workload=workload,servicename=servicename,ingress_rule=ingress_rule)
            except ObjectDoesNotExist as ex:
                obj = models.WorkloadListening(workload=workload,servicename=servicename,ingress_rule=ingress_rule)
        else:
            ingress_rule = None
            try:
                obj = models.WorkloadListening.objects.get(workload=workload,servicename=servicename,ingress_rule__isnull=True)
            except ObjectDoesNotExist as ex:
                obj = models.WorkloadListening(workload=workload,servicename=servicename,ingress_rule=None)

        update_fields = set_fields_from_config(obj,listen_config,[
            ("servicename","serviceName",None),
            ("listen_port","port",lambda val:int(val)),
            ("protocol","protocol",lambda val: val.lower() if val else None),
        ])

        #try to find the ingressName or container port
        if ingress_rule:
            #ingress router
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
                raise Exception("Failed to find the container port of the public port({}.{})".format(workload,obj.listen_port))
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
            update_fields.append("updated")
            obj.save(update_fields=update_fields)
            updated = True
            logger.debug("Update the workload listening({}),update_fields={}".format(obj,update_fields))
        else:
            logger.debug("The workload listening({}) is not changed".format(obj))
        listen_ids.append(obj.id)

    # remove the not deleted listenings from db
    del_objs = models.WorkloadListening.objects.filter(workload=workload).exclude(id__in=listen_ids).delete()
    if del_objs[0]:
        logger.debug("Delete the listenings for workload({}),deleted objects = {}".format(workload,del_objs))
        updated = True

    return updated


def update_workload_volumes(workload,config,spec_config):
    """
    Return True if some env is updated;otherwise return False
    """
    volumemount_configs = get_property(spec_config,("containers",0,"volumeMounts"))
    if not volumemount_configs:
        del_objs = models.WorkloadVolume.objects.filter(workload=workload).delete()
        if del_objs[0]:
            logger.debug("Delete the volumes for workload({}),deleted objects = {}".format(workload,del_objs))
            return True
        else:
            return False

    updated = False
    name = None
    del_objs = models.WorkloadVolume.objects.filter(workload=workload).exclude(name__in=[c["name"] for c in volumemount_configs]).delete()
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
            obj = models.WorkloadVolume.objects.get(workload=workload,name=name)
        except ObjectDoesNotExist as ex:
            obj = models.WorkloadVolume(workload=workload,name=name)

        writable = get_property(volumemount_config,"readOnly",lambda val: False if val else True)
        update_fields = set_fields_from_config(obj,volumemount_config,[
            ("mountpath","mountPath",None),
            ("subpath","subPath",None)
        ])
        if name not in volume_configs:
            continue
        volume_config = volume_configs[name]
        if "persistentVolumeClaim" in volume_config:
            #reference the volume from volume claim
            claimname = volume_config["persistentVolumeClaim"]["claimName"]
            set_field(obj,"volume_claim", models.PersistentVolumeClaim.objects.get(cluster=workload.cluster,namespace=workload.namespace,name=claimname),update_fields)
            set_field(obj,"volume", obj.volume_claim.volume,update_fields)
            set_field(obj,"volumepath", obj.volume_claim.volume.volumepath if obj.volume_claim.volume else None ,update_fields)
            set_field(obj,"other_config", None,update_fields)
            if writable:
                writable = obj.volume_claim.writable
        elif "hostPath" in volume_config:
            hostpath = volume_config["hostPath"]["path"]
            set_field(obj,"volume_claim", None,update_fields)
            set_field(obj,"volumepath", hostpath,update_fields)
            set_field(obj,"volume", models.PersistentVolume.objects.filter(cluster=workload.cluster,volumepath=hostpath).first(),update_fields)
            set_field(obj,"other_config", None,update_fields)
            if writable and obj.volume:
                writable = obj.volume.writable
        else:
            set_field(obj,"other_config", volume_config,update_fields)

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
            update_fields.append("updated")
            obj.save(update_fields=update_fields)
            updated = True
            logger.debug("Update the deployment workload volume({}),update_fields={}".format(obj,update_fields))
        else:
            logger.debug("The deployment workload volume({}) is not changed".format(obj))
    return updated

def update_deployment(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    kind = get_property(config,"kind")
    imageid = get_property(config,("spec","template","spec","containers",0,"image"))
    image = models.ContainerImage.parse_imageid(imageid,scan=True)

    try:
        obj = models.Workload.objects.get(cluster=cluster,namespace=namespace,name=name,kind=kind)
    except ObjectDoesNotExist as ex:
        obj = models.Workload(cluster=cluster,namespace=namespace,name=name,kind=kind)
    update_fields = set_fields_from_config(obj,config,[
        ("deleted",None,lambda obj:None),
        ("added_by_log",None,lambda obj:False),
        ("api_version","apiVersion",None),
        ("project",None,lambda val:namespace.project),
        ("modified",[("spec","template","metadata","annotations","cattle.io/timestamp"),("metadata","creationTimestamp")],lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("replicas",("spec","replicas"),lambda val:int(val) if val else 0),
        ("containerimage",None,lambda obj:image),
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

    #update listenings
    updated = update_workload_listenings(obj,config)

    #update volumes
    updated = update_workload_volumes(obj,config,get_property(config,("spec","template","spec"))) or updated

    #update envs
    updated = update_workload_envs(obj,config,get_property(config,("spec","template","spec","containers",0,"env")),get_property(config,("spec","template","spec","containers",0,"envFrom"))) or updated

    if created:
        pass
    elif update_fields or updated:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update the deployment workload({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The deployment workload({}) is not changed".format(obj))

    return obj

def delete_deployment(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    kind = config["kind"]
    obj = models.Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically delete the deployment workload({2}:{0}.{1})".format(namespace,name,kind))

    return obj

def update_cronjob(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    kind = get_property(config,"kind")
    imageid = get_property(config,("spec","jobTemplate","spec","template","spec","containers",0,"image"))
    image = models.ContainerImage.parse_imageid(imageid,scan=True)
    try:
        obj = models.Workload.objects.get(cluster=cluster,namespace=namespace,name=name,kind=kind)
    except ObjectDoesNotExist as ex:
        obj = models.Workload(cluster=cluster,namespace=namespace,name=name,kind=kind)

    update_fields = set_fields_from_config(obj,config,[
        ("deleted",None,lambda obj:None),
        ("added_by_log",None,lambda obj:False),
        ("api_version","apiVersion",None),
        ("project",None,lambda val:namespace.project),
        ("modified",[("spec","jobTemplate","spec","template","metadata","annotations","cattle.io/timestamp"),("metadata","creationTimestamp")],lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("containerimage",None,lambda obj:image),
        ("image",("spec","jobTemplate","spec","template","spec","containers",0,"image"),None),
        ("image_pullpolicy",("spec","jobTemplate","spec","template","spec","containers",0,"imagePullPolicy"),None),
        ("replicas",None,lambda val:0),
        ("cmd",("spec","jobTemplate","spec","template","spec","containers",0,"args"), lambda val:json.dumps(val) if val else None),
        ("schedule",("spec","schedule"), None),
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

    #delete all listening objects
    updated = update_workload_listenings(obj,config)

    #update volumes
    updated = update_workload_volumes(obj,config,get_property(config,("spec","jobTemplate","spec","template","spec"))) or updated

    #update envs
    updated = update_workload_envs(obj,config,get_property(config,("spec","jobTemplate","spec","template","spec","containers",0,"env")),get_property(config,("spec","jobTemplate","spec","template","spec","containers",0,"envFrom"))) or updated

    if created:
        pass
    elif update_fields or updated:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update the cronjob workload({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The cronjob workload({}) is not changed".format(obj))

    return obj

def delete_cronjob(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    kind = config["kind"]
    obj = models.Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically delete the cronjob workload({2}:{0}.{1})".format(namespace,name,kind))

    return obj

def update_daemonset(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    kind = get_property(config,"kind")
    imageid = get_property(config,("spec","template","spec","containers",0,"image"))
    image = models.ContainerImage.parse_imageid(imageid,scan=True)

    try:
        obj = models.Workload.objects.get(cluster=cluster,namespace=namespace,name=name,kind=kind)
    except ObjectDoesNotExist as ex:
        obj = models.Workload(cluster=cluster,namespace=namespace,name=name,kind=kind)

    update_fields = set_fields_from_config(obj,config,[
        ("deleted",None,lambda obj:None),
        ("added_by_log",None,lambda obj:False),
        ("api_version","apiVersion",None),
        ("kind","kind",None),
        ("project",None,lambda val:namespace.project),
        ("modified",[("spec","template","metadata","annotations","cattle.io/timestamp"),("metadata","creationTimestamp")],lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("containerimage",None,lambda obj:image),
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
        logger.debug("Create daemonset workload({})".format(obj))

    #delete all listening objects
    updated = update_workload_listenings(obj,config)

    #update volumes
    updated = update_workload_volumes(obj,config,get_property(config,("spec","template","spec"))) or updated

    #update envs
    updated = update_workload_envs(obj,config,get_property(config,("spec","template","spec","containers",0,"env")),get_property(config,("spec","template","spec","containers",0,"envFrom"))) or updated

    if created:
        pass
    elif update_fields or updated:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update the daemon workload({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The daemon workload({}) is not changed".format(obj))

    return obj

def delete_daemonset(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    kind = config["kind"]
    obj = models.Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically delete the daemonset workload({2}:{0}.{1})".format(namespace,name,kind))

    return obj

def update_statefulset(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    kind = get_property(config,"kind")
    imageid = get_property(config,("spec","template","spec","containers",0,"image"))
    image = models.ContainerImage.parse_imageid(imageid,scan=True)

    try:
        obj = models.Workload.objects.get(cluster=cluster,namespace=namespace,name=name,kind=kind)
    except ObjectDoesNotExist as ex:
        obj = models.Workload(cluster=cluster,namespace=namespace,name=name,kind=kind)

    update_fields = set_fields_from_config(obj,config,[
        ("deleted",None,lambda obj:None),
        ("added_by_log",None,lambda obj:False),
        ("api_version","apiVersion",None),
        ("project",None,lambda val:namespace.project),
        ("kind","kind",None),
        ("modified",[("spec","template","metadata","annotations","cattle.io/timestamp"),("metadata","creationTimestamp")],lambda dtstr:timezone.localtime(datetime.strptime(dtstr,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.timezone(offset=timedelta(hours=0)))) ),
        ("containerimage",None,lambda obj:image),
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

    #update listenings
    updated = update_workload_listenings(obj,config)

    #update volumes
    updated = update_workload_volumes(obj,config,get_property(config,("spec","template","spec"))) or updated

    #update envs
    updated = update_workload_envs(obj,config,get_property(config,("spec","template","spec","containers",0,"env")),get_property(config,("spec","template","spec","containers",0,"envFrom"))) or updated

    #update database server if it is a database server
    image_name_lower = obj.image.lower()
    if created:
        pass
    elif update_fields or updated:
        update_fields.append("updated")
        obj.save(update_fields=update_fields)
        logger.debug("Update the statefulset workload({}),update_fields={}".format(obj,update_fields))
    else:
        logger.debug("The statefulset workload({}) is not changed".format(obj))

    return obj

def delete_statefulset(cluster,status,metadata,config):
    namespace = config["metadata"]["namespace"]
    try:
        namespace = models.Namespace.objects.get(cluster=cluster,name=namespace)
    except:
        logger.error("Namespace({}.{}) does not exist".format(cluster,namespace))
        raise

    name = config["metadata"]["name"]
    kind = config["kind"]
    obj = models.Workload.objects.filter(cluster=cluster,namespace=namespace,name=name,kind=kind).first()
    if obj:
        obj.logically_delete()
        logger.info("Logically delete the statefulset workload({2}:{0}.{1})".format(namespace,name,kind))

    return obj

process_func_map = {
    10:(models.Namespace,update_namespace,0),
    13:(models.Secret,update_secret,3),
    15:(models.ConfigMap,update_configmap,4),
    20:(models.PersistentVolume,update_volume,1),
    30:(models.PersistentVolumeClaim,update_volume_claim,2),
    40:(models.Ingress,update_ingress,5),
    50:(models.Workload,update_deployment,6),
    60:(models.Workload,update_statefulset,6),
    70:(models.Workload,update_cronjob,6),
    75:(models.Workload,update_daemonset,6),
    80:(models.Workload,delete_cronjob,6),
    85:(models.Workload,delete_daemonset,6),
    90:(models.Workload,delete_statefulset,6),
    100:(models.Workload,delete_deployment,6),
    110:(models.Ingress,delete_ingress,5),
    120:(models.PersistentVolumeClaim,delete_volume_claim,2),
    130:(models.PersistentVolume,delete_volume,1),
    135:(models.ConfigMap,delete_configmap,4),
    137:(models.Secret,delete_secret,3),
    140:(models.Namespace,delete_namespace,0)
}

def resource_type(status,resource_id):
    if status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and NAMESPACE_RE.search(resource_id):
        return 10
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and SECRET_RE.search(resource_id):
        return 13
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and CONFIGMAP_RE.search(resource_id):
        return 15
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and VOLUMN_RE.search(resource_id):
        return 20
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and VOLUMN_CLAIM_RE.search(resource_id):
        return 30
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and INGRESS_RE.search(resource_id):
        return 40
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and DEPLOYMENT_RE.search(resource_id):
        return 50
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and STATEFULSET_RE.search(resource_id):
        return 60
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and CRONJOB_RE.search(resource_id):
        return 70
    elif status in (ResourceConsumeClient.NEW,ResourceConsumeClient.UPDATED,ResourceConsumeClient.NOT_CHANGED) and DAEMONSET_RE.search(resource_id):
        return 75
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and CRONJOB_RE.search(resource_id):
        return 80
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and DAEMONSET_RE.search(resource_id):
        return 85
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and STATEFULSET_RE.search(resource_id):
        return 90
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and DEPLOYMENT_RE.search(resource_id):
        return 100
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and INGRESS_RE.search(resource_id):
        return 110
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and VOLUMN_CLAIM_RE.search(resource_id):
        return 120
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and VOLUMN_RE.search(resource_id):
        return 130
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and CONFIGMAP_RE.search(resource_id):
        return 135
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and SECRET_RE.search(resource_id):
        return 137
    elif status in (ResourceConsumeClient.LOGICALLY_DELETED,ResourceConsumeClient.PHYSICALLY_DELETED) and NAMESPACE_RE.search(resource_id):
        return 140
    else:
        raise Exception("Not Support. status={}, resource_id={}".format(status,resource_id))

def sort_key(val):
    return resource_type(val[0],val[1][0])


def process_rancher(cluster,f_renew_lock,process_status):
    def _func(status,metadata,config_file):
        model_class,process_func,model_priority = process_func_map[resource_type(status,metadata["resource_id"])]
        if process_status is not None and process_status[model_priority] is None:
            process_status[model_priority] = [model_class,[],set()]
        try:
            if config_file:
                with open(config_file) as f:
                    config = yaml.load(f.read(),Loader=yaml.FullLoader)
                with transaction.atomic():
                    obj = process_func(cluster,status,metadata,config)
                    if obj and process_status is not None:
                        process_status[model_priority][2].add(obj.id)
            f_renew_lock()
        except Exception as ex:
            if process_status is not None:
                process_status[model_priority][1].append(str(ex))
            raise
        except :
            if process_status is not None:
                process_status[model_priority][1].append(traceback.format_exc())
            raise

    return _func

def resource_filter(resource_id):
    return True if RANCHER_FILE_RE.search(resource_id) else False

def _harvest(cluster,f_renew_lock,reconsume=False,lock_exception=None):
    harvest_result = [None,False]

    client = get_client(cluster.name)
    if not reconsume:
        now = timezone.localtime()
        client_consume_status = client.consume_status
        if "next_reconsume_time" in client_consume_status:
            reconsume_time = timezone.localtime(client_consume_status["next_reconsume_time"])
            if reconsume_time and now.weekday() == 6  and now.hours <=6 and now >= reconsume_time:
                #now is eraly morning  in Sunday, and also sync is requested but not executed.
                reconsume = True

    process_status = [None for i in range(7)] if reconsume else None

    def _post_consume(client_consume_status,consume_result):
        now = timezone.localtime()
        if "next_clean_time" not in client_consume_status:
            client_consume_status["next_clean_time"] = timezone.make_aware(datetime(now.year,now.month,now.day)) + timedelta(days=1)
        elif now.hour > 6:
            pass
        elif now >= client_consume_status["next_clean_time"]:
            harvest_result[1] = True
            client_consume_status["next_clean_time"] = timezone.make_aware(datetime(now.year,now.month,now.day)) + timedelta(days=1)


        if  "next_reconsume_time" not in client_consume_status or now > client_consume_status["next_reconsume_time"]:
            if now.weekday() == 6:
                next_reconsume_time = timezone.make_aware(datetime(now.year,now.month,now.day)) + timedelta(days=7)
            else:
                next_reconsume_time = timezone.make_aware(datetime(now.year,now.month,now.day)) + timedelta(days=6 - now.weekday())
            client_consume_status["next_reconsume_time"] = next_reconsume_time

    now = timezone.now()
    harvester = models.Harvester(name=harvestername.format(cluster.name),starttime=now,last_heartbeat=now,status=models.Harvester.RUNNING)
    harvester.save()
    message = None
    try:
        if isinstance(cluster,models.Cluster):
            pass
        elif isinstance(cluster,int):
            cluster = models.Cluster.objects.get(id=cluster)
        else:
            cluster = models.Cluster.objects.get(name=cluster)
        if cluster.added_by_log:
            message = "The cluster({}) was created by log. no configuration to harvest".format(cluster.name)
            harvester.status = models.Harvester.SKIPPED
            harvest_result[0] = ([],[])
            return harvest_result

        try:
            #try to get the lock here and relase the lock at the end
            if lock_exception:
                raise lock_exception
            now = timezone.now()
            result = client.consume(process_rancher(cluster,f_renew_lock,process_status),reconsume=reconsume,resources=resource_filter,sortkey_func=sort_key,stop_if_failed=False,f_post_consume=_post_consume)
            if reconsume:
                process_status.reverse()
                for model_class,process_msgs,objids in process_status:
                    if process_msgs:
                        logger.error("Ignore the process to clean the objects which don't exist in rancher anymore because some exceptions occur during havesting the configuration of {}.\n\t{}".format(model_class,"\n\t".join(process_msgs)))
                        break
                    for obj in model_class.objects.filter(cluster=cluster,deleted__isnull=True).exclude(id__in=objids).only("name"):
                        logger.debug("Logically delete the {0}({1}<{2}>)".format(model_class.__name__,obj.name,obj.id))
                        obj.logically_delete()
                    f_renew_lock()

            cluster.updated = timezone.now()
            if result[1]:
                if result[0]:
                    message = """Failed to refresh cluster({}),
    {} configuration files were consumed successfully.
    {}
    {} configuration files were failed to consume
    {}"""
                    message = message.format(
                        cluster.name,
                        len(result[0]),
                        "\n        ".join(["Succeed to harvest {} resource '{}'".format(resource_status_name,resource_ids) for resource_status,resource_status_name,resource_ids in result[0]]),
                        len(result[1]),
                        "\n        ".join(["Failed to harvest {} resource '{}'.{}".format(resource_status_name,resource_ids,msg) for resource_status,resource_status_name,resource_ids,msg in result[1]])
                    )
                else:
                    message = """Failed to refresh cluster({}),{} configuration files were failed to consume
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

            harvester.status = models.Harvester.FAILED if result[1] else models.Harvester.SUCCEED

            if len(result[0]) or len(result[1]):
                cluster.added_by_log = False
                cluster.save(update_fields=["added_by_log"])
            harvest_result[0] = result
            return harvest_result
        except exceptions.AlreadyLocked as ex:
            harvester.status = models.Harvester.SKIPPED
            message = "The previous harvest process is still running.{}".format(str(ex))
            logger.warning(message)
            harvest_result[0] = ([],[(None,None,None,message)])
            return harvest_result
    except :
        harvester.status = models.Harvester.FAILED
        message = "Failed to harvest rancher configuration.{}".format(traceback.format_exc())
        logger.info(message)
        harvest_result[0] = ([],[(None,None,None,message)])
        return harvest_result

    finally:
        #logger.debug("Begin to refresh rancher workload in web app locaion")
        harvester.message = message
        harvester.endtime = timezone.now()
        harvester.last_heartbeat = harvester.endtime
        harvester.save(update_fields=["endtime","message","status","last_heartbeat"])

def harvest(cluster,reconsume=False):
    lock_session = LockSession(get_client(cluster.name),3000,1500)
    def _renew_locks():
        lock_session.renew_if_needed()

    try:
        harvest_result = _harvest(cluster,_renew_locks,reconsume=reconsume)

        return harvest_result[0]
    finally:
        lock_session.release()


def harvest_all(reconsume=False):
    consume_results = []
    now = timezone.now()
    need_clean = False
    lock_sessions = {}

    def _renew_locks():
        for cluster,lock_session in lock_sessions.items():
            lock_session.renew_if_needed()
    try:
        lock_exception = None

        #try to acquire the lock for all clusters before processing
        for cluster in models.Cluster.objects.filter(added_by_log=False):
            try:
                lock_session = LockSession(get_client(cluster.name),3000,1500)
                lock_sessions[cluster] = lock_session
            except exceptions.AlreadyLocked as ex:
                #can't acquire one cluster's lock. and quit the process
                lock_exception = ex
                break

        #harvest the changed configurations
        for cluster in models.Cluster.objects.filter(added_by_log=False):
            harvest_result = _harvest(cluster,_renew_locks,reconsume=reconsume,lock_exception=lock_exception)
            if harvest_result[1]:
                need_clean = True
            consume_results.append((cluster,harvest_result[0]))

        if lock_exception:
            #found lock exception, quit the process
            return consume_results

        if need_clean:
            for func in (
                modeldata.clean_expired_deleted_data,
                modeldata.clean_orphan_projects,
                modeldata.clean_orphan_namespaces,
                modeldata.check_aborted_harvester,
                modeldata.clean_expired_harvester,
                modeldata.clean_unused_oss,
                modeldata.clean_unreferenced_vulnerabilities,
                modeldata.clean_unreferenced_images,
            ):
                try:
                    func()
                except:
                    logger.error("Failed to call method({}) to clean data.{}".format(func,traceback.format_exc()))
                _renew_locks()

        #sync dependent tree
        scan_module = models.EnvScanModule.objects.filter(active=True).order_by("-modified").defer("sourcecode").first()
        wl = models.Workload.objects.all().order_by("-resource_scaned").first()
        if scan_module and wl and (not wl.resource_scaned or not scan_module.modified or (wl.resource_scaned < scan_module.modified)):
            modeldata.sync_dependent_tree(rescan=False,cluster_lock_sessions=lock_sessions.items())
        else:
            modeldata.sync_dependent_tree(workload_changetime=now,rescan=False,cluster_lock_sessions=lock_sessions.items())
        #set workload's itsystem
        if need_clean:
            modeldata.set_workload_itsystem()

        return consume_results
    finally:
        #release the locks
        for cluster,lock_session in lock_sessions.items():
            try:
                lock_session.release()
            except Exception as ex:
                logger.error("Failed to release the lock.{}".format(str(ex)))


