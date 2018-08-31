from django.core.management.base import BaseCommand
import json

from organisation.models import CostCentre
from recoup.models import CostCentreLink


class Command(BaseCommand):
    help = 'Imports CostCentre objects from costcentre.json'

    def handle(self, *args, **options):
        j = json.loads(open('costcentre.json', 'r').read())
        print('{} records'.format(len(j)))
        for obj in j:
            if CostCentre.objects.filter(code=obj['fields']['code']).exists():
                ccl = CostCentreLink(
                    pk=obj['pk'],
                    cc=CostCentre.objects.get(code=obj['fields']['code']),
                    division_id=obj['fields']['division'],
                    user_count=obj['fields']['user_count']
                )
                ccl.save()
                print('{} imported'.format(obj['fields']['code']))
