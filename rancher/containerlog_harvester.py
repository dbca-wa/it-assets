import json
import traceback
import logging
import datetime
import collections
import re

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.core.mail import EmailMessage

from data_storage import HistoryDataConsumeClient,LocalStorage,exceptions,LockSession
from . import models
from itassets.utils import LogRecordIterator

from .utils import to_datetime,set_fields
from . import containerstatus_harvester
from . import podstatus_harvester
from . import modeldata

logger = logging.getLogger(__name__)

harvestername = "containerlog"

log_levels = [
    (re.compile("(^|[^a-zA-Z]+)TRACE[^a-zA-Z]+"),(models.ContainerLog.TRACE,True)),  # (message regex pattern,(message leve, start a new message?))
    (re.compile("(^|[^a-zA-Z]+)DEBUG[^a-zA-Z]+"),(models.ContainerLog.DEBUG,True)),
    (re.compile("(^|[^a-zA-Z]+)INFO[^a-zA-Z]+"),(models.ContainerLog.INFO,True)),
    (re.compile("(^|[^a-zA-Z]+)WARN(ING)?[^a-zA-Z]+"),(models.ContainerLog.WARNING,True)),
    (re.compile("(^|[^a-zA-Z]+)ERROR[^a-zA-Z]+"),(models.ContainerLog.ERROR,True)),
    (re.compile("(^|\s+)(level|lvl)\s*=\s*trace\s+",re.IGNORECASE),(models.ContainerLog.TRACE,True)),
    (re.compile("(^|\s+)(level|lvl)\s*=\s*debug\s+",re.IGNORECASE),(models.ContainerLog.DEBUG,True)),
    (re.compile("(^|\s+)(level|lvl)\s*=\s*info\s+",re.IGNORECASE),(models.ContainerLog.INFO,True)),
    (re.compile("(^|\s+)(level|lvl)\s*=\s*warn(ing)?\s+",re.IGNORECASE),(models.ContainerLog.WARNING,True)),
    (re.compile("(^|\s+)(level|lvl)\s*=\s*error\s+",re.IGNORECASE),(models.ContainerLog.ERROR,True)),
    (re.compile("(warning)[^a-zA-Z0-9]+",re.IGNORECASE),(models.ContainerLog.WARNING,False)),
    (re.compile("(exception|error|failed|wrong|err|traceback)[^a-zA-Z0-9]+",re.IGNORECASE),(models.ContainerLog.ERROR,False))
]
_containerlog_client = None


def get_client(cache=True):
    """
    Return the blob resource client
    """
    global _containerlog_client
    if _containerlog_client is None or not cache:
        client = HistoryDataConsumeClient(
            LocalStorage(settings.CONTAINERLOG_REPOSITORY_DIR),
            settings.CONTAINERLOG_RESOURCE_NAME,
            settings.RESOURCE_CLIENTID,
            max_saved_consumed_resources=settings.CONTAINERLOG_MAX_SAVED_CONSUMED_RESOURCES
        )
        if cache:
            _containerlog_client = client
        else:
            return client

    return _containerlog_client


def update_workload_latest_containers(context,containerlog):
    container = containerlog.container
    workload_key = (container.workload.cluster.id,container.workload.namespace.name,container.workload.name,container.workload.kind)
    if workload_key not in context["workloads"]:
        workload_update_fields = []
        workload = container.workload
        context["workloads"][workload_key] = (workload,workload_update_fields)
    else:
        workload,workload_update_fields = context["workloads"][workload_key]

    if not workload.latest_containers:
        return

    if containerlog.level == models.ContainerLog.WARNING:
        status = models.Workload.WARNING | models.Workload.INFO
    elif containerlog.level == models.ContainerLog.ERROR:
        status = models.Workload.ERROR | models.Workload.INFO
    else:
        status = models.Workload.INFO

    for container_data in workload.latest_containers:
        if container_data[0] != container.id:
            continue
        else:
            if container_data[2] & status != status:
                container_data[2] = container_data[2] | status
                if "latest_containers" not in workload_update_fields:
                    workload_update_fields.append("latest_containers")


