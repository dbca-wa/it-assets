import re
import os
import imp
import logging
from datetime import datetime,timedelta

from django.core.exceptions import ValidationError
from django.db import models,transaction
from django.contrib.postgres.fields import ArrayField
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings

from itassets.models import OriginalConfigMixin
from registers.models import ITSystem
from rancher.models import Cluster, Workload, WorkloadListening
from status.models import Host

logger = logging.getLogger(__name__)


class Domain(models.Model):
    name = models.CharField(max_length=64, unique=True)
    level = models.PositiveSmallIntegerField(editable=False)
    score = models.BigIntegerField(unique=True, editable=False)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        editable=False,
    )
    desc = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        db_obj = Domain.objects.get(pk=self.pk) if self.pk else None
        self.name = self.name.strip()
        self.level = len(self.name.split("."))
        parent_domain = None
        if self.level > 9:
            raise Exception("The maximum level of a domain is 9")
        elif self.level > 1:
            parent_name = self.name.split(".", 1)[1]
            self.parent = Domain.objects.filter(name=parent_name).first()
            if not self.parent:
                self.parent = Domain(name=parent_name)
                self.parent.save()

            self.parent_id = self.parent.id

        if self.score and (
            self.level == 1 or (db_obj and self.parent == db_obj.parent)
        ):
            # score already populated.
            pass
        else:
            if self.level == 1:
                last_sibling = (
                    Domain.objects.filter(level=self.level).order_by("-score").first()
                )
            else:
                last_sibling = (
                    Domain.objects.filter(parent=self.parent, level=self.level)
                    .order_by("-score")
                    .first()
                )

            if last_sibling:
                self.score = last_sibling.score + pow(100, 9 - self.level)
            elif self.parent:
                self.score = self.parent.score + pow(100, 9 - self.level)
            else:
                self.score = pow(100, 9 - self.level)

        result = super().save(*args, **kwargs)
        logger.debug(
            "Create domain(name={},level={},score={},parent={})".format(
                self.name, self.level, self.score, self.parent
            )
        )
        return result

    def __str__(self):
        return self.name


class SystemAlias(models.Model):
    system = models.ForeignKey(
        ITSystem, on_delete=models.PROTECT, related_name="alias", null=True, blank=True
    )
    name = models.CharField(max_length=64, unique=True)
    desc = models.TextField(null=True, blank=True)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    url_re = re.compile(
        "^((https|http):\/\/)?(www\.)?(?P<host>[a-zA-Z0-9\-\_]+(\.[a-zA-Z0-9]+)*)(\/.*)?$",
        re.IGNORECASE,
    )
    ip_re = re.compile("^[0-9]{1,3}(\.[0-9]{1,3}){3,3}$")

    @classmethod
    def create_default_alias(cls):
        for system in ITSystem.objects.filter(link__isnull=False):
            url = system.link.strip()
            if not url:
                continue
            # get the system default name
            m = cls.url_re.search(url)
            if not m:
                logger.warning("Can't parse url({})".format(url))
                continue

            name = m.group("host")
            domains = [
                "dpaw.wa.gov.au",
                "dbca.wa.gov.au",
                "der.wa.gov.au",
                "dec.wa.gov.au",
                "wa.gov.au",
                "com.au",
                "google.com",
                "riverguardians.com",
                "ascenderpay.com",
                "arcgis.com",
                "apple.com",
                "com",
                "org.au",
                "corporateict.domain",
            ]
            domain = None
            for d in domains:
                if name.endswith(d):
                    name = name[: (len(d) + 1) * -1]
                    domain = d
                    break
            if not domain:
                # domain not found
                if cls.ip_re.search(name):
                    # ip address
                    logger.info(
                        "The host({2}) of the system({0},link={1}) is ip address, ignore".format(
                            system.name, url, name
                        )
                    )
                    continue
                elif "." in name:
                    name, domain = name.split(".", 1)
            elif not name:
                name, domain = domain.split(".", 1)

            # remove the env from name if have
            for e in ("-uat", "-dev", "-prod"):
                if name.endswith(e):
                    name = name[: -1 * len(e)]
                    break

            if domain:
                if not Domain.objects.filter(name=domain).exists():
                    Domain(name=domain).save()

            system_alias = SystemAlias.objects.filter(name=name).first()
            if system_alias:
                if not system_alias.system:
                    system_alias.system = system
                    system_alias.save(update_fields=["system"])
            else:
                logger.debug(
                    "Create the alias name({2}) of the system({0},link={1})".format(
                        system.name, url, name
                    )
                )
                SystemAlias(
                    system=system, name=name, desc="System's default name"
                ).save()

    def __str__(self):
        if self.system:
            return "{} ({})".format(self.name, self.system.name)
        else:
            return self.name


