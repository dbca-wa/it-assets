from datetime  import datetime,timedelta
import logging

from django.db.models import F,Q
from django.conf import settings
from django.utils import timezone

from data_storage import LockSession

from . import models

logger = logging.getLogger(__name__)

def synchronize_logharvester(func):
    def _wrapper(*args,**kwargs):
        from .podstatus_harvester import get_podstatus_client
        from .containerstatus_harvester import get_containerstatus_client
        from .containerlog_harvester import get_containerlog_client
        with LockSession(get_podstatus_client(),3600 * 3) as lock_session1:
            with LockSession(get_containerstatus_client(),3600 * 3) as lock_session2:
                with LockSession(get_containerlog_client(),3600 * 3) as lock_session2:
                    func(*args,**kwargs)
    return _wrapper

def _reset_workload_latestcontainers():
    """
    Reset the latest containers
    """
    workloads = {}
    processed_containers = set()
    for workload in models.Workload.objects.all().order_by("cluster","name"):
        logger.debug("Begin to process models.Workload:{}({})".format(workload,workload.id))
        workload.latest_containers = None
        if workload.kind in ("Deployment",'DaemonSet','StatefulSet','service?'):
            for container in models.Container.objects.filter(cluster=workload.cluster,workload=workload,status__in=("waiting","running")).order_by("pod_created"):
                log_status = (models.Workload.INFO if container.log else 0) | (models.Workload.WARNING if container.warning else 0) | (models.Workload.ERROR if container.error else 0)
                if workload.latest_containers is None:
                    workload.latest_containers=[[container.id,1,log_status]]
                else:
                    workload.latest_containers.append([container.id,1,log_status])
        else:
            processed_containers.clear()
            for qs in [
                models.Container.objects.filter(cluster=workload.cluster,workload=workload,status__in=("waiting","running")).order_by("pod_created"),
                [models.Container.objects.filter(cluster=workload.cluster,workload=workload).order_by("-pod_created").first()]
            ]:
                for container in qs:
                    if not container:
                        continue
                    if container.id in processed_containers:
                        continue
                    processed_containers.add(container.id)

                    log_status = (models.Workload.INFO if container.log else 0) | (models.Workload.WARNING if container.warning else 0) | (models.Workload.ERROR if container.error else 0)
                    running_status = 1 if container.status in ("waiting","running") else 0
                    if workload.latest_containers is None:
                        workload.latest_containers=[[container.id,running_status,log_status]]
                    else:
                        workload.latest_containers.append([container.id,running_status,log_status])
        workload.save(update_fields=["latest_containers"])
        logger.debug("models.Workload({}<{}>):update latest_containers to {}".format(workload,workload.id,workload.latest_containers))

def reset_workload_latestcontainers(sync=True):
    if sync:
        synchronize_logharvester(_reset_workload_latestcontainers)()
    else:
        _reset_workload_latestcontainers()


def reset_project_property():
    """
    synchronize_logharvester namespace's project with the project of workload, ingress and models.PersistentVolumeClaim
    """
    #assign namespace's project to workload's project
    for obj in models.Workload.objects.filter(namespace__project__isnull=False).exclude(project=F("namespace__project")):
        obj.project = obj.namespace.project
        obj.save(update_fields=["project"])

    #set workload's project to None if namespace's project is none
    for obj in models.Workload.objects.filter(namespace__project__isnull=True).filter(project__isnull=False):
        obj.project = None
        obj.save(update_fields=["project"])

    #assign namespace's project to ingress's project
    for obj in models.Ingress.objects.filter(namespace__isnull=False,namespace__project__isnull=False).exclude(project=F("namespace__project")):
        obj.project = obj.namespace.project
        obj.save(update_fields=["project"])

    #set ingress's project to None if namespace's project is none
    for obj in models.Ingress.objects.filter(Q(namespace__isnull=True) | Q(namespace__project__isnull=True)).filter(project__isnull=False):
        obj.project = None
        obj.save(update_fields=["project"])

    #assign namespace's project to persistentvolumeclaim's project
    for obj in models.PersistentVolumeClaim.objects.filter(namespace__isnull=False,namespace__project__isnull=False).exclude(project=F("namespace__project")):
        obj.project = obj.namespace.project
        obj.save(update_fields=["project"])

    #set persistentvolumeclaim's project to None if namespace's project is none
    for obj in models.PersistentVolumeClaim.objects.filter(Q(namespace__isnull=True) | Q(namespace__project__isnull=True)).filter(project__isnull=False):
        obj.project = None
        obj.save(update_fields=["project"])