def _add_notify_log(context,containerlog):
    if settings.DISABLE_LOG_NOTIFICATION_EMAIL:
        return

    if containerlog.level not in (models.ContainerLog.WARNING,models.ContainerLog.ERROR):
        return

    container = containerlog.container
    workload = container.workload
    imagefamily = workload.containerimage.imagefamily
    if not imagefamily.enable_notify:
        return
    elif not imagefamily.enable_warning_msg and containerlog.level == models.ContainerLog.WARNING:
        return

    if not imagefamily.filter_log(containerlog):
        return

    if workload not in context["notify_contacts"]:
        if imagefamily.contacts:
            notify_contacts = imagefamily.contacts
            context["notify_contacts"][workload] = notify_contacts
        else:
            notify_contacts = None
            del_notify_contacts = None
            for res in models.WorkloadResource.objects.filter(
                workload=workload,
                resource_type__in=[models.EnvScanModule.MEMCACHED,models.EnvScanModule.REDIS,models.EnvScanModule.POSTGRES,models.EnvScanModule.ORACLE,models.EnvScanModule.MYSQL],
                config_source=models.WorkloadResource.SERVICE
            ).only("resource_id"):
                for dep in models.WorkloadDependency.objects.filter(workload=workload,dependency_type=res.resource_type,dependency_id=res.resource_id).only("dependent_workloads","del_dependent_workloads"):
                    for wlid in dep.dependent_workloads:
                        wl = models.Workload.objects.filter(id=wlid).only("containerimage").first()
                        if not wl:
                            continue
                        if wl.containerimage.imagefamily.contacts:
                            notify_contacts = wl.containerimage.imagefamily.contacts
                            break

                    if notify_contacts:
                        break
                    elif del_notify_contacts:
                        continue

                    for wlid in dep.del_dependent_workloads:
                        wl = models.Workload.objects.filter(id=wlid).only("containerimage").first()
                        if not wl:
                            continue
                        if wl.containerimage.imagefamily.contacts:
                            del_notify_contacts = wl.containerimage.imagefamily.contacts
                            break

                if notify_contacts:
                    break

            notify_contacts = notify_contacts or del_notify_contacts
            context["notify_contacts"][workload] = notify_contacts
    else:
        notify_contacts = context["notify_contacts"][workload]

    if not notify_contacts:
        return

    workload_logs = context["notify_logs"].get(workload)
    if not workload_logs:
        workload_logs = collections.OrderedDict()
        context["notify_logs"][workload] = workload_logs

    container_logs = workload_logs.get(container)
    if not container_logs:
        container_logs = []
        workload_logs[container] = container_logs

    container_logs.append("{} {}:{}".format(containerlog.logtime.strftime("%Y-%m-%d %H:%M:%S.%f"),containerlog.get_level_display(),containerlog.message))


