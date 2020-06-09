import re
import logging


from django.db import models
from django.contrib.postgres.fields import JSONField,ArrayField

from itassets.models import OriginalConfigMixin
from registers.models import ITSystem

logger = logging.getLogger(__name__)

# Create your models here.
class Domain(models.Model):
    name = models.CharField(max_length=64,unique=True)
    level = models.PositiveSmallIntegerField(editable=False)
    score = models.BigIntegerField(unique=True,editable=False)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, related_name='children',null=True,editable=False)
    desc = models.TextField(null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def save(self,*args,**kwargs):
        db_obj = Domain.objects.get(pk = self.pk) if self.pk else None
        self.name = self.name.strip()
        self.level = len(self.name.split("."))
        parent_domain = None
        if self.level > 9:
            raise Exception("The maximum level of a domain is 9")
        elif self.level > 1:
            parent_name = self.name.split(".",1)[1]
            self.parent = Domain.objects.filter(name=parent_name).first()
            if not self.parent:
                self.parent = Domain(name = parent_name)
                self.parent.save()

            self.parent_id = self.parent.id

        if self.score and (self.level == 1 or (db_obj and self.parent == db_obj.parent)):
            #score already populated.
            pass
        else:
            if self.level == 1:
                last_sibling = Domain.objects.filter(level=self.level).order_by("-score").first()
            else:
                last_sibling = Domain.objects.filter(parent=self.parent,level=self.level).order_by("-score").first()
    
            if last_sibling:
                self.score = last_sibling.score + pow(100,9 - self.level)
            elif self.parent:
                self.score = self.parent.score + pow(100,9 - self.level)
            else:
                self.score = pow(100,9 - self.level)
        
        result = super().save(*args,**kwargs)
        logger.debug("Create domain(name={},level={},score={},parent={})".format(self.name,self.level,self.score,self.parent))
        return result

    def __str__(self):
        return self.name


class SystemAlias(models.Model):
    system = models.ForeignKey(ITSystem, on_delete=models.PROTECT, related_name='alias',null=True,blank=True)
    name = models.CharField(max_length=64,unique=True)
    desc = models.TextField(null=True,blank=True)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    url_re = re.compile("^((https|http):\/\/)?(www\.)?(?P<host>[a-zA-Z0-9\-\_]+(\.[a-zA-Z0-9]+)*)(\/.*)?$",re.IGNORECASE)
    ip_re = re.compile("^[0-9]{1,3}(\.[0-9]{1,3}){3,3}$")
    @classmethod
    def create_default_alias(cls):
        for system in ITSystem.objects.filter(link__isnull=False):
            url = system.link.strip()
            if not url:
                continue
            #get the system default name
            m = cls.url_re.search(url)
            if not m:
                logger.warning("Can't parse url({})".format(url))
                continue

            name = m.group('host')
            domains = ["dpaw.wa.gov.au","dbca.wa.gov.au","der.wa.gov.au","dec.wa.gov.au","wa.gov.au","com.au","google.com","riverguardians.com","ascenderpay.com","arcgis.com","apple.com","com","org.au","corporateict.domain"]
            domain = None
            for d in domains:
                if name.endswith(d):
                    name = name[:(len(d) + 1) * -1]
                    domain = d
                    break
            if not domain:
                #domain not found
                if cls.ip_re.search(name):
                    #ip address
                    logger.info("The host({2}) of the system({0},link={1}) is ip address, ignore".format(system.name,url,name))
                    continue
                elif "." in name:
                    name,domain = name.split(".",1)
            elif not name:
                name,domain = domain.split(".",1)


            #remove the env from name if have
            for e in ("-uat","-dev","-prod"):
                if name.endswith(e):
                    name = name[:-1 * len(e)]
                    break

            if domain:
                if not Domain.objects.filter(name=domain).exists():
                    Domain(name=domain).save()

            system_alias = SystemAlias.objects.filter(name=name).first()
            if system_alias:
                if not system_alias.system:
                    system_alias.system = system
                    system_alias.save(update_fields = ["system"])
            else:
                logger.debug("Create the alias name({2}) of the system({0},link={1})".format(system.name,url,name))
                SystemAlias(system=system,name=name,desc="System's default name").save()


    def __str__(self):
        if self.system:
            return "{1}({0})".format(self.system.name,self.name)
        else:
            return self.name

class SystemEnv(models.Model):
    name = models.CharField(max_length=64,unique=True)
    desc = models.TextField(null=True,blank=True)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class WebApp(OriginalConfigMixin,models.Model):
    SSO_AUTH_NOT_REQUIRED = 0
    SSO_AUTH_TO_DBCA = 11
    SSO_AUTH_TO_DPAW = 12
    SSO_AUTH_TO_UAT = 13

    SSO_AUTH_DOMAINS = (
        (SSO_AUTH_TO_DBCA,"DBCA"),
        (SSO_AUTH_TO_DPAW,"DPAW"),
        (SSO_AUTH_TO_UAT,"UAT"),
        (SSO_AUTH_NOT_REQUIRED,"-")
    )

    name = models.CharField(max_length=128,unique=True,editable=False)
    system_alias = models.ForeignKey(SystemAlias, on_delete=models.PROTECT, related_name='webapps')
    system_env = models.ForeignKey(SystemEnv, on_delete=models.PROTECT, related_name='webapps',null=True)
    domain = models.ForeignKey(Domain, on_delete=models.PROTECT, related_name='webapps',null=True,blank=True)
    redirect_to = models.ForeignKey("self", on_delete=models.PROTECT, related_name='redirect_from',null=True,editable=False)
    redirect_to_other = models.CharField(max_length=128,editable=False,null=True)
    redirect_path = models.CharField(max_length=128,editable=False,null=True)
    configure_txt = models.TextField(editable=False)
    auth_domain = models.PositiveSmallIntegerField(editable=False,choices=SSO_AUTH_DOMAINS)
    modified = models.DateTimeField(auto_now=True)
    config_modified = models.DateTimeField(null=True,editable=False)
    config_changed_columns = ArrayField(models.CharField(max_length=128,null=False,blank=False),null=True,editable=False)
    created = models.DateTimeField(auto_now_add=True)

    @property
    def redirect(self):
        if self.redirect_to or self.redirect_to_other:
            if self.redirect_path:
                return "{}{}".format(self.redirect_to or self.redirect_to_other,self.redirect_path)
            else:
                return self.redirect_to or self.redirect_to_other
        else:
            return ""

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]

