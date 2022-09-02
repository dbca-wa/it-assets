import json
import traceback
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.http import QueryDict

from data_storage import HistoryDataConsumeClient, LocalStorage, exceptions, LockSession
from .models import (
    WebAppAccessLog,
    WebApp,
    WebAppLocation,
    RequestParameterFilter,
    WebAppAccessDailyLog,
    RequestPathNormalizer,
    apply_rules,
    WebAppAccessDailyReport,
)
from itassets.utils import LogRecordIterator

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
            settings.RESOURCE_CLIENTID,
            max_saved_consumed_resources=settings.NGINXLOG_MAX_SAVED_CONSUMED_RESOURCES,
        )
    return _consume_client


def to_float(data):
    try:
        return float(data)
    except:
        return 0


def process_log_file(context, metadata, log_file):
    if settings.NGINXLOG_STREAMING_PARSE:
        log_records = LogRecordIterator(log_file)
    else:
        with open(log_file, "r") as f:
            log_records = json.loads(f.read())

    records = 0
    webserver_records = {}
    webserver = None
    key = None
    original_request_path = None
    for record in log_records:
        records += 1
        try:
            if "?" in record["request_path"]:
                request_path, path_parameters = record["request_path"].split("?", 1)
                if path_parameters:
                    path_parameters = path_parameters.replace("%00", "").replace(
                        "\x00", ""
                    )
                    path_parameters = [
                        (k, v[0] if len(v) == 1 else v)
                        for k, v in QueryDict(path_parameters).lists()
                    ]
                    path_parameters.sort(key=lambda o: o[0].lower())
                    all_path_parameters = [o[0] for o in path_parameters]
                    path_parameters = WebAppAccessLog.to_path_parameters(
                        path_parameters
                    )
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

            (
                parameters_changed,
                path_parameters,
            ) = RequestParameterFilter.filter_parameters(
                record["webserver"],
                request_path,
                path_parameters,
                parameter_filters=context["parameter_filters"],
                parameter_filter_map=context["parameter_filter_map"],
            )

            path_changed, request_path = RequestPathNormalizer.normalize_path(
                record["webserver"],
                request_path,
                path_normalizers=context["path_normalizers"],
                path_normalizer_map=context["path_normalizer_map"],
                path_filter=context["path_filter"],
            )
            if request_path is None:
                continue

            if webserver:
                if record["webserver"] != webserver:
                    for log_record in webserver_records.values():
                        log_record.save()
                    webserver_records.clear()
                    webserver = record["webserver"]
            else:
                webserver = record["webserver"]

            key = (request_path, http_status, path_parameters)

            accesslog = webserver_records.get(key)
            if accesslog:
                accesslog.requests += int(record["requests"])
                accesslog.total_response_time += to_float(record["total_response_time"])
                if accesslog.max_response_time < to_float(record["max_response_time"]):
                    accesslog.max_response_time = to_float(record["max_response_time"])

                if accesslog.min_response_time > to_float(record["min_response_time"]):
                    accesslog.min_response_time = to_float(record["min_response_time"])

                accesslog.avg_response_time = (
                    accesslog.total_response_time / accesslog.requests
                )
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
                    log_starttime=metadata["archive_starttime"],
                    log_endtime=metadata["archive_endtime"],
                    webserver=record["webserver"],
                    request_path=request_path,
                    http_status=http_status,
                    path_parameters=path_parameters,
                    all_path_parameters=all_path_parameters,
                    requests=int(record["requests"]),
                    max_response_time=to_float(record["max_response_time"]),
                    min_response_time=to_float(record["min_response_time"]),
                    total_response_time=to_float(record["total_response_time"]),
                )
                accesslog.avg_response_time = (
                    accesslog.total_response_time / accesslog.requests
                )
                if accesslog.webserver not in context.get("webapps", {}):
                    if "webapps" not in context:
                        context["webapps"] = {}
                    context["webapps"][accesslog.webserver] = WebApp.objects.filter(
                        name=accesslog.webserver
                    ).first()
                accesslog.webapp = context["webapps"][accesslog.webserver]

                if (
                    accesslog.webapp
                    and not accesslog.webapp.redirect_to
                    and not accesslog.webapp.redirect_to_other
                ):
                    if accesslog.webapp not in context.get("webapplocations", {}):
                        if "webapplocations" not in context:
                            context["webapplocations"] = {}
                        context["webapplocations"][accesslog.webapp] = list(
                            WebAppLocation.objects.filter(
                                app=accesslog.webapp
                            ).order_by("-score")
                        )
                    accesslog.webapplocation = accesslog.webapp.get_matched_location(
                        original_request_path,
                        context["webapplocations"][accesslog.webapp],
                    )
                    if (
                        not accesslog.webapplocation
                        and accesslog.http_status < 300
                        and accesslog.http_status >= 200
                    ):
                        logger.warning(
                            "Can't find the app location for request path({1}) in web application({0})".format(
                                accesslog.webapp, accesslog.request_path
                            )
                        )
                webserver_records[key] = accesslog
        except Exception as ex:
            # delete already added records from this log file
            WebAppAccessLog.objects.filter(
                log_starttime=metadata["archive_starttime"]
            ).delete()
            logger.error(
                "Failed to parse the nginx access log record({}).{}".format(
                    record, traceback.format_exc()
                )
            )
            raise Exception(
                "Failed to parse the nginx access log record({}).{}".format(
                    record, str(ex)
                )
            )

    for log_record in webserver_records.values():
        log_record.save()

    logger.info("Harvest {1} records from log file '{0}'".format(log_file, records))