def check_project_property():
    """
    Check whether the namespace's project is the same as the project of workload, ingress and models.PersistentVolumeClaim, and print the result
    """
    objs = list(models.Workload.objects.filter(namespace__project__isnull=False).exclude(project=F("namespace__project")))
    objs += list(models.Workload.objects.filter(namespace__project__isnull=True).filter(project__isnull=False))
    if objs:
        logger.info("The following workloads'project are not equal with namespace's project.{}\n".format(["{}({})".format(o,o.id) for o in objs]))

    objs = list(models.Ingress.objects.filter(namespace__isnull=False,namespace__project__isnull=False).exclude(project=F("namespace__project")))
    objs += list(models.Ingress.objects.filter(Q(namespace__isnull=True) | Q(namespace__project__isnull=True)).filter(project__isnull=False))
    if objs:
        logger.info("The following ingresses'project are not equal with namespace's project.{}\n".format(["{}({})".format(o,o.id) for o in objs]))

    objs = list(models.PersistentVolumeClaim.objects.filter(namespace__isnull=False,namespace__project__isnull=False).exclude(project=F("namespace__project")))
    objs += list(models.PersistentVolumeClaim.objects.filter(Q(namespace__isnull=True) | Q(namespace__project__isnull=True)).filter(project__isnull=False))
    if objs:
        logger.info("The following models.PersistentVolumeClaims'project are not equal with namespace's project.{}\n".format(["{}({})".format(o,o.id) for o in objs]))

