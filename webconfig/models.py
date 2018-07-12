from django.db import models


class Domain(models.Model):
    name = models.CharField(max_length=128, unique=True)

    def __str__(self):
        return self.name


class FQDN(models.Model):
    name = models.CharField(max_length=128)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('name', 'domain')
        verbose_name = 'FQDN'
        verbose_name_plural = 'FQDNs'

    def __str__(self):
        return '{}{}{}'.format(self.name, '.' if self.name else '', self.domain)


class Site(models.Model):
    STATUS_CHOICES = (
        (1, 'Production'),
        (2, 'UAT'),
        (3, 'Development'),
        (4, 'Redirect'),
    )

    AVAILABILITY_CHOICES = (
        (1, 'Internal'),
        (2, 'Public'),
    )

    fqdn = models.OneToOneField(FQDN, null=True, on_delete=models.SET_NULL)
    enabled = models.BooleanField(default=False)
    aliases = models.ManyToManyField(FQDN, related_name='alias_for')
    allow_https = models.BooleanField(default=True)
    allow_http = models.BooleanField(default=False)
    rules = models.TextField()
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1)
    availability = models.SmallIntegerField(choices=AVAILABILITY_CHOICES, default=1)

    class Meta:
        unique_together = ('fqdn',)

    def __str__(self):
        return '{}'.format(self.fqdn)


class Location(models.Model):
    AUTH_LEVEL_CHOICES = (
        (1, 'SSO'),
        (2, 'SSO or Basic Auth'),
        (3, 'Public (SSO Dual)'),
        (4, 'Subnets (SSO Dual)'),
    )

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='locations')
    path = models.CharField(max_length=128)
    auth_level = models.SmallIntegerField(choices=AUTH_LEVEL_CHOICES, default=1)
    allow_cors = models.BooleanField(default=False)
    allow_websockets = models.BooleanField(default=False)
    rules = models.TextField()

    def __str__(self):
        return '{}, {}'.format(self.site, self.path)
