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

from .podstatus_harvester import get_podstatus_client
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

def update_latest_containers(context,container,workload=None,workload_update_fields=None):
    if workload is None:
        workload_key = (container.workload.cluster.id,container.workload.namespace.name,container.workload.name,container.workload.kind)
        if workload_key not in context["workloads"]:
            workload_update_fields = []
            workload = container.workload
            context["workloads"][workload_key] = (workload,workload_update_fields)
        else:
            workload,workload_update_fields = context["workloads"][workload_key]

    if container.container_terminated and (container.container_terminated.date() < timezone.now().date() or (workload.deleted and workload.deleted < container.container_terminated)):
        workload.deleted = container.container_terminated
        if "deleted" not in workload_update_fields:
            workload_update_fields.append("deleted")

    if workload.kind in ("Deployment",'DaemonSet','StatefulSet','service?'):
        if container.status in ("Waiting","Running"):
            if workload.latest_containers is None:
                workload.latest_containers=[[container.id,1,0]]
                if "latest_containers" not in workload_update_fields:
                    workload_update_fields.append("latest_containers")
            elif any(obj for obj in workload.latest_containers if obj[0] == container.id):
                pass
            else:
                workload.latest_containers.append([container.id,1,0])
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
                workload.latest_containers=[[container.id,1,0]]
            else:
                workload.latest_containers=[[container.id,0,0]]
            if "latest_containers" not in workload_update_fields:
                workload_update_fields.append("latest_containers")
        else:
            if container.status in ("Waiting","Running"):
                workload.latest_containers[0][1]=1
            else:
                workload.latest_containers[0][1]=0
            if "latest_containers" not in workload_update_fields:
                workload_update_fields.append("latest_containers")

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
            if finished:
                containerstate = "terminated"
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
            
            workload = None
            key = (cluster.id,containerid)
            if key in context["terminated_containers"]:
                continue
            elif key in context["containers"]:
                container = context["containers"][key]
            else:
                try:
                    container = Container.objects.get(cluster=cluster,containerid=containerid)
                    context["containers"][key] = container
                except ObjectDoesNotExist as ex:
                    pass

            if container:
                workload_key = (container.workload.cluster.id,container.workload.namespace.name,container.workload.name,container.workload.kind)
                if workload_key not in context["workloads"]:
                    workload_update_fields = []
                    workload = container.workload
                    context["workloads"][workload_key] = (workload,workload_update_fields)
                else:
                    workload,workload_update_fields = context["workloads"][workload_key]

            else:
                kind = "service?" if ports else "jobs?"
                new_workload_name = "{}-{}".format(image_without_tag,workload_name)
                workload_key = (cluster.id,"unknown",new_workload_name,kind)
                workload = None
                if workload_key in context["workloads"]:
                    workload,workload_update_fields = context["workloads"][workload_key]
                else:
                    #try to find the workload through cluster and workload name
                    workload_qs = Workload.objects.filter(cluster=cluster,name=workload_name)
                    for obj in workload_qs:
                        if obj.image.startswith(image_without_tag) and ((ports and obj.listenings.all().count()) or (not ports and obj.listenings.all().count() == 0)):
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

                        workload = Workload.objects.filter(cluster=cluster,namespace=namespace,name=new_workload_name,kind=kind).first()

                        if not workload:
                            image = "{}:{}".format(record["image"].strip(),record["imagetag"].strip())
                            workload = Workload(
                                cluster=namespace.cluster,
                                project=namespace.project,
                                namespace=namespace,
                                name=new_workload_name,
                                image=image,
                                kind=kind,
                                api_version="",
                                added_by_log=True,
                                modified=timezone.now(),
                                created=timezone.now()
                            )
                            #if finished and finished.date() < timezone.now().date():
                            #    workload.deleted = finished
                            workload.save()

                    workload_key = (cluster.id,workload.namespace.name,workload.name,workload.kind)
                    workload_update_fields = []
                    context["workloads"][workload_key] = (workload,workload_update_fields)

                container = Container(
                    cluster=workload.cluster,
                    namespace=workload.namespace,
                    workload=workload,
                    poduid = "",
                    containerid = containerid
                )
                context["containers"][key] = container

            #container
            container_status = get_container_status(container,containerstate)
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

            update_latest_containers(context,container,workload=workload,workload_update_fields=workload_update_fields)
            if container_status.lower() in ("deleted","terminated"):
                del context["containers"][key]
                context["terminated_containers"].add(key)

        except Exception as ex:
            #delete already added records from this log file
            logger.error("Failed to parse pod status record({}).{}".format(record,traceback.format_exc()))
            raise Exception("Failed to parse pod status record({}).{}".format(record,str(ex)))

    context["last_archive_time"] = metadata["archive_endtime"]
    logger.info("Harvest {1} records from file '{0}'".format(status_file,records))
            

def process_status(context,max_harvest_files):
    def _func(status,metadata,status_file):
        if max_harvest_files:
            if context["harvested_files"] >= max_harvest_files:
                raise Exception("Already harvested {} files".format(context["harvested_files"]))
            context["harvested_files"] += 1
            
        if status != HistoryDataConsumeClient.NEW:
            raise Exception("The status of the consumed history data shoule be New, but currently consumed histroy data's status is {},metadata={}".format(
                get_containerstatus_client().get_consume_status_name(status),
                metadata
            ))

        for key,client in (("podstatus_client",get_podstatus_client(cache=False)),):
            if key in context["clients"]:
                last_consume = context["clients"][key]
                if last_consume[1]["archive_endtime"] >= metadata["archive_endtime"]:
                    continue
            last_consume = client.last_consume
            if not last_consume or last_consume[1]["archive_endtime"] < metadata["archive_endtime"]:
                raise exceptions.StopConsuming("Can't consume containerstatus file({0}) which archive_endtime({1}) is after the archive_endtime({3}) of the last consumed podstatus file({2}) that was consumed at {4}".format(
                    metadata["resource_id"],
                    metadata["archive_endtime"],
                    last_consume[1]["resource_id"],
                    last_consume[1]["archive_endtime"],
                    last_consume[2]["consume_date"],
                ))
            context["clients"][key] = last_consume

        process_status_file(context,metadata,status_file)

        #save workload 
        for workload,workload_update_fields in context["workloads"].values():
            if workload_update_fields:
                workload.save(update_fields=workload_update_fields)
                workload_update_fields.clear()

        context["renew_lock_time"] = context["f_renew_lock"](context["renew_lock_time"])


    return _func
                        
def harvest(reconsume=False,max_harvest_files=None):
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
            "clients":{},
            "namespaces":{},
            "workloads":{},
            "containers":{},
            "terminated_containers":set()
        }
        if max_harvest_files:
            context["harvested_files"] = 0
        #consume nginx config file
        result = get_containerstatus_client().consume(process_status(context,max_harvest_files))
        #change the status of containers which has no status data harvested in recent half an hour
        if "last_archive_time" in context:
            for container in Container.objects.filter(status__in=("Waiting",'Running'),last_checked__lt=context["last_archive_time"] - datetime.timedelta(minutes=30)):
                container.status="LostHeartbeat"
                container.save(update_fields=["status"])
                update_latest_containers(context,container)

        #save workload 
        for workload,workload_update_fields in context["workloads"].values():
            if workload_update_fields:
                workload.save(update_fields=workload_update_fields)

        return result

    finally:
        get_containerstatus_client().release_lock()
        