def process_log(context):
    def _func(status, metadata, log_file):
        if status != HistoryDataConsumeClient.NEW:
            raise Exception(
                "The status of the consumed history data shoule be New, but currently consumed histroy data's status is {},metadata={}".format(
                    get_consume_client().get_consume_status_name(status), metadata
                )
            )
        WebAppAccessLog.objects.filter(
            log_starttime=metadata["archive_starttime"]
        ).delete()
        process_log_file(context, metadata, log_file)

        context["lock_session"].renew()

    return _func


def harvest(reconsume=False):
    try:
        with LockSession(
            get_consume_client(), settings.NGINXLOG_MAX_CONSUME_TIME_PER_LOG
        ) as lock_session:
            if reconsume and get_consume_client().is_client_exist(
                clientid=settings.RESOURCE_CLIENTID
            ):
                get_consume_client().delete_clients(clientid=settings.RESOURCE_CLIENTID)

            if reconsume:
                WebAppAccessLog.objects.all().delete()
                WebAppAccessDailyLog.objects.all().delete()

            context = {"reconsume": reconsume, "lock_session": lock_session}
            # apply the latest filter change first
            context["path_normalizers"] = list(
                RequestPathNormalizer.objects.filter(order__gt=0).order_by("-order")
            )
            context["path_filter"] = RequestPathNormalizer.objects.filter(
                order=0
            ).first()
            context["parameter_filters"] = list(
                RequestParameterFilter.objects.all().order_by("-order")
            )
            context["path_normalizer_map"] = {}
            context["parameter_filter_map"] = {}
            """
            don't apply the changed rules in the history data
            applied = False
            while not applied:
                context["path_normalizers"] = list(RequestPathNormalizer.objects.filter(order__gt=0).order_by("-order"))
                context["path_filter"] = RequestPathNormalizer.objects.filter(order=0).first()
                context["path_normalizer_map"] = {}
                context["parameter_filters"] = list(RequestParameterFilter.objects.all().order_by("-order"))
                context["parameter_filter_map"] = {}
                applied = apply_rules(context)
            """

            # consume nginx config file
            result = get_consume_client().consume(process_log(context))
            # populate daily log
            lock_session.renew()
            # populate daily report
            WebAppAccessDailyReport.populate_data(lock_session)

            now = timezone.localtime()
            if now.hour >= 0 and now.hour <= 2:
                obj = WebAppAccessLog.objects.all().order_by("-log_starttime").first()
                if obj:
                    last_log_datetime = timezone.localtime(obj.log_starttime)
                    earliest_log_datetime = timezone.make_aware(
                        datetime(
                            last_log_datetime.year,
                            last_log_datetime.month,
                            last_log_datetime.day,
                        )
                    ) - timedelta(days=settings.NGINXLOG_ACCESSLOG_LIFETIME)
                    sql = "DELETE FROM nginx_webappaccesslog where log_starttime < '{}'".format(
                        earliest_log_datetime.strftime("%Y-%m-%d 00:00:00 +8:00")
                    )
                    with connection.cursor() as cursor:
                        logger.info(
                            "Delete expired web app access log.last_log_datetime={}, sql = {}".format(
                                last_log_datetime, sql
                            )
                        )
                        cursor.execute(sql)
                    lock_session.renew()

                obj = WebAppAccessDailyLog.objects.all().order_by("-log_day").first()
                if obj:
                    last_log_day = obj.log_day
                    earliest_log_day = last_log_day - timedelta(
                        days=settings.NGINXLOG_ACCESSDAILYLOG_LIFETIME
                    )
                    sql = "DELETE FROM nginx_webappaccessdailylog where log_day < date('{}')".format(
                        earliest_log_day.strftime("%Y-%m-%d")
                    )
                    with connection.cursor() as cursor:
                        logger.info(
                            "Delete expired web app access daily log.last_log_day={}, sql = {}".format(
                                last_log_day, sql
                            )
                        )
                        cursor.execute(sql)

            return result
    except exceptions.AlreadyLocked as ex:
        msg = "The previous harvest process is still running.{}".format(str(ex))
        logger.info(msg)
        return ([], [(None, None, None, msg)])
