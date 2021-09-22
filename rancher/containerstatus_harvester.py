import os
import json
import simdjson
import traceback
import logging
from datetime import datetime,timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from data_storage import HistoryDataConsumeClient,LocalStorage,exceptions,LockSession
from . import models 
from itassets.utils import LogRecordIterator

from . import podstatus_harvester 
from .utils import to_datetime,set_fields
from . import modeldata

logger = logging.getLogger(__name__)
_containerstatus_client = None


harvestername = "containerstatus"

def get_client(cache=True):
    """
    Return the blob resource client
    """
    global _containerstatus_client
    if _containerstatus_client is None or not cache:
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
    "lostheartbeat":25,
    "shouldterminated":28,
    "terminated":30,
    "deleted":40
}

def get_container_status(container,status):
    status = status.lower()
    if not container.status:
        return status

    if status_map.get(container.status,0) < status_map.get(status,0):
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
    """
    if container.container_terminated and workload.deleted and workload.deleted < container.container_terminated:
        workload.deleted = container.container_terminated
        if "deleted" not in workload_update_fields:
            workload_update_fields.append("deleted")
    """

    if workload.kind in ("Deployment",'DaemonSet','StatefulSet','service?'):
        if container.status in ("waiting","running"):
            if workload.latest_containers is None:
                workload.latest_containers=[[container.id,1,0]]
                if "latest_containers" not in workload_update_fields:
                    workload_update_fields.append("latest_containers")
            else:
                index = len(workload.latest_containers) - 1
                found = False
                while index >= 0:
                    if workload.latest_containers[index][0] == container.id:
                        found = True
                        break
                    elif workload.latest_containers[index][0] < container.id:
                        break
                    else:
                        index -= 1
                if not found:
                    workload.latest_containers.insert(index + 1,[container.id,1,0])
                    if "latest_containers" not in workload_update_fields:
                        workload_update_fields.append("latest_containers")
        elif workload.latest_containers :
            index = len(workload.latest_containers) - 1
            while index >= 0:
                if workload.latest_containers[index][0] == container.id:
                    del workload.latest_containers[index]
                    if not workload.latest_containers:
                        workload.latest_containers = None
                    if "latest_containers" not in workload_update_fields:
                        workload_update_fields.append("latest_containers")
                    break
                else:
                    index -= 1
    else:
        #remove the terminated container first
        index = 0
        changed = False
        workload.latest_containers = workload.latest_containers if workload.latest_containers is not None else []
        while index <= len(workload.latest_containers):
            if index == len(workload.latest_containers):
                if container.status in ("waiting","running"):
                    workload.latest_containers.append([container.id,1,0]) 
                else:
                    workload.latest_containers.append([container.id,0,0])
                changed = True
            elif workload.latest_containers[index][0] > container.id:
                if container.status in ("waiting","running"):
                    #the container is running , add to the latest_container
                    workload.latest_containers.insert(index,[container.id,1,0])
                    changed = True
                    break
                elif index > 0:
                    #the container is terminated, but a earlier container is still running. , add to the latest_container
                    workload.latest_containers.insert(index,[container.id,1,0])
                    changed = True
                    break
                else:
                    #the container is terminated , and also it is a ealier container. ignore it
                    break
            elif workload.latest_containers[index][0] == container.id:
                if container.status not in ("waiting","running") and workload.latest_containers[index][1] == 1:
                    workload.latest_containers[index][1] = 0
                    changed = True
                break
            else:
                if workload.latest_containers[index][1] == 1:
                    #current latest container is still running, keep it
                    index += 1
                else:
                    if index == 0:
                        #this is the first latest container and it is stopped, also it is a earlier container than the container, remote  it
                        del workload.latest_containers[index]
                        changed = True
                    else:
                        #this is not the first latest container,keep it
                        index += 1
                                
        if changed and "latest_containers" not in workload_update_fields:
            workload_update_fields.append("latest_containers")

