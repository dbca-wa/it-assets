from django.core.management.base import BaseCommand
import json

from organisation.models import CostCentre
from recoup.models import DivisionITSystem
from registers.models import ITSystem


class Command(BaseCommand):
    help = 'Imports DivisionITSystem objects from itsystem.json'

    def handle(self, *args, **options):
        cc_list = json.loads(open('costcentre.json', 'r').read())
        j = json.loads(open('itsystem.json', 'r').read())
        print('{} records'.format(len(j)))
        for obj in j:
            if ITSystem.objects.filter(system_id=obj['fields']['system_id']).exists():
                # First first the matching ID in our old CC fixture list:
                for i in cc_list:
                    if i['pk'] == obj['fields']['cost_centre']:
                        if CostCentre.objects.filter(code=i['fields']['code']).exists():
                            cc = CostCentre.objects.get(code=i['fields']['code'])
                        else:
                            cc = None
                        break

                if cc:
                    dit = DivisionITSystem(
                        pk=obj['pk'],
                        it_system=ITSystem.objects.get(system_id=obj['fields']['system_id']),
                        cost_centre_id=obj['fields']['cost_centre'],
                        division_id=obj['fields']['division']
                    )
                    dit.save()
                    print('{} imported'.format(obj['fields']['system_id']))
