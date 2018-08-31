from django.core.management.base import BaseCommand
import json

from organisation.models import OrgUnit
from recoup.models import Division


class Command(BaseCommand):
    help = 'Imports Division objects from division.json'

    def handle(self, *args, **options):
        j = json.loads(open('division.json', 'r').read())
        print('{} records'.format(len(j)))
        for obj in j:
            div = Division(
                pk=obj['pk'],
                org_unit=OrgUnit.objects.get(name=obj['fields']['name']),
                user_count=obj['fields']['user_count'],
                position=obj['fields']['position']
            )
            div.save()
            print('{} imported'.format(obj['fields']['name']))