def process_status_file(context,metadata,status_file):
    now = timezone.now()
    context["containerstatus"]["harvester"].message="{}:Begin to process container status file '{}'".format(now.strftime("%Y-%m-%d %H:%M:%S"), metadata["resource_id"])
    context["containerstatus"]["harvester"].last_heartbeat = now
    context["containerstatus"]["harvester"].save(update_fields=["message","last_heartbeat"])
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
                imageid = "{}:{}".format(image_without_tag,record["imagetag"].strip())
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
                    cluster = models.Cluster.objects.get(name=clustername)
                except ObjectDoesNotExist as ex:
                    if settings.ENABLE_ADDED_BY_CONTAINERLOG:
                        cluster = models.Cluster(name=clustername,added_by_log=True)
                        cluster.save()
                    else:
                        continue

                context["clusters"][clustername] = cluster

            workload = None
            container = None
            key = (cluster.id,containerid)
            if key in context["containerstatus"]["terminated_containers"]:
                continue
            elif key in context["containerstatus"]["containers"]:
                container = context["containerstatus"]["containers"][key]
            else:
                try:
                    container = models.Container.objects.get(cluster=cluster,containerid=containerid)
                    context["containerstatus"]["containers"][key] = container
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

            elif settings.ENABLE_ADDED_BY_CONTAINERLOG:
                kind = "service?" if ports else "jobs?"
                new_workload_name = "{}-{}".format(image_without_tag,workload_name)
                workload_key = (cluster.id,"unknown",new_workload_name,kind)
                workload = None
                if workload_key in context["workloads"]:
                    workload,workload_update_fields = context["workloads"][workload_key]
                else:
                    #try to find the workload through cluster and workload name
                    workload_qs = models.Workload.objects.filter(cluster=cluster,name=workload_name)
                    for obj in workload_qs:
                        if obj.containerimage and obj.containerimage.imageid.startswith(image_without_tag) and ((ports and obj.listenings.all().count()) or (not ports and obj.listenings.all().count() == 0)):
                            workload = obj
                            break
                    if not workload :
                        if settings.ENABLE_ADDED_BY_CONTAINERLOG:
                            #not found , create a workload for this log
                            namespace_key = (cluster.id,"unknown")
                            if namespace_key in context["namespaces"]:
                                namespace = context["namespaces"][namespace_key]
                            else:
                                try:
                                    namespace = models.Namespace.objects.get(cluster=cluster,name="unknown")
                                except ObjectDoesNotExist as ex:
                                    namespace = models.Namespace(cluster=cluster,name="unknown",added_by_log=True,created=created or timezone.now(),modified=created or timezone.now())
                                    namespace.save()
    
                                context["namespaces"][namespace_key] = namespace
    
                            workload = models.Workload.objects.filter(cluster=cluster,namespace=namespace,name=new_workload_name,kind=kind).first()
    
                            if not workload:
                                image = models.ContainerImage.parse_image(imageid)
                                workload = models.Workload(
                                    cluster=namespace.cluster,
                                    project=namespace.project,
                                    namespace=namespace,
                                    name=new_workload_name,
                                    image=imageid,
                                    containerimage=image,
                                    kind=kind,
                                    api_version="",
                                    added_by_log=True,
                                    modified=created or timezone.now(),
                                    created=created or timezone.now()
                                )
                                #if finished and finished.date() < timezone.now().date():
                                #    workload.deleted = finished
                                workload.save()
                        else:
                            continue

                    workload_key = (cluster.id,workload.namespace.name,workload.name,workload.kind)
                    workload_update_fields = []
                    context["workloads"][workload_key] = (workload,workload_update_fields)

                container = models.Container(
                    cluster=workload.cluster,
                    namespace=workload.namespace,
                    workload=workload,
                    poduid = "",
                    containerid = containerid
                )
                context["containerstatus"]["containers"][key] = container
            else:
                continue

            #container
            container_status = get_container_status(container,containerstate)
            update_fields = set_fields(container,[
                ("exitcode",exitcode or container.exitcode),
                ("image",imageid or container.image),
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

            if container.status == "running" and container.workload.kind.lower() == "deployment" and (not container.pk or "status" in update_fields):
                context["containerstatus"]["new_deployed_workloads"].add(container.workload)

            if container_status.lower() in ("deleted","terminated"):
                del context["containerstatus"]["containers"][key]
                context["containerstatus"]["terminated_containers"].add(key)

        except Exception as ex:
            #delete already added records from this log file
            logger.error("Failed to parse container status record({}).{}".format(record,str(ex)))
            continue

    context["last_archive_time"] = metadata["archive_endtime"]
    logger.info("Harvest {1} records from file '{0}'".format(status_file,records))


def process_status(context):
    def _func(status,metadata,status_file):
        if context["containerstatus"]["max_harvest_files"]:
            if context["containerstatus"]["harvested_files"] >= context["containerstatus"]["max_harvest_files"]:
                raise exceptions.StopConsuming("Already harvested {} files".format(context["containerstatus"]["harvested_files"]))

            context["harvested_files"] += 1

        if status != HistoryDataConsumeClient.NEW:
            raise Exception("The status of the consumed history data shoule be New, but currently consumed histroy data's status is {},metadata={}".format(
                get_client().get_consume_status_name(status),
                metadata
            ))

        for key,client in (("podstatus_client",podstatus_harvester.get_client(cache=False)),):
            if key in context["resourceclients"]:
                last_consume = context["resourceclients"][key]
            else:
                last_consume = client.last_consume
                context["resourceclients"][key] = last_consume

            if not last_consume:
                raise exceptions.StopConsuming("Can't consume containerstatus file({0}) with archive_endtime '{1}', because no podstatus file was consumed".format(
                    metadata["resource_id"],
                    metadata["archive_endtime"]
                ))
            elif last_consume[1]["archive_endtime"] < metadata["archive_endtime"]:
                raise exceptions.StopConsuming("Can't consume containerstatus file({0}) which archive_endtime({1}) is after the archive_endtime({3}) of the last consumed podstatus file({2}) that was consumed at {4}".format(
                    metadata["resource_id"],
                    metadata["archive_endtime"],
                    last_consume[1]["resource_id"],
                    last_consume[1]["archive_endtime"],
                    last_consume[2]["consume_date"],
                ))

        process_status_file(context,metadata,status_file)

        #terminate the containers which should have terminated before.
        for workload in context["containerstatus"]["new_deployed_workloads"]:
            instances = workload.replicas if workload.replicas > 0 else 1
            containers = models.Container.objects.filter(cluster=workload.cluster,namespace=workload.namespace,workload=workload,status="running")[instances:]
            if not containers:
                continue
            workload_key = (workload.cluster.id,workload.namespace.name,workload.name,workload.kind)
            if workload_key in context["workloads"]:
                workload_update_fields = context["workloads"][workload_key][1]
            else:
                workload_update_fields = []
                context["workloads"][workload_key] = (workload,workload_update_fields)

            for c in containers:
                c.status = "shouldterminated"
                c.container_terminated = timezone.now()
                c.save(update_fields=["status","container_terminated"])
                update_latest_containers(context,c,workload=workload,workload_update_fields=workload_update_fields)


        #save workload
        for workload,workload_update_fields in context["workloads"].values():
            if workload_update_fields:
                workload.save(update_fields=workload_update_fields)
                workload_update_fields.clear()

        context["containerstatus"]["lock_session"].renew()
        context["containerstatus"]["harvested_files"] += 1


    return _func

def check_aborted_containers(harvester,context):
    """
    Find all running containers which lost hearbeat for long time and set the status of these containers to 'shouldterminated'
    """
    now = timezone.now()
    harvester.message="{}:Begin to check aborted containers".format(now.strftime("%Y-%m-%d %H:%M:%S"))
    harvester.last_heartbeat = now
    harvester.save(update_fields=["message","last_heartbeat"])
    for c in models.Container.objects.filter(status__in=("waiting","running"),last_checked__lt=now - settings.RANCHER_CONTAINER_ABORTED):
        c.status = "shouldterminated"
        c.container_terminated = timezone.now()
        c.save(update_fields=["status","container_terminated"])
        update_latest_containers(context,c)

    #save workload
    for workload,workload_update_fields in context["workloads"].values():
        if workload_update_fields:
            workload.save(update_fields=workload_update_fields)
            workload_update_fields.clear()

def clean_expired_containers(harvester):
    now = timezone.now()
    harvester.message="{}:Begin to clean expired containers".format(now.strftime("%Y-%m-%d %H:%M:%S"))
    harvester.last_heartbeat = now
    harvester.save(update_fields=["message","last_heartbeat"])
    modeldata.clean_expired_containers()

def harvest(reconsume=None,max_harvest_files=None,context={}):
    need_clean = [False]

    def _post_consume(client_consume_status,consume_result):
        now = timezone.localtime()
        if "next_clean_time" not in client_consume_status:
            client_consume_status["next_clean_time"] = timezone.make_aware(datetime(now.year,now.month,now.day)) + timedelta(days=1)
        elif now.hour > 6:
            return
        elif now >= client_consume_status["next_clean_time"]:
            need_clean[0] = True
            client_consume_status["next_clean_time"] = timezone.make_aware(datetime(now.year,now.month,now.day)) + timedelta(days=1)

    now = timezone.now()
    harvester = models.Harvester(name=harvestername,starttime=now,last_heartbeat=now,status=models.Harvester.RUNNING)
    harvester.save()
    message = None
    try:
        with LockSession(get_client(),settings.CONTAINERSTATUS_MAX_CONSUME_TIME_PER_LOG) as lock_session:
            try:
                if reconsume and get_client().is_client_exist(clientid=settings.RESOURCE_CLIENTID):
                    get_client().delete_clients(clientid=settings.RESOURCE_CLIENTID)
        
                context["containerstatus"] = context.get("containerstatus",{})
                context["containerstatus"] = {
                    "reconsume":reconsume  if reconsume is not None else context["containerstatus"].get("reconsume",False),
                    "max_harvest_files":max_harvest_files if max_harvest_files is not None else context["containerstatus"].get("max_harvest_files",None),
                    "lock_session":lock_session,
                    "new_deployed_workloads":set(),
                    "terminated_containers":set(),
                    "containers":{},
                    "harvester":harvester,
                    "harvested_files": 0
                }
                context["resourceclients"] = context.get("resourceclients",{})
                context["clusters"] = context.get("clusters",{})
                context["namespaces"] = context.get("namespaces",{})
                context["workloads"] = context.get("workloads",{})

                #consume container status file
                result = get_client().consume(process_status(context),f_post_consume=_post_consume)
                #change the status of containers which has no status data harvested in recent half an hour
                if result[1]:
                    if result[0]:
                        message = """Failed to harvest container status,
        {} container status files were consumed successfully.
        {}
        {} container status files were failed to consume
        {}"""
                        message = message.format(
                            len(result[0]),
                            "\n        ".join(["Succeed to harvest container status file '{}'".format(resource_ids) for resource_status,resource_status_name,resource_ids in result[0]]),
                            len(result[1]),
                            "\n        ".join(["Failed to harvest container status '{}'.{}".format(resource_ids,msg) for resource_status,resource_status_name,resource_ids,msg in result[1]])
                        )
                    else:
                        message = """Failed to harvest container status,{} container status files were failed to consume
        {}"""
                        message = message.format(
                            len(result[1]),
                            "\n        ".join(["Failed to harvest container status file '{}'.{}".format(resource_ids,msg) for resource_status,resource_status_name,resource_ids,msg in result[1]])
                        )
                elif result[0]:
                    message = """Succeed to harvest container status, {} container status files were consumed successfully.
        {}"""
                    message = message.format(
                        len(result[0]),
                        "\n        ".join(["Succeed to harvest container status file '{}'".format(resource_ids) for resource_status,resource_status_name,resource_ids in result[0]])
                    )
                else:
                    message = "Succeed to harvest container status, no new container status file was added since last harvesting"
    
    
                harvester.status = models.Harvester.FAILED if result[1] else models.Harvester.SUCCEED
            
                try:
                    if "last_archive_time" in context:
                        for container in models.Container.objects.filter(status__in=("Waiting",'Running'),last_checked__lt=context["last_archive_time"] - timedelta(minutes=30)):
                            container.status="LostHeartbeat"
                            container.save(update_fields=["status"])
                            update_latest_containers(context,container)
            
                    #save workload
                    for workload,workload_update_fields in context["workloads"].values():
                        if workload_update_fields:
                            workload.save(update_fields=workload_update_fields)
    
                except:
                    harvester.status = models.Harvester.FAILED
                    msg = "Failed to save changed Containers or Workloads.{}".format(traceback.format_exc())
                    logger.error(msg)
                    message = """{}
    =========Consuming Results================
    {}""".format(msg,message)
    
                return result
            except:
                harvester.status = models.Harvester.FAILED
                message = "Failed to harvest container status.{}".format(traceback.format_exc())
                logger.error(message)
                return ([],[(None,None,None,message)])
    except exceptions.AlreadyLocked as ex:
        harvester.status = models.Harvester.SKIPPED
        message = "The previous harvest process is still running.{}".format(str(ex))
        logger.warning(message)
        return ([],[(None,None,None,message)])
    finally:
        if need_clean[0]:
            try:
                check_aborted_containers(harvester,context)
                clean_expired_containers(harvester)
                message = """Succeed to clean expired containers.
{}""".format(message)
            except:
                harvester.status = models.Harvester.FAILED
                msg = "Failed to clean expired containers.{}".format(traceback.format_exc())
                logger.error(msg)
                message = """{}
=========Consuming Results================
{}""".format(msg,message)
        harvester.message = message
        harvester.endtime = timezone.now()
        harvester.last_heartbeat = harvester.endtime
        harvester.save(update_fields=["endtime","message","status","last_heartbeat"])