def check_workloads_property():
    """
    Check whether the active and deleted workloads is the same as the value of column 'active_workloads' and 'deleted_workloads' in model 'models.Namespace','models.Project' and 'models.Cluster' and print the result
    """
    for obj in models.Namespace.objects.all():
        active_workloads = models.Workload.objects.filter(namespace=obj,deleted__isnull=True).count()
        deleted_workloads = models.Workload.objects.filter(namespace=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            logger.info("models.Namespace({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))


    for obj in models.Project.objects.all():
        active_workloads = models.Workload.objects.filter(namespace__project=obj,deleted__isnull=True).count()
        deleted_workloads = models.Workload.objects.filter(namespace__project=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            logger.info("models.Project({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))

    for obj in models.Cluster.objects.all():
        active_workloads = models.Workload.objects.filter(cluster=obj,deleted__isnull=True).count()
        deleted_workloads = models.Workload.objects.filter(cluster=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            logger.info("models.Cluster({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))

def reset_workloads_property():
    """
    Update the column 'active_workoads' and 'deleted_workloads' in model 'models.Namespace', 'models.Project' and 'models.Cluster' to the active workloads and deleted workloads

    """
    for obj in models.Namespace.objects.all():
        active_workloads = models.Workload.objects.filter(namespace=obj,deleted__isnull=True).count()
        deleted_workloads = models.Workload.objects.filter(namespace=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            logger.info("models.Namespace({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))
            obj.active_workloads = active_workloads
            obj.deleted_workloads = deleted_workloads
            obj.save(update_fields=["active_workloads","deleted_workloads"])


    for obj in models.Project.objects.all():
        active_workloads = models.Workload.objects.filter(namespace__project=obj,deleted__isnull=True).count()
        deleted_workloads = models.Workload.objects.filter(namespace__project=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            logger.info("models.Project({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))
            obj.active_workloads = active_workloads
            obj.deleted_workloads = deleted_workloads
            obj.save(update_fields=["active_workloads","deleted_workloads"])

    for obj in models.Cluster.objects.all():
        active_workloads = models.Workload.objects.filter(cluster=obj,deleted__isnull=True).count()
        deleted_workloads = models.Workload.objects.filter(cluster=obj,deleted__isnull=False).count()
        if obj.active_workloads != active_workloads or obj.deleted_workloads != deleted_workloads:
            logger.info("models.Cluster({}<{}>): active_workloads={}, expected acrive_workloads={}; deleted_workloads={}, expected deleted_workloads={}".format(
                obj,
                obj.id,
                obj.active_workloads,
                active_workloads,
                obj.deleted_workloads,
                deleted_workloads
            ))
            obj.active_workloads = active_workloads
            obj.deleted_workloads = deleted_workloads
            obj.save(update_fields=["active_workloads","deleted_workloads"])


def _clean_containers():
    """
    clean all containers and container logs,
    sync projects and workloads
    """
    sync_workloads()
    models.ContainerLog.objects.all().delete()
    models.Container.objects.all().delete()
    models.Workload.objects.filter(added_by_log=True).delete()
    models.Namespace.objects.filter(added_by_log=True).delete()
    models.Cluster.objects.filter(added_by_log=True).delete()
    models.Workload.objects.all().update(deleted=None,latest_containers=None)
    sync_project()
    sync_workloads()

def clean_containers(sync=True):
    if sync:
        synchronize_logharvester(_clean_containers)()
    else:
        _clean_containers()


def _clean_containerlogs():
    """
    Clear all container logs
    """
    models.ContainerLog.objects.all().delete()
    models.Container.objects.all().update(log=False,warning=False,error=False)
    for workload in models.Workload.objects.all():
        if workload.latest_containers:
            for container in workload.latest_containers:
                container[2] = 0
            workload.save(update_fields=["latest_containers"])

def clean_containerlogs(sync=True):
    if sync:
        synchronize_logharvester(_clean_containerlogs)()
    else:
        _clean_containerlogs()


def clean_added_by_log_data():
    """
    Clean all the data which is added by log
    """
    deleted_rows = models.ContainerLog.objects.filter(container__workload__added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.Container.objects.filter(workload__added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.Ingress.objects.filter(namespace__added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.Workload.objects.filter(added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.PersistentVolume.objects.filter(cluster__added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.PersistentVolumeClaim.objects.filter(cluster__added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.ConfigMap.objects.filter(namespace__added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.Namespace.objects.filter(added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.Project.objects.filter(cluster__added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.Cluster.objects.filter(added_by_log=True).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def clean_expired_deleted_data():
    logger.info("Begin to clean expired deleted data")
    expired_time = timezone.now() - settings.DELETED_RANCHER_OBJECT_EXPIRED
    deleted_rows = models.ContainerLog.objects.filter(container__workload__deleted__lt=expired_time).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.Container.objects.filter(workload__deleted__lt=expired_time).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.Ingress.objects.filter(deleted__lt=expired_time).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.Workload.objects.filter(deleted__lt=expired_time).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


    deleted_rows = models.PersistentVolumeClaim.objects.filter(volume__deleted__lt=expired_time).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.PersistentVolume.objects.filter(deleted__lt=expired_time).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.Namespace.objects.filter(deleted__lt=expired_time).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def clean_expired_containers(cluster=None):
    if cluster:
        if isinstance(cluster,models.Cluster):
            cluster_qs = [cluster]
        else:
            try:
                cluster_qs = models.Cluster.objects.filter(id=int(cluster))
            except:
                cluster_qs = models.Cluster.objects.filter(name=str(cluster))
    else:
        cluster_qs = models.Cluster.objects.all().order_by("name")

    for cluster in cluster_qs:
        logger.info("Begin to clean expired containers of workloads in cluster({})".format(cluster))
        for workload in models.Workload.objects.filter(cluster=cluster).order_by("id"):
            logger.debug("Begin to clean expired containers for workload({})".format(workload))
            earliest_running_container = models.Container.objects.filter(cluster=cluster,workload=workload).filter(status__in=("running","waiting")).order_by("pod_created").first()
            if earliest_running_container:
                #found a running container
                non_expired_qs = models.Container.objects.filter(cluster=cluster,workload=workload,pod_created__lt=earliest_running_container.pod_created).order_by("-pod_created")[:settings.RANCHER_CONTAINERS_PER_WORKLOAD]
            else:
                non_expired_qs = models.Container.objects.filter(cluster=cluster,workload=workload).order_by("-pod_created")[:settings.RANCHER_CONTAINERS_PER_WORKLOAD]

            if non_expired_qs.count() < settings.RANCHER_CONTAINERS_PER_WORKLOAD:
                #all containers are not expired
                continue
            non_expired_ids = [o.id for  o in non_expired_qs]
            if earliest_running_container:
                deleted_rows = models.Container.objects.filter(cluster=cluster,workload=workload,pod_created__lt=earliest_running_container.pod_created).exclude(id__in=non_expired_ids).delete()
            else:
                deleted_rows = models.Container.objects.filter(cluster=cluster,workload=workload).exclude(id__in=non_expired_ids).delete()
            logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def clean_expired_containerlogs():
    expired_time = timezone.now() - settings.RANCHER_CONTAINERLOG_EXPIRED
    
    deleted_rows = models.ContainerLog.objects.filter(logtime__lt=expired_time).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def delete_cluster(idorname):
    """
    delete cluster
    """
    try:
        cluster = models.Cluster.objects.get(id=int(idorname))
    except:
        cluster = models.Cluster.objects.get(name=str(idorname))

    deleted_rows = models.ContainerLog.objects.filter(container__cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.Container.objects.filter(cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.Workload.objects.filter(cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.Ingress.objects.filter(cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.PersistentVolumeClaim.objects.filter(cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.PersistentVolume.objects.filter(cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.ConfigMap.objects.filter(cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))

    deleted_rows = models.Namespace.objects.filter(cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = models.Project.objects.filter(cluster=cluster).delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))
    deleted_rows = cluster.delete()
    logger.info("Delete {} objects. {}".format(deleted_rows[0]," , ".join( "{}={}".format(k,v) for k,v in deleted_rows[1].items())))


def clean_orphan_projects(cluster = None):
    """
    cluster can be 
      1. None: means all clusters
      2. models.Cluster instance
      3. models.Cluster id
      4. models.Cluster name
    """
    logger.info("Begin to clean orphan projects")
    if cluster:
        if isinstance(cluster,models.Cluster):
            qs = models.Project.objects.filter(cluster=cluster)
        else:
            try:
                qs = models.Project.objects.filter(cluster__id=int(cluster))
            except:
                qs - models.Project.objects.filter(cluster__name=cluster)
    else:
        qs = models.Project.objects.all()

    deleted_projects = []
    for project in qs:
        exists = False
        for cls in (models.Namespace,models.PersistentVolumeClaim,models.Ingress,models.Workload):
            if cls.objects.filter(project=project).exists():
                exists = True
                break
        if not exists:
            deleted_projects.append(project)


    if deleted_projects:
        logger.info("There are {} orphan projects,({}). try to delete them ".format(len(deleted_projects)," , ".join(str(p) for p in deleted_projects)))
        for project in deleted_projects:
            project.delete()
    else:
        logger.info("No orphan projects are found.")


def clean_orphan_namespaces(cluster = None):
    """
    cluster can be 
      1. None: means all clusters
      2. models.Cluster instance
      3. models.Cluster id
      4. models.Cluster name
    """
    logger.info("Begin to clean orphan namespaces")
    if cluster:
        if isinstance(cluster,models.Cluster):
            qs = models.Namespace.objects.filter(cluster=cluster)
        else:
            try:
                qs = models.Namespace.objects.filter(cluster__id=int(cluster))
            except:
                qs - models.Namespace.objects.filter(cluster__name=cluster)
    else:
        qs = models.Namespace.objects.all()

    deleted_namespaces = []
    for namespace in qs:
        exists = False
        for cls in (models.ConfigMap,models.PersistentVolumeClaim,models.Ingress,models.Workload,models.Container):
            if cls.objects.filter(namespace=namespace).exists():
                exists = True
                break
        if not exists:
            deleted_namespaces.append(namespace)


    if deleted_namespaces:
        logger.info("There are {} orphan namespaces,({}). try to delete them ".format(len(deleted_namespaces)," , ".join(str(p) for p in deleted_namespaces)))
        for namespace in deleted_namespaces:
            namespace.delete()
    else:
        logger.info("No orphan namespaces are found.")

def check_aborted_harvester():
    now = timezone.now()
    abort_time = now - settings.HARVESTER_ABORTED
    models.Harvester.objects.filter(status=models.Harvester.RUNNING,last_heartbeat__lt=abort_time).update(status=models.Harvester.ABORTED,message="Harvester exited abnormally.",endtime=now)

def clean_expired_harvester():
    expired_time = timezone.now() - settings.HARVESTER_EXPIRED
    models.Harvester.objects.filter(starttime__lt=expired_time).delete()