def process_status_file(context,metadata,status_file):
    now = timezone.now()
    context["logstatus"]["harvester"].message="{}:Begin to process container log file '{}'".format(now.strftime("%Y-%m-%d %H:%M:%S"), metadata["resource_id"])
    context["logstatus"]["harvester"].last_heartbeat = now
    context["logstatus"]["harvester"].save(update_fields=["message","last_heartbeat"])
    if settings.CONTAINERLOG_STREAMING_PARSE:
        status_records = LogRecordIterator(status_file)
    else:
        with open(status_file,"r") as f:
            status_records = json.loads(f.read())

    records = 0
    for record in status_records:
        try:
            if any(not (record.get(key) or "").strip() for key in ("computer","containerid","logentry","logtime")):
                #data is incomplete,ignore
                continue

            logtime = to_datetime(record["logtime"])
            containerid = record["containerid"].strip()
            message = record["logentry"].strip()
            if not message:
                continue

            message = message.replace("\x00","").replace("\\n","\n")
            message = message.strip()
            """
            #try to get log time from message.
            datestr = message[0:19]
            for pattern in ["%Y-%m-%d %H:%M:%S"]:
                try:
                    logtime = timezone.make_aware(datetime.datetime.strptime(datestr,pattern))
                    break
                except:
                    continue
            """

            source = (record["logentrysource"] or "").strip() or None

            computer = record["computer"].strip()
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
            """
            if cluster.name != 'az-k3s-oim01':
                continue
            """

            key = (cluster.id,containerid)
            if key in context["logstatus"]["containers"]:
                container,container_update_fields = context["logstatus"]["containers"][key]
            else:
                try:
                    container = models.Container.objects.get(cluster=cluster,containerid=containerid)
                except ObjectDoesNotExist as ex:
                    if settings.CONTAINERLOG_FAILED_IF_CONTAINER_NOT_FOUND:
                        raise Exception("The containerId({}) in log resource({}) Not Found".format(containerid,metadata))
                    else:
                        continue
                container_update_fields = []
                context["logstatus"]["containers"][key] = (container,container_update_fields)

            key = (cluster.id,containerid)
            if key in context["logstatus"]["containerlogs"]:
                containerlog = context["logstatus"]["containerlogs"][key]
                containerlog.archiveid = metadata["resource_id"]
            else:
                containerlog = models.ContainerLog(archiveid=metadata["resource_id"])
                context["logstatus"]["containerlogs"][key] = containerlog

            result = container.workload.containerimage.imagefamily.get_loglevel(message)
            if result:
                level,newmessage = result
            else:
                level = None
                newmessage = False
                for log_level_re,value in log_levels:
                    if log_level_re.search(message):
                        level,newmessage = value
                        break

                if level is None:
                    if source.lower() in ('stderr',):
                        level = models.ContainerLog.ERROR
                    else:
                        level = models.ContainerLog.INFO

            if not containerlog.logtime:
                containerlog.id = None
                containerlog.container = container
                containerlog.logtime = logtime
                containerlog.latest_logtime = logtime
                containerlog.source = source
                #containerlog.message = "{}:{}".format(logtime.strftime("%Y-%m-%d %H:%M:%S.%f"),message)
                containerlog.message = message
                containerlog.level = level
            elif newmessage or logtime >= (containerlog.latest_logtime + datetime.timedelta(seconds=1)) or containerlog.source != source :
                records += 1

                containerlog.save()
                _add_notify_log(context,containerlog)
                container = containerlog.container
                update_workload_latest_containers(context,containerlog)
                key = (container.cluster.id,container.containerid)
                if key in context["logstatus"]["containers"]:
                    container,container_update_fields = context["logstatus"]["containers"][key]
                else:
                    container_update_fields = []
                    context["logstatus"]["containers"][key] = (container,container_update_fields)
                container_update_fields = set_fields(container,[
                    ("log", True),
                    ("warning", True if containerlog.level == models.ContainerLog.WARNING else container.warning),
                    ("error", True if containerlog.level == models.ContainerLog.ERROR else container.error),
                ],container_update_fields)
                if newmessage and containerlog.logtime >= logtime:
                    #more than one logs at the same time, add one millesconds to the logtime because of unique index
                    logtime = containerlog.logtime + datetime.timedelta(milliseconds=1)
                containerlog.id = None
                containerlog.container = container
                containerlog.logtime = logtime
                containerlog.latest_logtime = logtime
                containerlog.source = source
                #containerlog.message = "{}:{}".format(logtime.strftime("%Y-%m-%d %H:%M:%S.%f"),message)
                containerlog.message = message
                containerlog.level = level
            else:
                if level > containerlog.level:
                    containerlog.level = level
                #containerlog.message = "{}\n{}:{}".format(containerlog.message,logtime.strftime("%Y-%m-%d %H:%M:%S.%f"),message)
                containerlog.message = "{}\n{}".format(containerlog.message,message)
                if logtime > containerlog.latest_logtime:
                    containerlog.latest_logtime = logtime
        except Exception as ex:
            #delete already added records from this log file
            logger.error("Failed to parse container log record({}).{}".format(record,str(ex)))
            continue

    #save the last message
    containerlogs = [o for o in context["logstatus"]["containerlogs"].values() if o.logtime and o.container]
    containerlogs.sort(key=lambda o:o.logtime)
    for containerlog in containerlogs:
        records += 1
        containerlog.save()
        _add_notify_log(context,containerlog)
        container = containerlog.container
        update_workload_latest_containers(context,containerlog)
        key = (container.cluster.id,container.containerid)
        if key in context["logstatus"]["containers"]:
            container,container_update_fields = context["logstatus"]["containers"][key]
        else:
            container_update_fields = []
            context["logstatus"]["containers"][key] = (container,container_update_fields)
        container_update_fields = set_fields(container,[
            ("log", True),
            ("warning", True if containerlog.level == models.ContainerLog.WARNING else container.warning),
            ("error", True if containerlog.level == models.ContainerLog.ERROR else container.error),
        ],container_update_fields)
        containerlog.id = None
        containerlog.logtime = None
        containerlog.level = None
        containerlog.message = None
        containerlog.source = None
        containerlog.container = None
        containerlog.latest_logtime = None

    #save terminated containers
    terminated_keys = []
    for key,value  in context["logstatus"]["containers"].items():
        container,container_update_fields = value
        if container.container_terminated and (container.container_terminated + datetime.timedelta(minutes=30)) < metadata["archive_endtime"]:
            terminated_keys.append(key)
            if not container.pk:
                container.save()
            elif container_update_fields:
                container.save(update_fields=container_update_fields)
                container_update_fields.clear()

    #delete terminated containers from cache
    for key in terminated_keys:
        del context["logstatus"]["containers"][key]
        if key in context["logstatus"]["containerlogs"]:
            del context["logstatus"]["containerlogs"][key]
    logger.info("Harvest {1} records from file '{0}'".format(status_file,records))


