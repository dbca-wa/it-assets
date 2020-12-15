import simdjson
import traceback
import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from data_storage import HistoryDataConsumeClient,LocalStorage,exceptions
from .models import Cluster,Namespace,Workload,Container
from itassets.utils import LogRecordIterator
from .utils import to_datetime,set_fields

logger = logging.getLogger(__name__)
_podstatus_client = None


def get_podstatus_client(cache=True):
    """
    Return the blob resource client
    """
    global _podstatus_client
    if _podstatus_client is None:
        client = HistoryDataConsumeClient(
            LocalStorage(settings.PODSTATUS_REPOSITORY_DIR),
            settings.PODSTATUS_RESOURCE_NAME,
            settings.RESOURCE_CLIENTID,
            max_saved_consumed_resources=settings.PODSTATUS_MAX_SAVED_CONSUMED_RESOURCES
        )
        if cache:
            _podstatus_client = client
        else:
            return client

    return _podstatus_client


workload_kind_mapping = {
    "replicaset":"Deployment",
    "job":"CronJob",
    "statefulset":"StatefulSet",
    "daemonset":"DaemonSet"
}


def to_workload_kind(controllerkind):
    kind = workload_kind_mapping.get(controllerkind.strip().lower())
    if not kind:
        raise Exception("Controllder kind({}) Not Support".format(controllerkind))

    return kind

def process_status_file(context,metadata,status_file):
    if settings.PODSTATUS_STREAMING_PARSE:
        status_records = LogRecordIterator(status_file)
    else:
        with open(status_file,"r") as f:
            status_records = simdjson.loads(f.read())

    records = 0
    for record in status_records:
        records += 1
        try:
            if any(not (record.get(key) or "").strip() for key in ("clusterid","computer","namespace","poduid","containerid","pod_created","container_name","controllerkind")):
                #data is incomplete,ignore
                continue

            if record["computer"].strip().lower().startswith("aks-nodepool"):
                cluster_name = record["clusterid"].strip().rsplit("/")[-1]
            else:
                cluster_name = record["computer"].strip()

            cluster_name = cluster_name.split(".",1)[0]

            if cluster_name in context["clusters"]:
                cluster = context["clusters"][cluster_name]
            else:
                #logger.debug("find cluster {}".format(cluster_name))
                try:
                    cluster = Cluster.objects.get(name=cluster_name)
                except ObjectDoesNotExist as ex:
                    cluster = Cluster(name=cluster_name,added_by_log=True)
                    cluster.save()
                context["clusters"][cluster_name] = cluster

            namespace_name = record["namespace"].strip()
            key = (cluster,namespace_name)
            if key in context["namespaces"]:
                namespace = context["namespaces"][key]
            else:
                #logger.debug("find namespace {}".format(namespace_name))
                try:
                    namespace = Namespace.objects.get(cluster=cluster,name=namespace_name)
                except ObjectDoesNotExist as ex:
                    namespace = Namespace(cluster=cluster,name=namespace_name,added_by_log=True,created=pod_created,modified=pod_created)
                    namespace.save()
                context["namespaces"][key] = namespace

            poduid = record["poduid"].strip()
            containerid = record["containerid"].strip()
            container_name = record["container_name"].split("/")
            if len(container_name) != 2:
                raise Exception("Can't parse the container_name '{}'".format(record["container_name"]))
            elif container_name[0].strip() != poduid:
                raise Exception("The first part of the container_name '{}' should be '{}'".format(record["container_name"],poduid))
            else:
                workload_name = container_name[1].strip()

            pod_created = to_datetime(record.get("pod_created"))
            pod_started = to_datetime(record.get("pod_started"))
            podip = record.get("podip")
            max_timegenerated = to_datetime(record["max_timegenerated"])

            workload_kind = to_workload_kind(record["controllerkind"])

            key = (namespace,workload_name,workload_kind)
            if key in context["workloads"]:
                workload,workload_update_fields = context["workloads"][key]
            else:
                #logger.debug("find workload.{}/{}({})".format(namespace.name,workload_name,workload_kind))
                try:
                    #logger.debug("find workload, cluster={}, project={}, namespace={},name={},kind={}".format(cluster,namespace.project,namespace,workload_name,workload_kind))
                    workload = Workload.objects.get(cluster=cluster,namespace=namespace,name=workload_name,kind=workload_kind)
                except ObjectDoesNotExist as ex:
                    workload = Workload(cluster=cluster,project=namespace.project,namespace=namespace,name=workload_name,kind=workload_kind,image="",api_version="",modified=pod_created,created=pod_created,added_by_log=True)
                    #if pod_created.date() < timezone.now().date():
                    #    workload.deleted = max_timegenerated
                    workload.save()
                workload_update_fields = []
                context["workloads"][key] = (workload,workload_update_fields)

            try:
                container = Container.objects.get(cluster=cluster,containerid=containerid)
                previous_workload = container.workload
                previous_namespace = container.namespace
            except ObjectDoesNotExist as ex:
                container = Container(cluster=cluster,containerid=containerid)
                previous_workload = None
                previous_namespace = None

            update_fields = set_fields(container,[
                ("namespace",namespace),
                ("workload",workload),
                ("pod_created",pod_created),
                ("pod_started",pod_started),
                ("podip",podip),
                ("poduid",poduid),
                ("last_checked",to_datetime(record["max_timegenerated"]))
            ])
            if workload and workload.deleted and workload.deleted < max_timegenerated:
                workload.deleted = max_timegenerated
                if "deleted" not in workload_update_fields:
                    workload_update_fields.append("deleted")

            if previous_workload and previous_workload != workload and previous_workload.added_by_log and previous_workload.namespace.name == "unknown":
                context["orphan_workloads"].add(previous_workload)
                context["orphan_namespaces"].add(previous_workload.namespace)

            if container.pk is None:
                container.save()
            elif update_fields:
                container.save(update_fields=update_fields)

        except Exception as ex:
            #delete already added records from this log file
            logger.error("Failed to parse pod status record({}).{}".format(record,traceback.format_exc()))
            raise Exception("Failed to parse pod status record({}).{}".format(record,str(ex)))

    logger.info("Harvest {1} records from file '{0}'".format(status_file,records))