class WebAppListen(models.Model):
    app = models.ForeignKey(WebApp, on_delete=models.CASCADE, related_name='listens',editable=False)
    listen_host = models.CharField(max_length=128,editable=False)
    listen_port = models.PositiveIntegerField(editable=False)
    https = models.BooleanField(default=False,editable=False)
    configure_txt = models.CharField(max_length=256,editable=False)
    modified = models.DateTimeField(auto_now=True)
    config_modified = models.DateTimeField(null=True,editable=False)
    config_changed_columns = ArrayField(models.CharField(max_length=128,null=False,blank=False),null=True,editable=False)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "{}:{}{}".format(self.listen_host,self.listen_port," ssl" if self.https else "")

    class Meta:
        unique_together = [["app","listen_host","listen_port"]]

class WebServer(models.Model):
    AWS_SERVER = 1
    RANCHER_CLUSTER = 2
    DOCKER_SERVER = 4
    WEB_SERVER = 3
    SERVER_CATEGORIES = (
        (AWS_SERVER,"AWS Server"),
        (RANCHER_CLUSTER,"Rancher Cluster"),
        (DOCKER_SERVER,"Docker Server"),
        (WEB_SERVER,"Web Server")
    )

    name = models.CharField(max_length=128,unique=True)
    category = models.PositiveSmallIntegerField(choices=SERVER_CATEGORIES,null=True)
    desc = models.TextField(null=True,blank=True)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return "{}({})".format(self.name,self.get_category_display())

class WebAppLocation(OriginalConfigMixin,models.Model):
    EXACT_LOCATION = 1
    PREFIX_LOCATION = 2
    CASE_SENSITIVE_REGEX_LOCATION = 3
    CASE_INSENSITIVE_REGEX_LOCATION = 4
    NON_REGEX_LOCATION = 5

    LOCATION_TYPES = (
        (EXACT_LOCATION,"Exact Location"),
        (PREFIX_LOCATION,"Prefix Location"),
        (CASE_SENSITIVE_REGEX_LOCATION,"Case Sensitive Regex Location"),
        (CASE_INSENSITIVE_REGEX_LOCATION,"Case Insensitive Regex Location"),
        (NON_REGEX_LOCATION,"Non-regex Location")
    )

    NO_SSO_AUTH = 0
    SSO_AUTH = 1
    SSO_AUTH_DUAL = 2
    SSO_AUTH_TO_DBCA = 11
    SSO_AUTH_TO_DPAW = 12
    SSO_AUTH_TO_UAT = 13

    SSO_AUTH_TYPES = (
        (NO_SSO_AUTH,"SSO Not Required"),
        (SSO_AUTH,"SSO Required"),
        (SSO_AUTH_DUAL,"SSO Dual Auth Required"),
        (SSO_AUTH_TO_DBCA,"SSO To DBCA"),
        (SSO_AUTH_TO_DPAW,"SSO To DPAW"),
        (SSO_AUTH_TO_UAT,"SSO To UAT")
    )

    HTTP = 1
    HTTPS = 2
    UWSGI = 3
    PROTOCOL_TYPES = (
        (HTTP,"Http"),
        (HTTPS,"Https"),
        (UWSGI,"Uwsgi")
    )


    app = models.ForeignKey(WebApp, on_delete=models.CASCADE, related_name='locations',editable=False)
    location = models.CharField(max_length=256,editable=False)
    location_type = models.PositiveSmallIntegerField(editable=False,choices=LOCATION_TYPES)
    auth_type = models.PositiveSmallIntegerField(choices=SSO_AUTH_TYPES)
    cors_enabled = models.BooleanField(default=False,editable=False)
    forward_protocol = models.PositiveSmallIntegerField(choices=PROTOCOL_TYPES,editable=False,null=True)
    forward_path = models.CharField(max_length=256,editable=False,null=True)
    redirect = models.CharField(max_length=256,editable=False,null=True)
    return_code = models.PositiveSmallIntegerField(editable=False,null=True)
    refuse = models.BooleanField(default=False,editable=False)
    configure_txt = models.TextField(editable=False)
    modified = models.DateTimeField(auto_now=True)
    config_modified = models.DateTimeField(null=True,editable=False)
    config_changed_columns = ArrayField(models.CharField(max_length=128,null=False,blank=False),null=True,editable=False)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "{}({})".format(self.location,self.get_location_type_display())

    class Meta:
        unique_together = [["app","location_type","location"]]

class WebAppLocationServer(models.Model):
    location = models.ForeignKey(WebAppLocation, on_delete=models.CASCADE, related_name='servers',editable=False)
    server = models.ForeignKey(WebServer, on_delete=models.PROTECT, related_name='+')
    port = models.PositiveIntegerField()
    user_added = models.BooleanField(default=True,editable=False)
    modified = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return "{}:{}".format(self.server.name,self.port)

    class Meta:
        unique_together = [["location","server","port"]]

