import json
import os
import traceback
import logging
from collections import OrderedDict

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models,transaction
from django.utils import timezone
from django.http import QueryDict

from data_storage import HistoryDataConsumeClient,LocalStorage
from data_storage.utils import acquire_runlock,release_runlock
from .models import WebAppAccessLog,WebApp,WebAppLocation,RequestParameterFilter,WebAppAccessDailyLog,RequestPathNormalizer,apply_rules,WebAppAccessDailyReport

logger = logging.getLogger(__name__)

_consume_client = None
def get_consume_client():
    """
    Return the blob resource client
    """
    global _consume_client
    if _consume_client is None:
        _consume_client = HistoryDataConsumeClient(
            LocalStorage(settings.NGINXLOG_REPOSITORY_DIR),
            settings.NGINXLOG_RESOURCE_NAME,
            settings.NGINXLOG_RESOURCE_CLIENTID,
            max_saved_consumed_resources=settings.NGINXLOG_MAX_SAVED_CONSUMED_RESOURCES
        )
    return _consume_client

def process_log_file(context,metadata,config_file):
    with open(config_file,"r") as f:
        log_records = json.loads(f.read())

    for record in log_records:
        try:
            if "?" in record["request_path"]:
                request_path,path_parameters = record["request_path"].split("?",1)
                if path_parameters:
                    path_parameters = path_parameters.replace("%00","").replace("\x00","")
                    path_parameters = [(k,v[0] if len(v) == 1 else v) for k,v in QueryDict(path_parameters).lists()]
                    path_parameters.sort(key=lambda o:o[0].lower())
                    all_path_parameters = [o[0] for o in path_parameters]
                    path_parameters = WebAppAccessLog.to_path_parameters(path_parameters)
            else:
                request_path = record["request_path"]
                path_parameters = None
                all_path_parameters = None

            try:
                http_status = int(record["http_status"])
            except:
                http_status = 0

    
            parameters_changed,path_parameters = RequestParameterFilter.filter_parameters(
                record["webserver"],
                request_path,
                path_parameters,
                parameter_filters=context["parameter_filters"],
                parameter_filter_map=context["parameter_filter_map"]
            )

            path_changed,request_path = RequestPathNormalizer.normalize_path(
                record["webserver"],
                request_path,
                path_normalizers=context["path_normalizers"],
                path_normalizer_map=context["path_normalizer_map"]
            )
            accesslog = WebAppAccessLog.objects.filter(
                log_starttime = metadata["archive_starttime"],
                webserver = record["webserver"],
                request_path = request_path,
                http_status = http_status,
                path_parameters = path_parameters
            ).first()

            if accesslog:
                accesslog.requests += int(record["requests"])
                accesslog.total_response_time += float(record["total_response_time"])
                if accesslog.max_response_time < float(record["max_response_time"]):
                    accesslog.max_response_time = float(record["max_response_time"])
    
                if accesslog.min_response_time > float(record["min_response_time"]):
                    accesslog.min_response_time = float(record["min_response_time"])
    
                accesslog.avg_response_time = accesslog.total_response_time / accesslog.requests
                if all_path_parameters:
                    if accesslog.all_path_parameters:
                        changed = False
                        for param in all_path_parameters:
                            if param not in accesslog.all_path_parameters:
                                accesslog.all_path_parameters.append(param)
                                changed = True
                        if changed:
                            accesslog.all_path_parameters.sort()
                    else:
                        accesslog.all_path_parameters = all_path_parameters
            else:
                accesslog = WebAppAccessLog(
                    log_starttime = metadata["archive_starttime"],
                    log_endtime = metadata["archive_endtime"],
                    webserver = record["webserver"],
                    request_path = request_path,
                    http_status = http_status,
                    path_parameters = path_parameters,
                    all_path_parameters = all_path_parameters,
                    requests = int(record["requests"]),
                    max_response_time = float(record["max_response_time"]),
                    min_response_time = float(record["min_response_time"]),
                    avg_response_time = float(record["avg_response_time"]),
                    total_response_time = float(record["total_response_time"])
                )
            if accesslog.webserver not in context.get("webapps",{}):
                if "webapps" not in context:
                    context["webapps"] = {}
                context["webapps"][accesslog.webserver] = WebApp.objects.filter(name=accesslog.webserver).first()
            accesslog.webapp = context["webapps"][accesslog.webserver]
    
            if accesslog.webapp and not accesslog.webapp.redirect_to and not accesslog.webapp.redirect_to_other:
                if accesslog.webapp not in context.get("webapplocations",{}):
                    if "webapplocations" not in context:
                        context["webapplocations"] = {}
                    context["webapplocations"][accesslog.webapp] = list(WebAppLocation.objects.filter(app=accesslog.webapp).order_by("-score"))
                accesslog.webapplocation = accesslog.webapp.get_matched_location(accesslog.request_path,context["webapplocations"][accesslog.webapp])
                if not accesslog.webapplocation and accesslog.http_status < 400 and accesslog.http_status > 0:
                    raise Exception("Can't find the app location for request path({1}) in web application({0})".format(accesslog.webapp,accesslog.request_path))
            accesslog.save()
        except Exception as ex:
            logger.error("Failed to parse the nginx access log record({}).{}".format(record,traceback.format_exc()))
            raise Exception("Failed to parse the nginx access log record({}).{}".format(record,str(ex)))
            

def process_log(context):
    def _func(status,metadata,config_file):
        if status != HistoryDataConsumeClient.NEW:
            raise Exception("The status of the consumed history data shoule be New, but currently consumed histroy data's status is {},metadata={}".format(
                get_consume_client().get_consume_status_name(status),
                metadata
            ))
        WebAppAccessLog.objects.filter(log_starttime = metadata["archive_starttime"]).delete()
        with transaction.atomic():
            process_log_file(context,metadata,config_file)

    return _func
                        
def harvest(reconsume=False):
    lock_file = os.path.join(settings.NGINXLOG_REPOSITORY_DIR,settings.NGINXLOG_RESOURCE_NAME,"{}.lock".format(settings.NGINXLOG_RESOURCE_CLIENTID))

    acquire_runlock(lock_file)
    try:
        if reconsume and get_consume_client().is_client_exist(clientid=settings.NGINXLOG_RESOURCE_CLIENTID):
            get_consume_client().delete_clients(clientid=settings.NGINXLOG_RESOURCE_CLIENTID)
    
        if reconsume:
            WebAppAccessLog.objects.all().delete()
            WebAppAccessDailyLog.objects.all().delete()
    
        context = {
            "reconsume":reconsume,
        }
        #apply the latest filter change first
        applied = False
        while not applied:
            context["path_normalizers"] = list(RequestPathNormalizer.objects.all().order_by("-order"))
            context["path_normalizer_map"] = {}
            context["parameter_filters"] = list(RequestParameterFilter.objects.all().order_by("-order"))
            context["parameter_filter_map"] = {}
            applied = apply_rules(context)
    
        #consume nginx config file
        result = get_consume_client().consume(process_log(context))

        WebAppAccessDailyLog.populate_data()
        WebAppAccessDailyReport.populate_data()

        return result

    finally:
        release_runlock(lock_file)
        