def process_status(context):
    def _func(status,metadata,status_file):
        if context["logstatus"]["max_harvest_files"]:
            if context["logstatus"]["harvested_files"] >= context["logstatus"]["max_harvest_files"]:
                raise exceptions.StopConsuming("Already harvested {} files".format(context["logstatus"]["harvested_files"]))

        if status != HistoryDataConsumeClient.NEW:
            raise Exception("The status of the consumed history data shoule be New, but the status of the currently consumed histroy data is {},metadata={}".format(
                get_client().get_consume_status_name(status),
                metadata
            ))
        #guarantee containerlog must be consumed after podstatus and containerstatus
        for name,key,client in (("podstatus","podstatus_client",podstatus_harvester.get_client(cache=False)),("containerstatus","containerstatus_client",containerstatus_harvester.get_client(cache=False))):
            if key in context["resourceclients"]:
                last_consume = context["resourceclients"][key]
            else:
                last_consume = client.last_consume
                context["resourceclients"][key] = last_consume

            if not last_consume:
                raise exceptions.StopConsuming("Can't consume containerlog file({0}) with archive_endtime '{1}', because no {2} file was consumed.".format(
                    metadata["resource_id"],
                    metadata["archive_endtime"],
                    name
                ))
            elif last_consume[1]["archive_endtime"] < metadata["archive_endtime"]:
                raise exceptions.StopConsuming("Can't consume containerlog file({0}) which archive_endtime({1}) is after the archive_endtime({4}) of the last consumed {2} file({3}) that was consumed at {5}".format(
                    metadata["resource_id"],
                    metadata["archive_endtime"],
                    name,
                    last_consume[1]["resource_id"],
                    last_consume[1]["archive_endtime"],
                    last_consume[2]["consume_date"],
                ))

        #delete the existing log which were populated in the previous consuming
        models.ContainerLog.objects.filter(archiveid=metadata["resource_id"]).delete()

        process_status_file(context,metadata,status_file)

        #save containers
        for container,container_update_fields  in context["logstatus"]["containers"].values():
            if container_update_fields:
                container.save(update_fields=container_update_fields)
                container_update_fields.clear()

        #save workload
        for workload,workload_update_fields in context["workloads"].values():
            if workload_update_fields:
                workload.save(update_fields=workload_update_fields)
                workload_update_fields.clear()

        context["logstatus"]["lock_session"].renew()
        context["logstatus"]["harvested_files"] += 1

    return _func


def clean_expired_containerlogs(harvester):
    now = timezone.now()
    harvester.message="{}:Begin to clean expired containers".format(now.strftime("%Y-%m-%d %H:%M:%S"))
    harvester.last_heartbeat = now
    harvester.save(update_fields=["message","last_heartbeat"])
    modeldata.clean_expired_containerlogs()


