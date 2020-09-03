import os
import json
import simdjson
import traceback
import logging
import datetime
from collections import OrderedDict

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models,transaction
from django.utils import timezone
from django.http import QueryDict

from data_storage import HistoryDataConsumeClient,LocalStorage,exceptions
from .models import Cluster,Namespace,Workload,Container
from itassets.utils import LogRecordIterator

from .utils import to_datetime,set_fields,set_field

logger = logging.getLogger(__name__)

_containerstatus_client = None
def get_containerstatus_client(cache=True):
    """
    Return the blob resource client
    """
    global _containerstatus_client
    if _containerstatus_client is None:
        client = HistoryDataConsumeClient(
            LocalStorage(settings.CONTAINERSTATUS_REPOSITORY_DIR),
            settings.CONTAINERSTATUS_RESOURCE_NAME,
            settings.RESOURCE_CLIENTID,
            max_saved_consumed_resources=settings.CONTAINERSTATUS_MAX_SAVED_CONSUMED_RESOURCES
        )
        if cache:
            _containerstatus_client = client
        else:
            return client

    return _containerstatus_client

status_map = {
    "waiting":10,
    "running":20,
    "terminated":30,
    "deleted":40
}

def get_container_status(container,status):
    if not container.status:
        return status

    if status_map.get(container.status.lower(),0) < status_map.get(status.lower(),0):
        return status
    else:
        return container.status

def process_status_file(context,metadata,status_file):
    if settings.CONTAINERSTATUS_STREAMING_PARSE:
        status_records = LogRecordIterator(status_file)
    else:
        with open(status_file,"r") as f:
            status_records = simdjson.loads(f.read())

    records = 0
    for record in status_records:
        records += 1
        try:
            if any(not (record.get(key) or "").strip() for key in ("computer","containerid","image","name")):
                #data is incomplete,ignore
                continue
            
            created = to_datetime(record["created"])
            started = to_datetime(record["started"])
            finished = to_datetime(record.get("finished"))
            containerid = record["containerid"]
            ports = record["ports"] or None
            containerstate = record["containerstate"]
            envs = os.linesep.join(json.loads(record["environmentvar"])) if record["environmentvar"] else None
            exitcode = str(record["exitcode"]) if finished else None
            computer = record["computer"].strip()
            workload_name = record["name"].strip()
            image_without_tag = record.get("image","").strip()
            if not image_without_tag:
                continue
            else:
                image = "{}:{}".format(image_without_tag,record["imagetag"].strip())
            cluster = None
            clustername = None
            if computer in context["clusters"]:
                cluster = context["clusters"][computer]
            elif record.get("resourceid"):
                resourceid = record["resourceid"].strip().rsplit("/",1)[-1]
                if resourceid in context["clusters"]:
                    cluster = context["clusters"][resourceid]
                else:
                    clustername = resourceid
            else:
                clustername = computer

            if not cluster:
                try:
                    cluster = Cluster.objects.get(name=clustername)
                except ObjectDoesNotExist as ex:
                    cluster = Cluster(name=clustername,added_by_log=True)
                    cluster.save()

                context["clusters"][clustername] = cluster

            key = (cluster.id,containerid)
            if key in context["terminated_containers"]:
                continue
            elif key in context["containers"]:
                container = context["containers"][key]
            else:
                try:
                    container = Container.objects.get(cluster=cluster,containerid=containerid)
                except ObjectDoesNotExist as ex:
                    kind = "service?" if ports else "jobs?"
                    workload_key = (cluster.id,workload_name,kind)
                    workload = None
                    if workload_key in context["workloads"]:
                        workload = context["workloads"][workload_key]
                    else:
                        #try to find the workload through cluster and workload name
                        workload_qs = Workload.objects.filter(cluster=cluster,name=workload_name)
                        for obj in workload_qs:
                            if obj.image.startswith(image_without_tag) and ((kind == obj.kind) or (ports and obj.listenings.all().count()) or (not ports and obj.listenings.all().count() == 0)):
                                workload = obj
                                break
                    if not workload:
                        #not found , create a workload for this log
                        namespace_key = (cluster.id,"unknown")
                        if namespace_key in context["namespaces"]:
                            namespace = context["namespaces"][namespace_key]
                        else:
                            try:
                                namespace = Namespace.objects.get(cluster=cluster,name="unknown")
                            except ObjectDoesNotExist as ex:
                                namespace = Namespace(cluster=cluster,name="unknown",added_by_log=True)
                                namespace.save()
    
                            context["namespaces"][namespace_key] = namespace
    
                        image = "{}:{}".format(record["image"].strip(),record["imagetag"].strip())
                        workload = Workload(
                            cluster=namespace.cluster,
                            project=namespace.project,
                            namespace=namespace,
                            name=workload_name,
                            image=image,
                            kind=kind,
                            api_version="",
                            added_by_log=True,
                            modified=timezone.now(),
                            created=timezone.now()
                        )
                        workload.save()
                    context["workloads"][workload_key] = workload

                    container = Container(
                        cluster=workload.cluster,
                        namespace=workload.namespace,
                        workload=workload,
                        poduid = "",
                        containerid = containerid
                        )
                context["containers"][key] = container

            #container
            container_status = get_container_status(container,record["containerstate"])
            update_fields = set_fields(container,[
                ("exitcode",exitcode or container.exitcode),
                ("image",image or container.image),
                ("ports",ports or container.ports),
                ("envs",envs or container.envs),
                ("container_created",created or container.container_created),
                ("container_started",started or container.container_started),
                ("container_terminated",finished or container.container_terminated),
                ("status",container_status),
                ("last_checked",to_datetime(record["max_timegenerated"]))
            ])

            if container.pk is None:
                container.save()
            elif update_fields:
                container.save(update_fields=update_fields)

            if container_status.lower() in ("deleted","terminated"):
                del context["containers"][key]
                context["terminated_containers"].add(key)

        except Exception as ex:
            #delete already added records from this log file
            logger.error("Failed to parse pod status record({}).{}".format(record,traceback.format_exc()))
            raise Exception("Failed to parse pod status record({}).{}".format(record,str(ex)))

    logger.info("Harvest {1} records from file '{0}'".format(status_file,records))
            