def process_status(context,max_harvest_files):
    def _func(status,metadata,status_file):
        if max_harvest_files:
            if context["harvested_files"] >= max_harvest_files:
                raise Exception("Already harvested {} files".format(context["harvested_files"]))
            context["harvested_files"] += 1

        if status != HistoryDataConsumeClient.NEW:
            raise Exception("The status of the consumed history data shoule be New, but currently consumed histroy data's status is {},metadata={}".format(
                get_podstatus_client().get_consume_status_name(status),
                metadata
            ))
        process_status_file(context,metadata,status_file)

        #save workload
        for workload,workload_update_fields in context["workloads"].values():
            if workload_update_fields:
                workload.save(update_fields=workload_update_fields)
                workload_update_fields.clear()

        #delete orphan workloads
        for workload in context["orphan_workloads"]:
            if not Container.objects.filter(cluster=workload.cluster,workload=workload).exists():
                workload.delete()
        context["orphan_workloads"].clear()

        #delete orphan namespaces
        for namespace in context["orphan_namespaces"]:
            if not Workload.objects.filter(cluster=namespace.cluster,namespace=namespace).exists():
                namespace.delete()
        context["orphan_namespaces"].clear()

        context["renew_lock_time"] = context["f_renew_lock"](context["renew_lock_time"])

    return _func

def harvest(reconsume=False,max_harvest_files=None):
    try:
        renew_lock_time = get_podstatus_client().acquire_lock(expired=settings.PODSTATUS_MAX_CONSUME_TIME_PER_LOG)
    except exceptions.AlreadyLocked as ex:
        msg = "The previous harvest process is still running.{}".format(str(ex))
        logger.info(msg)
        return ([],[(None,None,None,msg)])

    try:
        if reconsume and get_podstatus_client().is_client_exist(clientid=settings.RESOURCE_CLIENTID):
            get_podstatus_client().delete_clients(clientid=settings.RESOURCE_CLIENTID)

        context = {
            "reconsume":reconsume,
            "renew_lock_time":renew_lock_time,
            "f_renew_lock":get_podstatus_client().renew_lock,
            "clusters":{},
            "namespaces":{},
            "workloads":{},
            "orphan_workloads":set(),
            "orphan_namespaces":set()
        }
        if max_harvest_files:
            context["harvested_files"] = 0
        #consume nginx config file
        result = get_podstatus_client().consume(process_status(context,max_harvest_files))

        return result

    finally:
        get_podstatus_client().release_lock()