class SystemEnv(models.Model):
    name = models.CharField(max_length=64, unique=True)
    desc = models.TextField(null=True, blank=True)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class WebApp(OriginalConfigMixin, models.Model):
    SSO_AUTH_NOT_REQUIRED = 0
    SSO_AUTH_TO_DBCA = 11
    SSO_AUTH_TO_DPAW = 12
    SSO_AUTH_TO_UAT = 13

    SSO_AUTH_DOMAINS = (
        (SSO_AUTH_TO_DBCA, "DBCA"),
        (SSO_AUTH_TO_DPAW, "DPAW"),
        (SSO_AUTH_TO_UAT, "UAT"),
        (SSO_AUTH_NOT_REQUIRED, "-"),
    )

    name = models.CharField(max_length=128, unique=True, editable=False)
    system_alias = models.ForeignKey(
        SystemAlias, on_delete=models.PROTECT, related_name="webapps"
    )
    system_env = models.ForeignKey(
        SystemEnv, on_delete=models.PROTECT, related_name="webapps", null=True
    )
    domain = models.ForeignKey(
        Domain, on_delete=models.PROTECT, related_name="webapps", null=True, blank=True
    )
    redirect_to = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="redirect_from",
        null=True,
        editable=False,
    )
    redirect_to_other = models.CharField(max_length=128, editable=False, null=True)
    redirect_path = models.CharField(max_length=128, editable=False, null=True)
    configure_txt = models.TextField(editable=False)
    auth_domain = models.PositiveSmallIntegerField(
        editable=False, choices=SSO_AUTH_DOMAINS
    )
    modified = models.DateTimeField(auto_now=True)
    config_modified = models.DateTimeField(null=True, editable=False)
    config_changed_columns = ArrayField(
        models.CharField(max_length=128, null=False, blank=False),
        null=True,
        editable=False,
    )
    created = models.DateTimeField(auto_now_add=True)

    @property
    def redirect(self):
        if self.redirect_to or self.redirect_to_other:
            if self.redirect_path:
                return "{}{}".format(
                    self.redirect_to or self.redirect_to_other, self.redirect_path
                )
            else:
                return self.redirect_to or self.redirect_to_other
        else:
            return ""

    def set_location_score(self):
        locations = list(WebAppLocation.objects.filter(app=self))
        #set the score for exact location, non regex location, and prefix location
        for location in locations:
            location.score = WebAppLocation.LOCATION_SCORES[location.location_type] * 1000 + len(location.location)
            location.save(update_fields=["score"])

    def get_matched_location(self,request_path,locations=None):
        """
        locations: all locations belonging to a webapp and also order by score desc
        """
        locations = locations or WebAppLocation.objects.filter(app=self).order_by("-score")
        saved_location = None
        saved_matched_path = None
        saved_regex_location = None
        saved_regex_matched_path = None
        for location in locations:
            if location.location_type != WebAppLocation.PREFIX_LOCATION or not saved_location: 
                matched,matched_path = location.is_match(request_path)
            if matched:
                if location.location_type in (WebAppLocation.EXACT_LOCATION,WebAppLocation.NON_REGEX_LOCATION):
                    return location
                elif location.location_type == WebAppLocation.PREFIX_LOCATION:
                    saved_location = location
                    saved_matched_path = matched_path
                elif saved_location:
                    if matched_path.startswith(saved_matched_path):
                        if not saved_regex_location or not saved_regex_matched_path.startswith(saved_matched_path) or len(saved_regex_matched_path) < len(matched_path):
                            saved_regex_location = location
                            saved_regex_matched_path = matched_path
                    elif saved_regex_location:
                        if saved_regex_matched_path.startswith(saved_matched_path):
                            pass
                        elif len(saved_regex_matched_path) < len(matched_path):
                            saved_regex_location = location
                            saved_regex_matched_path = matched_path
                    else:
                        saved_regex_location = location
                        saved_regex_matched_path = matched_path
                elif saved_regex_location:
                    if request_path.startswith(saved_regex_matched_path):
                        if request_path.startswith(matched_path) and len(matched_path) > len(saved_regex_matched_path):
                            saved_regex_location = location
                            saved_regex_matched_path = matched_path
                    elif request_path.startswith(matched_path) :
                        saved_regex_location = location
                        saved_regex_matched_path = matched_path
                    elif len(matched_path) > len(saved_regex_matched_path):
                        saved_regex_location = location
                        saved_regex_matched_path = matched_path
                else:
                    saved_regex_location = location
                    saved_regex_matched_path = matched_path

        return saved_regex_location or saved_location

    @classmethod
    def set_all_location_score(cls):
        for app in cls.objects.all():
            app.set_location_score()


    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class WebAppListen(models.Model):
    app = models.ForeignKey(
        WebApp, on_delete=models.CASCADE, related_name="listens", editable=False
    )
    listen_host = models.CharField(max_length=128, editable=False)
    listen_port = models.PositiveIntegerField(editable=False)
    https = models.BooleanField(default=False, editable=False)
    configure_txt = models.CharField(max_length=256, editable=False)
    modified = models.DateTimeField(auto_now=True)
    config_modified = models.DateTimeField(null=True, editable=False)
    config_changed_columns = ArrayField(
        models.CharField(max_length=128, null=False, blank=False),
        null=True,
        editable=False,
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "{}:{}{}".format(
            self.listen_host, self.listen_port, " ssl" if self.https else ""
        )

    class Meta:
        unique_together = [["app", "listen_host", "listen_port"]]


class WebServer(models.Model):
    AWS_SERVER = 1
    RANCHER_CLUSTER = 2
    DOCKER_SERVER = 4
    WEB_SERVER = 3
    EXTERNAL_SERVER = 5
    SERVER_CATEGORIES = (
        (AWS_SERVER, "AWS Server"),
        (RANCHER_CLUSTER, "Rancher Cluster"),
        (DOCKER_SERVER, "Docker Server"),
        (WEB_SERVER, "Web Server"),
        (EXTERNAL_SERVER, "External Server"),
    )

    IP_ADDRESS_RE = re.compile("^[0-9]{1,3}(\.[0-9]{1,3}){3}$")

    name = models.CharField(max_length=128, unique=True)
    category = models.PositiveSmallIntegerField(choices=SERVER_CATEGORIES, null=True)
    other_names = ArrayField(
        models.CharField(max_length=128), editable=False, null=True
    )
    desc = models.TextField(null=True, blank=True)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    host = models.ForeignKey(
        Host,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webservers",
        help_text="The equivalent Host object in the status application.",
    )

    @property
    def hostname(self):
        return self.get_hostname(self.name)

    @classmethod
    def get_hostname(cls, name):
        if cls.IP_ADDRESS_RE.search(name):
            return name
        else:
            for domain in (".corporateict.domain", ".lan.fyi"):
                if name.endswith(domain):
                    return name[: -1 * len(domain)]
            return name

    def __str__(self):
        if self.category:
            return "{} ({})".format(self.name, self.get_category_display())
        else:
            return self.name


class ClusterEventListener(object):
    @staticmethod
    @receiver(post_delete, sender=Cluster)
    def _post_delete(sender, instance, **args):
        WebServer.objects.filter(
            models.Q(name__startswith=instance.name) | models.Q(name=instance.ip)
        ).update(category=None)

    @staticmethod
    @receiver(post_save, sender=Cluster)
    def _post_save(sender, instance, **args):
        WebServer.objects.filter(
            models.Q(name__startswith=instance.name) | models.Q(name=instance.ip)
        ).update(category=WebServer.RANCHER_CLUSTER)


class WebAppLocation(OriginalConfigMixin, models.Model):
    EXACT_LOCATION = 1
    PREFIX_LOCATION = 2
    CASE_SENSITIVE_REGEX_LOCATION = 3
    CASE_INSENSITIVE_REGEX_LOCATION = 4
    NON_REGEX_LOCATION = 5

    LOCATION_TYPES = (
        (EXACT_LOCATION, "Exact Location"),
        (PREFIX_LOCATION, "Prefix Location"),
        (CASE_SENSITIVE_REGEX_LOCATION, "Case Sensitive Regex Location"),
        (CASE_INSENSITIVE_REGEX_LOCATION, "Case Insensitive Regex Location"),
        (NON_REGEX_LOCATION, "Non-regex Location"),
    )

    LOCATION_SCORES = {
        EXACT_LOCATION:900,
        PREFIX_LOCATION:700,
        CASE_SENSITIVE_REGEX_LOCATION:600,
        CASE_INSENSITIVE_REGEX_LOCATION:500,
        NON_REGEX_LOCATION:800
    }

    LOCATION_MATCH = {
        EXACT_LOCATION:lambda loc,path:loc.location == path,
        PREFIX_LOCATION:lambda loc,path:path.startswith(loc.location),
        CASE_SENSITIVE_REGEX_LOCATION:lambda loc,path:True if loc.location_re.search(path) else False,
        CASE_INSENSITIVE_REGEX_LOCATION:lambda loc,path:True if loc.location_re.search(path) else False,
        NON_REGEX_LOCATION:lambda loc,path:path.startswith(loc.location)
    }

    NO_SSO_AUTH = 0
    SSO_AUTH = 1
    SSO_AUTH_DUAL = 2
    SSO_AUTH_TO_DBCA = 11
    SSO_AUTH_TO_DPAW = 12
    SSO_AUTH_TO_UAT = 13

    SSO_AUTH_TYPES = (
        (NO_SSO_AUTH, "SSO Not Required"),
        (SSO_AUTH, "SSO Required"),
        (SSO_AUTH_DUAL, "SSO Dual Auth Required"),
        (SSO_AUTH_TO_DBCA, "SSO To DBCA"),
        (SSO_AUTH_TO_DPAW, "SSO To DPAW"),
        (SSO_AUTH_TO_UAT, "SSO To UAT"),
    )

    HTTP = 1
    HTTPS = 2
    UWSGI = 3
    PROTOCOL_TYPES = ((HTTP, "Http"), (HTTPS, "Https"), (UWSGI, "Uwsgi"))

    _location_re = None

    app = models.ForeignKey(
        WebApp, on_delete=models.CASCADE, related_name="locations", editable=False
    )
    location = models.CharField(max_length=256, editable=False)
    location_type = models.PositiveSmallIntegerField(
        editable=False, choices=LOCATION_TYPES
    )
    score = models.PositiveIntegerField(editable=False,default=0)
    auth_type = models.PositiveSmallIntegerField(choices=SSO_AUTH_TYPES)
    cors_enabled = models.BooleanField(default=False, editable=False)
    forward_protocol = models.PositiveSmallIntegerField(
        choices=PROTOCOL_TYPES, editable=False, null=True
    )
    forward_path = models.CharField(max_length=256, editable=False, null=True)
    redirect = models.CharField(max_length=256, editable=False, null=True)
    return_code = models.PositiveSmallIntegerField(editable=False, null=True)
    refuse = models.BooleanField(default=False, editable=False)
    configure_txt = models.TextField(editable=False)
    modified = models.DateTimeField(auto_now=True)
    config_modified = models.DateTimeField(null=True, editable=False)
    config_changed_columns = ArrayField(
        models.CharField(max_length=128, null=False, blank=False),
        null=True,
        editable=False,
    )
    created = models.DateTimeField(auto_now_add=True)

    def is_match(self,path):
        if self.location_type == self.EXACT_LOCATION:
            if self.location == path:
                return (True,self.location)
        elif self.location_type == self.PREFIX_LOCATION:
            if path.startswith(self.location):
                return (True,self.location)
        elif self.location_type == self.NON_REGEX_LOCATION:
            if path.startswith(self.location):
                return (True,self.location)
        else:
            m = self.location_re.search(path)
            if m:
                return (True,m.group(0))

        return (False,"")

    @property
    def location_re(self):
        if self.location_type == self.CASE_SENSITIVE_REGEX_LOCATION :
            if not self._location_re:
                self._location_re = re.compile(self.location)
        elif self.location_type == self.CASE_INSENSITIVE_REGEX_LOCATION :
            if not self._location_re:
                self._location_re = re.compile(self.location,re.IGNORECASE)

        return self._location_re

    def __str__(self):
        return "{} ({})".format(self.location, self.get_location_type_display())

    class Meta:
        unique_together = [["app", "location_type", "location"]]


class WebAppLocationServer(models.Model):
    location = models.ForeignKey(
        WebAppLocation, on_delete=models.CASCADE, related_name="servers", editable=False
    )
    server = models.ForeignKey(WebServer, on_delete=models.PROTECT, related_name="+")
    port = models.PositiveIntegerField()
    user_added = models.BooleanField(default=True, editable=False)
    rancher_workload = models.ForeignKey(
        Workload,
        on_delete=models.SET_NULL,
        related_name="servers",
        editable=False,
        null=True,
    )
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        self.rancher_workload = self.locate_rancher_workload

    def locate_rancher_workload(self):
        if self.server.category != WebServer.RANCHER_CLUSTER:
            return None

        hostname = self.server.hostname
        qs = WorkloadListening.objects.filter(
            models.Q(workload__cluster__name=hostname)
            | models.Q(workload__cluster__ip=hostname)
        )
        workloadlistening = None
        path = None
        # try to find the workloadlistening object through ingress rule
        for listening in qs.filter(
            ingress_rule__hostname=self.location.app.name, ingress_rule__port=self.port
        ).order_by("-ingress_rule__path"):
            if not listening.ingress_rule.path:
                if not workloadlistening:
                    workloadlistening = listening
            elif self.location.startswith(listening.ingress_rule.path):
                if not workloadlistening:
                    workloadlistening = listening
                    path = listening.ingress_rule.path
                elif listening.ingress_rule.path.startswith(path):
                    workloadlistening = listening
                    path = listening.ingress_rule.path

        if not workloadlistening and self.port >= 30000:
            # try to locate the workload if port is larger than 30000(custom container port)
            workloadlistening = qs.filter(listen_port=self.port).first()

        return workloadlistening.workload if workloadlistening else None

    @classmethod
    def refresh_rancher_workload(cls, cluster):
        for location_server in cls.objects.filter(
            server__category=WebServer.RANCHER_CLUSTER
        ).filter(
            models.Q(server__name__startswith=cluster.name)
            | models.Q(server__name=cluster.ip)
        ):
            rancher_workload = location_server.locate_rancher_workload()
            if location_server.rancher_workload != rancher_workload:
                location_server.rancher_workload = rancher_workload
                location_server.save(update_fields=["rancher_workload"])

    def __str__(self):
        return "{}:{}".format(self.server.name, self.port)

    class Meta:
        unique_together = [["location","server","port"]]

class RequestPathNormalizer(models.Model):
    _f_filter = None
    _f_normalize = None
    _module = None

    filter_code = models.CharField(max_length=512,null=False,unique=True,help_text="A lambda function with two parameters 'webserver' and 'request_path'")
    normalize_code = models.TextField(null=False,unique=True,help_text="The source code of the module which contains a method 'def normalize(request_path)' to return a normalized request  path")

    order = models.PositiveSmallIntegerField(null=False,default=0,help_text="The order to find the filter rule, high order means hight priority")
    changed = models.DateTimeField(null=False,auto_now=True,help_text="The last time when the filter was changed")
    applied = models.DateTimeField(null=True,editable=False,help_text="The last time when the filter was applied to the existed data")

    def clean(self):
        #valdate the filter code
        try:
            self.filter("test.dbca.wa.gov.au","/test")
        except Exception as ex:
            raise ValidationError("Invalid filter code.{}".format(str(ex)))

        try:
            self.normalize("/test/2/change")
        except Exception as ex:
            raise ValidationError("Invalid normalize code.{}".format(str(ex)))

    def filter(self,webserver,request_path):
        """
        Return True if this rule can be applied on the webserver and request_path;otherwise return False
        """
        if not self._f_filter:
            exec("self._f_filter = {}".format(self.filter_code))

        return self._f_filter(webserver,request_path)

    def normalize(self,request_path):
        if not self._f_normalize:
            module_name = "{}_{}".format(self.__class__.__name__,self.id)
            self._module = imp.new_module(module_name)
            exec(self.normalize_code,self._module.__dict__)
            if not hasattr(self._module,"normalize"):
                #method 'normalize' not found
                raise Exception("The method 'normalize' is not found in RequestPathNormalizer({})".format(self.id))
            self._f_normalize = getattr(self._module,"normalize")

        return self._f_normalize(request_path)

    def save(self,*args,**kwargs):
        self.normalize_code = self.normalize_code.strip()
        if self.id:
            existing_obj = RequestPathNormalizer.objects.get(id=self.id)
            if existing_obj.filter_code == self.filter_code and existing_obj.order == self.order and existing_obj.normalize_code == self.normalize_code:
                #no change
                return self
        return super().save(*args,**kwargs)


    @classmethod
    def normalize_path(cls,webserver,request_path,path_normalizers = None,path_normalizer_map = None):
        """
        Return tuple(True, normalized request path) if path parameters is normalized ;otherwise return tuple(False,original request path)
        """
        if not request_path:
            return (False,request_path)
    
        path_normalizer = None
        if path_normalizer_map is not None:
            key = (webserver,request_path)
            path_normalizer = path_normalizer_map.get(key)

        if not path_normalizer:
            path_normalizers = path_normalizers or cls.objects.all().order_by("-order")
            for obj in path_normalizers:
                if obj.filter(webserver,request_path):
                    path_normalizer = obj
                    break
            if path_normalizer_map is not None:
                path_normalizer_map[key] = path_normalizer

        if not path_normalizer:
            #can't find an fiter to apply to the webserver and request path
            return (False,request_path)

        normalized_path = path_normalizer.normalize(request_path)
        return (request_path != normalized_path,normalized_path)


class RequestParameterFilter(models.Model):
    _f_filter = None

    filter_code = models.CharField(max_length=512,null=False,unique=True,help_text="A lambda function with two parameters 'webserver' and 'request_path'")
    included_parameters = ArrayField(models.CharField(max_length=64,null=False,blank=False),null=True,help_text="The list of parameters",blank=True)
    excluded_parameters= ArrayField(models.CharField(max_length=64,null=False,blank=False),null=True,help_text="The list of parameters excluded from the request parameters",blank=True)
    case_insensitive = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(null=False,default=0,help_text="The order to find the filter rule, high order means hight priority")
    changed = models.DateTimeField(null=False,auto_now=True,help_text="The last time when the filter was changed")
    applied = models.DateTimeField(null=True,editable=False,help_text="The last time when the filter was applied to the existed data")

    def clean(self):
        #valdate the filter code
        try:
            self.filter("test.dbca.wa.gov.au","/test")
        except Exception as ex:
            raise ValidationError("Invalid filter code.{}".format(str(ex)))

        if not self.included_parameters:
            self.included_parameters = None
        if not self.excluded_parameters:
            self.excluded_parameters = None

    def save(self,*args,**kwargs):
        if self.case_insensitive:
            if self.included_parameters:
                index = 0
                while index < len(self.included_parameters):
                    self.included_parameters[index] = self.included_parameters[index].lower()
                    index += 1

            if self.excluded_parameters:
                index = 0
                while index < len(self.excluded_parameters):
                    self.excluded_parameters[index] = self.excluded_parameters[index].lower()
                    index += 1
        if self.id:
            existing_obj = RequestParameterFilter.objects.get(id=self.id)
            if existing_obj.filter_code == self.filter_code and existing_obj.order == self.order and existing_obj.included_parameters == self.included_parameters and existing_obj.excluded_parameters == self.excluded_parameters:
                #no change
                return self
        return super().save(*args,**kwargs)


    def filter(self,webserver,request_path):
        """
        Return True if this rule can be applied on the webserver and request_path;otherwise return False
        """
        if not self._f_filter:
            exec("self._f_filter = {}".format(self.filter_code))

        return self._f_filter(webserver,request_path)

    def get_parameters(self,path_parameter_list):
        """
        Return tuple(True, filtered path parameters) if path parameters is filtered ;otherwise return tuple(False,original path parameter)
        """
        changed = False
        if self.included_parameters:
            if "__none__" in self.included_parameters:
                return (True,[])
            index = len(path_parameter_list) - 1
            while index >= 0:
                if self.case_insensitive:
                    if path_parameter_list[index][0].lower() != path_parameter_list[index][0]:
                        path_parameter_list[index][0] = path_parameter_list[index][0].lower()
                        changed = True

                if path_parameter_list[index][0] not in self.included_parameters:
                    changed = True
                    del path_parameter_list[index]
                index -= 1

        elif self.exlucded_parameters:
            if "__all__" in self.excluded_parameters:
                return (True,[])
            index = len(path_parameter_list) - 1
            while index >= 0:
                if self.case_insensitive:
                    if path_parameter_list[index][0].lower() != path_parameter_list[index][0]:
                        path_parameter_list[index][0] = path_parameter_list[index][0].lower()
                        changed = True

                if path_parameter_list[index][0] in self.excluded_parameters:
                    changed = True
                    del path_parameter_list[index]
                index -= 1
        return (changed,path_parameter_list)

    @classmethod
    def filter_parameters(cls,webserver,request_path,path_parameters,parameter_filters = None,parameter_filter_map = None):
        """
        Return tuple(True, filtered path parameters) if path parameters is filtered ;otherwise return tuple(False,original path parameter)
        """
        if not path_parameters:
            return (False,path_parameters)
    
        path_parameter_list = WebAppAccessLog.to_path_parameter_list(path_parameters)
        parameter_filter = None
        if parameter_filter_map is not None:
            key = (webserver,request_path)
            parameter_filter = parameter_filter_map.get(key)

        if not parameter_filter:
            parameter_filters = parameter_filters or cls.objects.all().order_by("-order")
            for obj in parameter_filters:
                if obj.filter(webserver,request_path):
                    parameter_filter = obj
                    break
            if parameter_filter_map is not None:
                parameter_filter_map[key] = parameter_filter

        if not parameter_filter:
            #can't find an fiter to apply to the webserver and request path
            return (False,path_parameters)

        changed,path_parameter_list = parameter_filter.get_parameters(path_parameter_list)

        return (changed,WebAppAccessLog.to_path_parameters(path_parameter_list) if changed else path_parameters)

def apply_rules(context={}):
    """
    apply new rules configured in RequestParameterFilter and RequestPathNormalize
    context: the execution context, currently support two items
        parameter_filters:  the filter list
        parameter_filter_map: the map between filter and webserver,request_path
        path_normalizers: the normalizers list
        path_normalizer_map: the map between normalizer and webserver,reques path
    """
    parameter_filter_changed  =  RequestParameterFilter.objects.filter(models.Q(applied__isnull=True) | models.Q(changed__gt=models.F("applied"))).exists()
    path_normalizer_changed  =  RequestPathNormalizer.objects.filter(models.Q(applied__isnull=True) | models.Q(changed__gt=models.F("applied"))).exists()
    if not parameter_filter_changed and not path_normalizer_changed:
        #both filters and normalizers are not changed since last applied
        return True

    if path_normalizer_changed:
        if "path_normalizers" not in context:
            context["path_normalizers"] = list(RequestPathNormalizer.objects.all().order_by("-order"))
        path_normalizers = context["path_normalizers"]

        if "path_normalizer_map" not in context:
            context["path_normalizer_map"] = {}
        path_normalizer_map = context["path_normalizer_map"]
    else:
        path_normalizers = None
        path_normalizer_map = None

    if parameter_filter_changed:
        if "parameter_filters" not in context:
            context["parameter_filters"] = list(cls.objects.all().order_by("-order"))
        parameter_filters = context["parameter_filters"]

        if "parameter_filter_map" not in context:
            context["parameter_filter_map"] = {}
        parameter_filter_map = context["parameter_filter_map"]
    else:
        parameter_filters = None
        parameter_filter_map = None

    #update WebAppAccessLog
    log_obj = WebAppAccessLog.objects.order_by("log_starttime").first()
    log_starttime = log_obj.log_starttime if log_obj else None
    records = {}
    del_records=[]
    while log_starttime:
        records.clear()
        del_records.clear()
        key = None
        for record in WebAppAccessLog.objects.filter(log_starttime = log_starttime):
            if path_normalizer_changed:
                path_changed,request_path = RequestPathNormalizer.normalize_path(
                    record.webserver,
                    record.request_path,
                    path_normalizers=path_normalizers,
                    path_normalizer_map=path_normalizer_map
                )
            else:
                path_changed = False
                request_path = record.request_path

            if parameter_filter_changed:
                parameters_changed,path_parameters = RequestParameterFilter.filter_parameters(
                    record.webserver,
                    record.request_path,
                    record.path_parameters,
                    parameter_filters=parameter_filters,
                    parameter_filter_map=parameter_filter_map
                )
            else:
                parameters_changed = False
                path_parameters = record.path_parameters

            if path_changed or parameters_changed:
                record.path_parameters = path_parameters
                record.request_path = request_path
                record._changed = True
            else:
                record._changed = False

            key = (log_starttime,record.webserver,record.request_path,record.http_status,record.path_parameters)
            if key in records:
                accesslog = records[key]
                accesslog.requests += int(record.requests)
                accesslog.total_response_time += record.total_response_time
                if accesslog.max_response_time < record.max_response_time:
                    accesslog.max_response_time = record.max_response_time
    
                if accesslog.min_response_time > record.min_response_time:
                    accesslog.min_response_time = record.min_response_time
    
                accesslog.avg_response_time = accesslog.total_response_time / accesslog.requests
                del_records.append(record.id)
                accesslog._changed = True
            else:
                records[key] = record

        with transaction.atomic():
            changed = False
            for key,record in records.items():
                if record._changed:
                    record.save()
                    changed = True

            if del_records:
                WebAppAccessLog.objects.filter(id__in=del_records).delete()

            if del_records or changed:
                logger.debug("{0}: {1} log records have been merged into {2} log records".format(log_starttime,len(del_records),len(records)))
                    
        log_obj = WebAppAccessLog.objects.filter(log_starttime__gt=log_starttime).order_by("log_starttime").first()
        log_starttime = log_obj.log_starttime if log_obj else None

    #update WebAppAccessDaiyLog
    log_obj = WebAppAccessDailyLog.objects.order_by("log_day").first()
    log_day = log_obj.log_day if log_obj else None
    while log_day:
        logger.debug("Apply the new rules on daily log records({})".format(log_day))
        records.clear()
        del_records.clear()
        key = None
        for record in WebAppAccessDailyLog.objects.filter(log_day = log_day):
            if path_normalizer_changed:
                path_changed,request_path = RequestPathNormalizer.normalize_path(
                    record.webserver,
                    record.request_path,
                    path_normalizers=path_normalizers,
                    path_normalizer_map=path_normalizer_map
                )
            else:
                path_changed = False
                request_path = record.request_path

            if parameter_filter_changed:
                parameters_changed,path_parameters = RequestParameterFilter.filter_parameters(
                    record.webserver,
                    record.request_path,
                    record.path_parameters,
                    parameter_filters=parameter_filters,
                    parameter_filter_map=parameter_filter_map
                )
            else:
                parameters_changed = False
                path_parameters = record.path_parameters

            if path_changed or parameters_changed:
                record.path_parameters = path_parameters
                record.request_path = request_path
                record._changed = True
            else:
                record._changed = False

            key = (log_starttime,record.webserver,record.request_path,record.http_status,record.path_parameters)
            if key in records:
                accesslog = records[key]
                accesslog.requests += int(record.requests)
                accesslog.total_response_time += record.total_response_time
                if accesslog.max_response_time < record.max_response_time:
                    accesslog.max_response_time = record.max_response_time
        
                if accesslog.min_response_time > record.min_response_time:
                    accesslog.min_response_time = record.min_response_time
        
                accesslog.avg_response_time = accesslog.total_response_time / accesslog.requests
                del_records.append(record.id)
                accesslog._changed = True
            else:
                records[key] = record

        with transaction.atomic():
            changed = False
            for key,record in records.items():
                if record._changed:
                    record.save()
                    changed = True

            if del_records:
                WebAppAccessDailyLog.objects.filter(id__in=del_records).delete()

            if del_records or changed:
                logger.debug("{0}: {1} daily log records have been merged into {2} daily log records".format(log_day,len(del_records),len(records)))
        
        log_obj = WebAppAccessDailyLog.objects.filter(log_day__gt=log_day).order_by("log_day").first()
        log_day = log_obj.log_day if log_obj else None

    #already applied the latest filter 
    all_applied = True
    now = timezone.now()

    if path_normalizer_changed:
        for path_normalizer in path_normalizers:
            #update the request parameter filter's applied to current time if the filter was not changed during the apply process
            if RequestPathNormalizer.objects.filter(id=path_normalizer.id,changed=path_normalizer.changed).update(applied=now) == 0:
                all_applied = False

    if parameter_filter_changed:
        for parameter_filter in parameter_filters:
            #update the request parameter filter's applied to current time if the filter was not changed during the apply process
            if RequestParameterFilter.objects.filter(id=parameter_filter.id,changed=parameter_filter.changed).update(applied=now) == 0:
                all_applied = False

    return all_applied

class PathParametersMixin(object):
    @property
    def path_parameter_list(self):
        return self.to_path_parameter_list(self.path_parameters)

    @path_parameter_list.setter
    def path_parameter_list(self,value):
        self.path_parameters = self.to_path_parameters(value)

    @staticmethod
    def to_path_parameter_list(path_parameters):
        if not path_parameters:
            return []
        else:
            return [o.split("=",1) for o in path_parameters.split("&")]

    @staticmethod
    def to_path_parameters(path_parameter_list):
        if not path_parameter_list:
            return None
        else:
            return "&".join("{}={}".format(*o) for o in path_parameter_list)


class WebAppAccessLog(PathParametersMixin,models.Model):
    log_starttime = models.DateTimeField(editable=False,null=False)
    log_endtime = models.DateTimeField(editable=False,null=False)

    webserver = models.CharField(max_length=256,editable=False,null=False)
    webapp = models.ForeignKey(WebApp, on_delete=models.SET_NULL,null=True, related_name='logs',editable=False)

    request_path = models.CharField(max_length=512,editable=False,null=False)
    webapplocation = models.ForeignKey(WebAppLocation, on_delete=models.SET_NULL,null=True, related_name='logs',editable=False)

    path_parameters = models.TextField(editable=False,null=True)
    all_path_parameters = ArrayField(models.CharField(max_length=64,null=False),editable=False,null=True)
    http_status = models.PositiveIntegerField(null=False,editable=False)
    requests = models.PositiveIntegerField(null=False,editable=False)
    max_response_time = models.FloatField(null=False,editable=False)
    min_response_time = models.FloatField(null=False,editable=False)
    avg_response_time = models.FloatField(null=False,editable=False)
    total_response_time = models.FloatField(null=False,editable=False)

    class Meta:
        unique_together = [["log_starttime","webserver","request_path","http_status","path_parameters"]]
        index_together = [["log_starttime","webapp","webapplocation"],["webapp","webapplocation"]]


class WebAppAccessDailyLog(PathParametersMixin,models.Model):
    log_day = models.DateField(editable=False,null=False)

    webserver = models.CharField(max_length=256,editable=False,null=False)
    webapp = models.ForeignKey(WebApp, on_delete=models.SET_NULL,null=True, related_name='dailylogs',editable=False)

    request_path = models.CharField(max_length=512,editable=False,null=False)
    webapplocation = models.ForeignKey(WebAppLocation, on_delete=models.SET_NULL,null=True, related_name='dailylogs',editable=False)

    path_parameters = models.TextField(editable=False,null=True)
    all_path_parameters = ArrayField(models.CharField(max_length=64,null=False),editable=False,null=True)
    http_status = models.PositiveIntegerField(null=False,editable=False)
    requests = models.PositiveIntegerField(null=False,editable=False)
    max_response_time = models.FloatField(null=False,editable=False)
    min_response_time = models.FloatField(null=False,editable=False)
    avg_response_time = models.FloatField(null=False,editable=False)
    total_response_time = models.FloatField(null=False,editable=False)

    @classmethod
    def populate_data(cls,lock_file=None,renew_time=None):
        if lock_file and not renew_time:
            try:
                renew_time = acquire_runlock(lock_file,expired=settings.NGINXLOG_MAX_CONSUME_TIME_PER_LOG)
            except exceptions.ProcessIsRunning as ex: 
                msg = "The previous data populating process is still running, no need to run the process this time.{}".format(str(ex))
                logger.info(msg)
                return 
        
        obj = cls.objects.all().order_by("-log_day").first()
        last_populated_log_day = obj.log_day if obj else None
        if last_populated_log_day:
            first_populate_log_day = timezone.make_aware(datetime(last_populated_log_day.year,last_populated_log_day.month,last_populated_log_day.day) + timedelta(days=1))
        else:
            obj = WebAppAccessLog.objects.all().order_by("log_starttime").first()
            if obj:
                first_log_datetime = timezone.localtime(obj.log_starttime)
                first_populate_log_day = timezone.make_aware(datetime(first_log_datetime.year,first_log_datetime.month,first_log_datetime.day))
            else:
                first_populate_log_day = None

        if not first_populate_log_day:
            return

        obj = WebAppAccessLog.objects.all().order_by("-log_starttime").first()
        last_log_datetime = timezone.localtime(obj.log_starttime) if obj else None
        if not last_log_datetime:
            return
        elif last_log_datetime.hour == 23:
            last_populate_log_day = timezone.make_aware(datetime(last_log_datetime.year,last_log_datetime.month,last_log_datetime.day) + timedelta(days=1))
        else:
            last_populate_log_day = timezone.make_aware(datetime(last_log_datetime.year,last_log_datetime.month,last_log_datetime.day))

        populate_log_day = first_populate_log_day
        daily_records = {}
        while populate_log_day < last_populate_log_day:
            next_populate_log_day = populate_log_day + timedelta(days=1)
            logger.debug("Populate the daily access log({}) from {} to {}".format(populate_log_day.date(),populate_log_day,next_populate_log_day))
            daily_records.clear()
            for record in WebAppAccessLog.objects.filter(log_starttime__gte=populate_log_day,log_starttime__lt=next_populate_log_day):
                key = (record.webserver,record.request_path,record.http_status,record.path_parameters)
                if key in daily_records:
                    daily_record = daily_records[key]
                    daily_record.requests += record.requests
                    daily_record.total_response_time += record.total_response_time
                    if daily_record.max_response_time < record.max_response_time:
                        daily_record.max_response_time = record.max_response_time
        
                    if daily_record.min_response_time > record.min_response_time:
                        daily_record.min_response_time = record.min_response_time
        
                    daily_record.avg_response_time = daily_record.total_response_time / daily_record.requests
                    if record.all_path_parameters:
                        if daily_record.all_path_parameters:
                            changed = False
                            for param in record.all_path_parameters:
                                if param not in daily_record.all_path_parameters:
                                    daily_record.all_path_parameters.append(param)
                                    changed = True
                            if changed:
                                daily_record.all_path_parameters.sort()
                        else:
                            daily_record.all_path_parameters = record.all_path_parameters
                else:
                    daily_record = WebAppAccessDailyLog(
                        log_day = populate_log_day.date(),
                        webserver = record.webserver,
                        webapp = record.webapp,
                        request_path = record.request_path,
                        webapplocation = record.webapplocation,
                        http_status = record.http_status,
                        path_parameters = record.path_parameters,
                        all_path_parameters = record.all_path_parameters,
                        requests = record.requests,
                        max_response_time = record.max_response_time,
                        min_response_time = record.min_response_time,
                        avg_response_time = record.avg_response_time,
                        total_response_time = record.total_response_time
                    )
                    daily_records[key] = daily_record
            with transaction.atomic():
                for daily_record in daily_records.values():
                    daily_record.save()
            if lock_file:
                renew_time = renew_runlock(lock_file,renew_time)
            populate_log_day = next_populate_log_day
        return renew_time

    class Meta:
        unique_together = [["log_day","webserver","request_path","http_status","path_parameters"]]
        index_together = [["log_day","webapp","webapplocation"],["webapp","webapplocation"]]


class WebAppAccessDailyReport(models.Model):
    log_day = models.DateField(editable=False,null=False)

    webserver = models.CharField(max_length=256,editable=False,null=False)
    webapp = models.ForeignKey(WebApp, on_delete=models.SET_NULL,null=True, related_name='dailyreports',editable=False)

    requests = models.PositiveIntegerField(null=False,editable=False,default=0)
    success_requests = models.PositiveIntegerField(null=False,editable=False,default=0)
    error_requests = models.PositiveIntegerField(null=False,editable=False,default=0)
    unauthorized_requests = models.PositiveIntegerField(null=False,editable=False,default=0)
    timeout_requests = models.PositiveIntegerField(null=False,editable=False,default=0)

    @classmethod
    def populate_data(cls,lock_file=None,renew_time=None):
        if lock_file and not renew_time:
            try:
                renew_time = acquire_runlock(lock_file,expired=settings.NGINXLOG_MAX_CONSUME_TIME_PER_LOG)
            except exceptions.ProcessIsRunning as ex: 
                msg = "The previous data populating process is still running, no need to run the process this time.{}".format(str(ex))
                logger.info(msg)
                return 
        
        obj = cls.objects.all().order_by("-log_day").first()
        last_populated_log_day = obj.log_day if obj else None
        if last_populated_log_day:
            first_populate_log_day = last_populated_log_day + timedelta(days=1)
        else:
            obj = WebAppAccessDailyLog.objects.all().order_by("log_day").first()
            if obj:
                first_populate_log_day = obj.log_day
            else:
                first_populate_log_day = None

        if not first_populate_log_day:
            return

        obj = WebAppAccessDailyLog.objects.all().order_by("-log_day").first()
        last_populate_log_day = obj.log_day if obj else None
        if not last_populate_log_day:
            return
        last_populate_log_day += timedelta(days=1)

        populate_log_day = first_populate_log_day
        daily_reports = {}
        while populate_log_day < last_populate_log_day:
            next_populate_log_day = populate_log_day + timedelta(days=1)
            logger.debug("Populate the daily report({})".format(populate_log_day))
            daily_reports.clear()
            for record in WebAppAccessDailyLog.objects.filter(log_day=populate_log_day):
                key = (record.webserver,)
                if key in daily_reports:
                    daily_report = daily_reports[key]
                    daily_report.requests += record.requests
                    if record.http_status > 0 and record.http_status < 400:
                        daily_report.success_requests += record.requests
                    elif record.http_status in (401,403):
                        daily_report.unauthorized_requests += record.requests
                    elif record.http_status == 408:
                        daily_report.timeout_requests += record.requests
                    elif record.http_status == 0 or record.http_status >= 400:
                        daily_report.error_requests += record.requests
                else:
                    daily_report = WebAppAccessDailyReport(
                        log_day = populate_log_day,
                        webserver = record.webserver,
                        webapp = record.webapp,
                        requests = record.requests,
                        success_requests = record.requests if record.http_status > 0 and record.http_status < 400  else 0,
                        error_requests = record.requests if record.http_status == 0 or (record.http_status >= 400 and record.http_status not in (401,403,408)) else 0,
                        unauthorized_requests = record.requests if record.http_status in (401,403) else 0,
                        timeout_requests = record.requests if record.http_status == 408 else 0,
                    )
                    daily_reports[key] = daily_report
            with transaction.atomic():
                for daily_report in daily_reports.values():
                    daily_report.save()

            if lock_file:
                renew_time = renew_runlock(lock_file,renew_time)
            populate_log_day += timedelta(days=1)
        return renew_time

    class Meta:
        unique_together = [["log_day","webserver"]]
        index_together = [["log_day","webapp"],["webapp"]]

