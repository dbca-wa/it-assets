import simdjson
import re
import os
import traceback
import logging
from collections import OrderedDict

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models,transaction
from django.utils import timezone
from django.http import QueryDict

from data_storage import HistoryDataConsumeClient,LocalStorage,exceptions
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

class LogRecordIterator(object):
    block_size = 1024 * 512 #read 512 k
    def __init__(self,input_file):
        self._input_file = input_file
        self._f = None
        self._index = None
        self._data_block = None
        self._read = True

    def _close(self):
        try:
            if self._f:
                self._f.close()
        except :
            pass
        finally:
            self._f = None

    first_record_start_re = re.compile("^\s*\[\s*\{\s*\n")
    record_sep_re = re.compile("\n\s*}\s*,\s*{\s*\n")
    last_record_end_re = re.compile("\n\s*}\s*\,?\s*\]\s*$")
    def _next_record(self):
        if not self._f:
            raise StopIteration("No more records")
        
        while (self._f):
            if self._read:
                data = self._f.read(self.block_size)
                self._read = False
                if data:
                    if self._data_block:
                        self._data_block += data
                    else:
                        self._data_block = data
                else:
                    #end of file
                    self._close()
                    if self._data_block:
                        m = self.last_record_end_re.search(self._data_block)
                        if m:
                            self._index += 1
                            json_str = "{{\n{}\n}}".format(self._data_block[:m.start()])
                            self._data_block = None
                            return simdjson.loads(json_str)
                        else:
                            raise Exception("The last record is incomplete in nginx access log file({}).".format(self._input_file))
                    else:
                        raise StopIteration("No more records")

            if self._index is None:
                m = self.first_record_start_re.search(self._data_block)
                if m:
                    self._data_block = self._data_block[m.end():]
                    self._index = -1
                elif self._data_block.strip():
                    raise Exception("The nginx access log file({}) is an invalid json file".format(self._input_file))
                else:
                    self._data_block = None
                    self._read = True
            else:
                m = self.record_sep_re.search(self._data_block)
                if m:
                    self._index += 1
                    json_str = "{{\n{}\n}}".format(self._data_block[:m.start()])
                    self._data_block = self._data_block[m.end():]
                    return simdjson.loads(json_str)
                else:
                    self._read = True

    def __iter__(self):
        self._close()

        self._index = None
        self._data_block = None
        self._read = True

        self._f = open(self._input_file,'r')
        return self

    def __next__(self):
        return self._next_record()

def to_float(data):
    try:
        return float(data)
    except:
        return 0

def process_log_file(context,metadata,log_file):
    if settings.NGINXLOG_STREAMING_PARSE:
        log_records = LogRecordIterator(log_file)
    else:
        with open(log_file,"r") as f:
            log_records = simdjson.loads(f.read())

    records = 0
    webserver_records = {}
    webserver = None
    key = None
    original_request_path = None
    for record in log_records:
        records += 1
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

            original_request_path = request_path
            if not request_path:
                request_path = "/"
                original_request_path = request_path
            elif len(request_path) > 512:
                request_path = request_path[0:512]
    
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
                path_normalizer_map=context["path_normalizer_map"],
                path_filter=context["path_filter"]
            )
            if request_path is None:
                continue

            if webserver :
                if record["webserver"] != webserver:
                    for log_record in webserver_records.values():
                        log_record.save()
                    webserver_records.clear()
                    webserver = record["webserver"]
            else:
                webserver = record["webserver"]
            

            key = (request_path,http_status,path_parameters)

            accesslog = webserver_records.get(key)
            if accesslog:
                accesslog.requests += int(record["requests"])
                accesslog.total_response_time += to_float(record["total_response_time"])
                if accesslog.max_response_time < to_float(record["max_response_time"]):
                    accesslog.max_response_time = to_float(record["max_response_time"])
    
                if accesslog.min_response_time > to_float(record["min_response_time"]):
                    accesslog.min_response_time = to_float(record["min_response_time"])
    
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
                    max_response_time = to_float(record["max_response_time"]),
                    min_response_time = to_float(record["min_response_time"]),
                    total_response_time = to_float(record["total_response_time"])
                )
                accesslog.avg_response_time = accesslog.total_response_time / accesslog.requests
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
                    accesslog.webapplocation = accesslog.webapp.get_matched_location(original_request_path,context["webapplocations"][accesslog.webapp])
                    if not accesslog.webapplocation and accesslog.http_status < 300 and accesslog.http_status >= 200:
                        logger.warning("Can't find the app location for request path({1}) in web application({0})".format(accesslog.webapp,accesslog.request_path))
                webserver_records[key] = accesslog
        except Exception as ex:
            #delete already added records from this log file
            WebAppAccessLog.objects.filter(log_starttime = metadata["archive_starttime"]).delete()
            logger.error("Failed to parse the nginx access log record({}).{}".format(record,traceback.format_exc()))
            raise Exception("Failed to parse the nginx access log record({}).{}".format(record,str(ex)))

    for log_record in webserver_records.values():
        log_record.save()

    logger.info("Harvest {1} records from log file '{0}'".format(log_file,records))
            

def process_log(context):
    def _func(status,metadata,log_file):
        if status != HistoryDataConsumeClient.NEW:
            raise Exception("The status of the consumed history data shoule be New, but currently consumed histroy data's status is {},metadata={}".format(
                get_consume_client().get_consume_status_name(status),
                metadata
            ))
        WebAppAccessLog.objects.filter(log_starttime = metadata["archive_starttime"]).delete()
        process_log_file(context,metadata,log_file)

        context["renew_lock_time"] = context["f_renew_lock"](context["renew_lock_time"])

    return _func
                        
def harvest(reconsume=False):
    try:
        renew_lock_time = get_consume_client().acquire_lock(expired=settings.NGINXLOG_MAX_CONSUME_TIME_PER_LOG)
    except exceptions.AlreadyLocked as ex: 
        msg = "The previous harvest process is still running.{}".format(str(ex))
        logger.info(msg)
        return ([],[(None,None,None,msg)])
        
    try:
        if reconsume and get_consume_client().is_client_exist(clientid=settings.NGINXLOG_RESOURCE_CLIENTID):
            get_consume_client().delete_clients(clientid=settings.NGINXLOG_RESOURCE_CLIENTID)
    
        if reconsume:
            WebAppAccessLog.objects.all().delete()
            WebAppAccessDailyLog.objects.all().delete()
    
        context = {
            "reconsume":reconsume,
            "renew_lock_time":renew_lock_time,
            "f_renew_lock":get_consume_client().renew_lock
        }
        #apply the latest filter change first
        applied = False
        while not applied:
            context["path_normalizers"] = list(RequestPathNormalizer.objects.all().order_by("-order"))
            context["path_filter"] = RequestPathNormalizer.objects.filter(order=0).first()
            context["path_normalizer_map"] = {}
            context["parameter_filters"] = list(RequestParameterFilter.objects.all().order_by("-order"))
            context["parameter_filter_map"] = {}
            applied = apply_rules(context)
    
        #consume nginx config file
        result = get_consume_client().consume(process_log(context))

        renew_lock_time = WebAppAccessDailyLog.populate_data(context["f_renew_lock"],context["renew_lock_time"])
        WebAppAccessDailyReport.populate_data(context["f_renew_lock"],renew_lock_time)

        return result

    finally:
        get_consume_client().release_lock()
        


