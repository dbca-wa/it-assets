from __future__ import division, print_function, unicode_literals, absolute_import
from datetime import datetime, date, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.timezone import utc
import locale
from reversion import revisions
import threading


class UTCCreatedField(models.DateTimeField):
    """
    A DateTimeField that automatically populates itself at
    object creation.

    By default, sets editable=False, default=datetime.utcnow.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('editable', False)
        super(UTCCreatedField, self).__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        value = datetime.utcnow().replace(tzinfo=utc)
        setattr(model_instance, self.attname, value)
        return value


class UTCLastModifiedField(UTCCreatedField):
    """
    A DateTimeField that updates itself on each save() of the model.

    By default, sets editable=False and default=datetime.utcnow.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('editable', False)
        super(UTCCreatedField, self).__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        value = datetime.utcnow().replace(tzinfo=utc)
        setattr(model_instance, self.attname, value)
        return value


class Audit(models.Model):
    class Meta:
        abstract = True

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='%(app_label)s_%(class)s_created', editable=False)
    modifier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='%(app_label)s_%(class)s_modified', editable=False)
    created = UTCCreatedField()
    modified = UTCLastModifiedField()

    def __init__(self, *args, **kwargs):
        super(Audit, self).__init__(*args, **kwargs)
        # Initialise any existing model with a dictionary (prev_values), to
        # keep track of any changes on save().
        if self.pk:
            fieldnames = self._meta.get_all_field_names()
            self._fieldnames = set(fieldnames + [f + "_id" for f in fieldnames]).intersection(set(self.__dict__.keys()))
            self._initvalues = set([k for k in self.__dict__.iteritems() if k[0] in self._fieldnames])
        else:
            pass

    def save(self, *args, **kwargs):
        """Falls back on using an admin user if a thread request object wasn't found
        """
        User = get_user_model()
        _locals = threading.local()
        if not hasattr(_locals, "request") or _locals.request.user.is_anonymous():
            if hasattr(_locals, "user"):
                user = _locals.user
            else:
                user = User.objects.get(id=1)
                _locals.user = user
        else:
            user = _locals.request.user
        # If creating a new model, set the creator.
        if not self.pk:
            self.creator = user
        self.modifier = user
        super(Audit, self).save(*args, **kwargs)
        # If the model has existing values, test if any values are being changed.
        # Old values can be accessed through self.prev_values
        change_list = []
        if hasattr(self, '_initvalues'):
            currentvalues = set([k for k in self.__dict__.iteritems() if k[0] in self._fieldnames])
            change_list = self._initvalues - currentvalues
        # Modified and modifier always change; filter these from the list.
        change_list = [item for item in change_list if item[0] not in ['modified' ,'modifier_id']]
        if change_list:
            comment_changed = 'Changed ' + ', '.join([t[0] for t in change_list]) + '.'
            with revisions.create_revision():
                revisions.set_comment(comment_changed)
        elif not change_list and not self.pk:
            with revisions.create_revision():
                revisions.set_comment('Initial version.')
        else:
            # An existing object was saved, with no changes: don't create a revision.
            with revisions.create_revision():
                revisions.set_comment('Nothing changed.')

    def _searchfields(self):
        return set(field.name for field in self.__class__._meta.fields)

    def __unicode__(self):
        fields = ""
        for field in self._searchfields().difference(set(['created', 'modified', 'creator', 'modifier', 'id'])):
            fields += "{0}: {1}, ".format(field, repr(getattr(self, field)))
        return "{0} - {1}".format(self.pk, fields)[:320]

    def get_absolute_url(self):
        return reverse('{0}_detail'.format(self._meta.object_name.lower()), kwargs={'pk':self.pk})