def process_status(context):
    def _func(status,metadata,status_file):
        if status != HistoryDataConsumeClient.NEW:
            raise Exception("The status of the consumed history data shoule be New, but currently consumed histroy data's status is {},metadata={}".format(
                get_containerstatus_client().get_consume_status_name(status),
                metadata
            ))
        process_status_file(context,metadata,status_file)

        context["renew_lock_time"] = context["f_renew_lock"](context["renew_lock_time"])

    return _func
                        
def harvest(reconsume=False):
    try:
        renew_lock_time = get_containerstatus_client().acquire_lock(expired=settings.CONTAINERSTATUS_MAX_CONSUME_TIME_PER_LOG)
    except exceptions.AlreadyLocked as ex: 
        msg = "The previous harvest process is still running.{}".format(str(ex))
        logger.info(msg)
        return ([],[(None,None,None,msg)])
        
    try:
        if reconsume and get_containerstatus_client().is_client_exist(clientid=settings.RESOURCE_CLIENTID):
            get_containerstatus_client().delete_clients(clientid=settings.RESOURCE_CLIENTID)
    
        context = {
            "reconsume":reconsume,
            "renew_lock_time":renew_lock_time,
            "f_renew_lock":get_containerstatus_client().renew_lock,
            "clusters":{},
            "namespaces":{},
            "workloads":{},
            "containers":{},
            "terminated_containers":set()
        }
        #consume nginx config file
        result = get_containerstatus_client().consume(process_status(context))
        return result

    finally:
        get_containerstatus_client().release_lock()
        