def harvest(reconsume=None,max_harvest_files=None,context={}):
    need_clean = [False]

    def _post_consume(client_consume_status,consume_result):
        now = timezone.localtime()
        if "next_clean_time" not in client_consume_status:
            client_consume_status["next_clean_time"] = timezone.make_aware(datetime.datetime(now.year,now.month,now.day)) + datetime.timedelta(days=1)
        elif now.hour > 6:
            return
        elif now >= client_consume_status["next_clean_time"]:
            need_clean[0] = True
            client_consume_status["next_clean_time"] = timezone.make_aware(datetime.datetime(now.year,now.month,now.day)) + datetime.timedelta(days=1)

    now = timezone.now()
    harvester = models.Harvester(name=harvestername,starttime=now,last_heartbeat=now,status=models.Harvester.RUNNING)
    harvester.save()
    message = None
    try:
        with LockSession(get_client(),settings.CONTAINERLOG_MAX_CONSUME_TIME_PER_LOG) as lock_session:
            try:
                if reconsume:
                    if get_client().is_client_exist(clientid=settings.RESOURCE_CLIENTID):
                        get_client().delete_clients(clientid=settings.RESOURCE_CLIENTID)
                    modeldata.clean_containerlogs()

                context["logstatus"] = context.get("logstatus",{})
                context["logstatus"] = {
                    "reconsume":reconsume  if reconsume is not None else context["logstatus"].get("reconsume",False),
                    "max_harvest_files":max_harvest_files if max_harvest_files is not None else context["logstatus"].get("max_harvest_files",None),
                    "lock_session":lock_session,
                    "containerlogs":{},
                    "harvester":harvester,
                    "containers":{},
                    "harvested_files": 0
                }
                context["resourceclients"] = context.get("resourceclients",{})
                context["clusters"] = context.get("clusters",{})
                context["workloads"] = context.get("workloads",{})
                #consume container log file
                result = get_client().consume(process_status(context),f_post_consume=_post_consume)

                if result[1]:
                    if result[0]:
                        message = """Failed to harvest container log,
        {} container log files were consumed successfully.
        {}
        {} container log files were failed to consume
        {}"""
                        message = message.format(
                            len(result[0]),
                            "\n        ".join(["Succeed to harvest container log file '{}'".format(resource_ids) for resource_status,resource_status_name,resource_ids in result[0]]),
                            len(result[1]),
                            "\n        ".join(["Failed to harvest container log '{}'.{}".format(resource_ids,msg) for resource_status,resource_status_name,resource_ids,msg in result[1]])
                        )
                    else:
                        message = """Failed to harvest container log,{} container log files were failed to consume
        {}"""
                        message = message.format(
                            len(result[1]),
                            "\n        ".join(["Failed to harvest container log file '{}'.{}".format(resource_ids,msg) for resource_status,resource_status_name,resource_ids,msg in result[1]])
                        )
                elif result[0]:
                    message = """Succeed to harvest container log, {} container log files were consumed successfully.
        {}"""
                    message = message.format(
                        len(result[0]),
                        "\n        ".join(["Succeed to harvest container log file '{}'".format(resource_ids) for resource_status,resource_status_name,resource_ids in result[0]])
                    )
                else:
                    message = "Succeed to harvest container log, no new container log file was added since last harvesting"

                harvester.status = models.Harvester.FAILED if result[1] else models.Harvester.SUCCEED
                return result
            except:
                harvester.status = models.Harvester.FAILED
                message = "Failed to harvest container log.{}".format(traceback.format_exc())
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
                clean_expired_containerlogs(harvester)
                message = """Succeed to clean expired containers.
=========Consuming Results================
{}""".format(message)
            except:
                harvester.status = models.Harvester.FAILED
                msg = "Failed to clean expired container logs.{}".format(traceback.format_exc())
                logger.error(msg)
                message = """{}
=========Consuming Results================
{}""".format(msg,message)

        harvester.message = message
        harvester.endtime = timezone.now()
        harvester.last_heartbeat = harvester.endtime
        harvester.save(update_fields=["endtime","message","status","last_heartbeat"])


def harvest_all(context={}):
    podstatus_harvester.harvest(context)
    containerstatus_harvester.harvest(context)
    context["notify_logs"] = {}
    context["notify_contacts"] = {}
    harvest(context = context)
    if context["notify_logs"]:
        #send notify email to developersA
        #populate the map between contact and workloads
        contacts = {}
        for wl,wl_contacts in context["notify_contacts"].items():
            if not wl_contacts:
                continue
            for wl_contact in wl_contacts:
                if wl_contact in contacts:
                    contacts[wl_contact].append(wl)
                else:
                    contacts[wl_contact] = [wl]

        #group contacts by workloads
        contact_groups = {}
        for contact,wls in contacts.items():
            wls = tuple(wls)
            if wls in contact_groups:
                contact_groups[wls].append(contact)
            else:
                contact_groups[wls] = [contact]

        contacts.clear()
        contacts = None
        content = None
        #send notify emails
        for wls,contacts in contact_groups.items():
            html_content = "<br><br>-------------------------------------------------------------------<br><br>".join(
                "<div css='font-weight:bold;font-size:25px'>{0}</div>{1}".format(
                    wl,
                    "<br><br>".join(
                        "<div css='font-weight:bold;font-size:20px'>{0}</div>{1}".format(
                            container,
                            "<br>".join("<pre>{}</pre>".format(msg) for msg in messages)
                        ) for container,messages in context["notify_logs"][wl].items()
                    )
                ) for wl in wls
            )
            mail = EmailMessage("Some errors/warnings occured in your workloads.",html_content,settings.NOREPLY_EMAIL,contacts)
            mail.content_subtype = "html"
            mail.send()