def get_nice_age(d):
    """
    Returns a nice age like "25 days" or "3 months", with appropriate
    resolution.

    Requires a timedelta object as an argument.
    """
    days = d.days
    if d.days >= 730:
        years = d.days/365
        months = (d.days - years*365)/30
        if months > 0:
            return "%d years, %d months" % (years, months)
        else:
            return "%d years" % (years)
    elif d.days >= 365:
        months = (d.days - 365)/30
        if months > 0:
            return "1 year, %d months" % (months)
        else:
            return "1 year"
    elif d.days >= 60:
        return "%d months" % (d.days/30)
    elif d.days >= 30:
        return "1 month"
    elif d.days >= 2:
        return "%d days" % (d.days)
    elif d.days == 1:
        return "1 day"
    elif d.seconds >= 7200:
        return "%d hours" % (d.seconds/3600)
    elif d.seconds >= 3600:
        return "1 hour"
    elif d.seconds >= 120:
        return "%d minutes" % (d.seconds/60)
    elif d.seconds >= 60:
        return "1 minute"
    elif d.seconds >= 2:
        return "%s seconds" % (d.seconds)
    elif d.seconds == 0:
        # Things exactly the same are probably date objects, so max. 1-day
        # resolution
        return "1 day"
    else:
        return "1 second"


class Supplier(Audit):
    name = models.CharField(max_length=200, help_text="eg. Dell, Cisco")
    account_rep = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def get_account_rep(self):
        """
        Returns the account rep's name as a clickable email link.
        """
        if self.contact_email:
            return "<a href='mailto:%s'>%s</a>" % (self.contact_email, self.account_rep)
        else:
            return self.account_rep
    get_account_rep.allow_tags = True
    get_account_rep.short_description = "Account Rep"

    def get_website(self):
        """
        Returns the website as a clickable link.
        """
        if self.website:
            return "<a href='%s'>%s</a>" % (self.website, self.website)
        else:
            return ""
    get_website.allow_tags = True
    get_website.short_description = "Website"

    def get_assets(self):
        """
        Returns the number of assets entered against this manufacturer.
        """
        total = 0
        for model in self.model_set.all():
            total += model.asset_set.count()

        if total:
            return "<a href='../asset/?model__manufacturer__id__exact=%d'>%d</a>" % (self.id, total)
        else:
            return 0
    get_assets.allow_tags = True
    get_assets.short_description = "Assets"


class Model(Audit):
    type_choices = (
        ('Air conditioner', 'Air conditioner'),
        ('Camera - Compact', 'Camera - Compact'),
        ('Camera - SLR', 'Camera - SLR'),
        ('Camera - Security (IP)', 'Camera - Security (IP)'),
        ('Camera - Security (non-IP)', 'Camera - Security (non-IP)'),
        ('Camera - Other', 'Camera - Other'),
        ('Chassis', 'Chassis'),
        ('Computer - Desktop', 'Computer - Desktop'),
        ('Computer - Docking station', 'Computer - Docking station'),
        ('Computer - Input device', 'Computer - Input device'),
        ('Computer - Laptop', 'Computer - Laptop'),
        ('Computer - Misc Accessory', 'Computer - Misc Accessory'),
        ('Computer - Monitor', 'Computer - Monitor'),
        ('Computer - Tablet PC', 'Computer - Tablet PC'),
        ('Computer - Other', 'Computer - Other'),
        ('Environmental monitor', 'Environmental monitor'),
        ('Network - Hub', 'Network - Hub'),
        ('Network - Media converter', 'Network - Media converter'),
        ('Network - Modem', 'Network - Modem'),
        ('Network - Module or card', 'Network - Module or card'),
        ('Network - Power injector', 'Network - Power injector'),
        ('Network - Router', 'Network - Router'),
        ('Network - Switch (Ethernet)', 'Network - Switch (Ethernet)'),
        ('Network - Switch (FC)', 'Network - Switch (FC)'),
        ('Network - Wireless AP', 'Network - Wireless AP'),
        ('Network - Wireless bridge', 'Network - Wireless bridge'),
        ('Network - Wireless controller', 'Network - Wireless controller'),
        ('Network - Other', 'Network - Other'),
        ('Phone - Conference', 'Phone - Conference'),
        ('Phone - Desk', 'Phone - Desk'),
        ('Phone - Gateway', 'Phone - Gateway'),
        ('Phone - Mobile', 'Phone - Mobile'),
        ('Phone - Wireless or portable', 'Phone - Wireless or portable'),
        ('Phone - Other', 'Phone - Other'),
        ('Power Distribution Unit', 'Power Distribution Unit'),
        ('Printer - Fax machine', 'Printer - Fax machine'),
        ('Printer - Local', 'Printer - Local'),
        ('Printer - Local Multifunction', 'Printer - Local Multifunction'),
        ('Printer - Multifunction copier', 'Printer - Multifunction copier'),
        ('Printer - Plotter', 'Printer - Plotter'),
        ('Printer - Workgroup', 'Printer - Workgroup'),
        ('Printer - Other', 'Printer - Other'),
        ('Projector', 'Projector'),
        ('Rack', 'Rack'),
        ('Server - Blade', 'Server - Blade'),
        ('Server - Rackmount', 'Server - Rackmount'),
        ('Server - Tower', 'Server - Tower'),
        ('Storage - Disk array', 'Storage - Disk array'),
        ('Storage - NAS', 'Storage - NAS'),
        ('Storage - SAN', 'Storage - SAN'),
        ('Storage - Other', 'Storage - Other'),
        ('Speaker', 'Speaker'),
        ('Tablet', 'Tablet'),
        ('Tape autoloader', 'Tape autoloader'),
        ('Tape drive', 'Tape drive'),
        ('UPS', 'UPS'),
        ('Other', 'Other'),
    )

    model_type = models.CharField(max_length=50, choices=type_choices, verbose_name="type")
    manufacturer = models.ForeignKey(Supplier)
    model = models.CharField(max_length=50, help_text="Enter the short model number here (eg. '7945G' for a Cisco 7956G phone). Do not enter the class (eg. '7900 series') or the product code (eg. 'WS-7945G=')")
    lifecycle = models.IntegerField( help_text="Enter in years how long we should keep items of this model before they get decomissioned. Desktops should generally be three years, servers and networking equipment five years.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['manufacturer', 'model']

    def __unicode__(self):
        return u"%s %s" % (self.manufacturer, self.model)

    def get_assets(self):
        """
        Returns the number of assets entered against this model.
        """
        total = self.asset_set.count()

        if total:
            return "<a href='../asset/?model__model=%s'>%d</a>" % (self.model, total)
        else:
            return 0
    get_assets.allow_tags = True
    get_assets.short_description = "Assets"

class Location(Audit):
    name = models.CharField(max_length=50, help_text="Enter a specific location - a cupboard or room number.")
    block = models.CharField(max_length=50, blank=True, help_text="eg. 'Block 10' (if applicable)")
    site = models.CharField(max_length=50, help_text="Enter the standard DEC site, eg. 'Kensington' or 'Northcliffe'. If the device is portable, enter 'Portable'.")

    class Meta:
        ordering = ['site', 'block', 'name']

    def __unicode__(self):
        if self.block:
            return u"%s, %s, %s" % (self.name, self.block, self.site)
        elif self.site == "Portable":
            return self.name
        else:
            return u"%s, %s" % (self.name, self.site)

    def get_assets(self):
        """
        Returns the number of assets entered against this location.
        """
        total = self.asset_set.count()

        if total:
            return "<a href='../asset/?location__id__exact=%s'>%d</a>" % (self.id, total)
        else:
            return 0
    get_assets.allow_tags = True
    get_assets.short_description = "Assets"


class Invoice(Audit):
    supplier = models.ForeignKey(Supplier)
    supplier_ref = models.CharField(max_length=50, blank=True, help_text="Enter the supplier's reference or invoice number for this order.")
    job_number = models.CharField(max_length=50, blank=True, help_text="Enter the DEC job number relating to this order.")
    date = models.DateField(blank=True, null=True, help_text="The date as shown on the invoice")
    cost_centre_name = models.CharField(max_length=50, blank=True, help_text="The name of the cost centre that owns this asset for financial purposes.")
    cost_centre_number = models.IntegerField(blank=True, null=True, help_text="The cost centre that owns this asset for financial purposes.")
    etj_number = models.CharField(max_length=20, blank=True, verbose_name="ETJ number")
    total_value = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True, help_text="Enter the total value of the invoice, excluding GST.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-job_number']

    def __unicode__(self):
        if self.job_number and self.total_value:
            return "%s #%s - %2f" % (self.supplier.name, self.job_number, self.total_value)
        elif self.total_value:
            return "%s - %2f" % (self.supplier.name, self.total_value)
        else:
            return self.supplier.name

    def get_assets(self):
        """
        Returns the number of assets entered against this invoice.
        """
        total = self.asset_set.count()

        if total:
            return "<a href='../asset/?invoice__id__exact=%s'>%d</a>" % (self.id, total)
        else:
            return 0
    get_assets.allow_tags = True
    get_assets.short_description = "Assets"


class Asset(Audit):
    asset_tag = models.CharField(max_length=10, unique=True)
    finance_asset_tag = models.CharField(max_length=10, blank=True, help_text="The asset number for this sevices, as issued by Finance (leave blank if unsure)")
    model = models.ForeignKey(Model)
    status_choices = (
            ('In storage', 'In storage'),
            ('Deployed', 'Deployed'),
            ('Disposed', 'Disposed'),
            )
    status = models.CharField(max_length=50, choices=status_choices, default="In storage.")
    serial = models.CharField(max_length=50, help_text="For Dell machines, enter the Service Tag.")
    date_purchased = models.DateField(default=datetime.now)
    invoice = models.ForeignKey(Invoice, blank=True, null=True)
    purchased_value = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True, help_text="Enter the amount paid for this asset, inclusive of any permanent modules or upgrades, and excluding GST.")
    location = models.ForeignKey(Location)
    assigned_user = models.CharField(max_length=50, blank=True, null=True, help_text="Enter the username of the assigned user.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-asset_tag']

    def __unicode__(self):
        return self.asset_tag

    def get_age(self):
        d = date.today() - self.date_purchased
        max_age = timedelta(days = self.model.lifecycle * 365)

        if d > max_age:
            if self.model.lifecycle == 1:
                y = "year"
            else:
                y = "years"
            return "<font color='#FF0000'><b>%s</b></font> (max %d %s)" % (get_nice_age(d), self.model.lifecycle, y)
        else:
            return get_nice_age(d)
    get_age.short_description = "Age"
    get_age.allow_tags = True

    def get_purchased_value(self):
        """
        Return the purchased value as a currency.
        """
        if self.purchased_value == None:
            return "Unknown"
        else:
            locale.setlocale(locale.LC_ALL, ('en_AU', 'UTF-8'))
            return locale.currency(self.purchased_value)
    get_purchased_value.short_description = "Purchased value"

    def get_location(self):
        """
        Return a clickable location field.
        """
        if self.location:
            return "<a href='?location__id__exact=%d'>%s</a>" % (self.location.id, self.location.__unicode__())
        else:
            return ""
    get_location.short_description = "Location"
    get_location.allow_tags = True

    def get_assigned_user(self):
        """
        Return a clickable assigned_user field.
        """
        if self.assigned_user:
            return "<a href='?assigned_user=%s'>%s</a>" % (self.assigned_user, self.assigned_user)
        else:
            return ""
    get_assigned_user.short_description = "Assigned user"
    get_assigned_user.allow_tags = True

    def get_model(self):
        """
        Return a clickable model field.
        """
        if self.model:
            return "<a href='?model__model=%s'>%s</a>" % (self.model.model, self.model)
        else:
            return ""
    get_model.short_description = "Model"
    get_model.allow_tags = True

    def get_type(self):
        """
        Return a clickable type field.
        """
        if self.model:
            return "<a href='?model__model_type=%s'>%s</a>" % (self.model.model_type, self.model.model_type)
        else:
            return ""
    get_type.short_description = "Type"
    get_type.allow_tags = True

