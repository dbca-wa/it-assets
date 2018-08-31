from django.core.management.base import BaseCommand
import json

from recoup.models import SystemDependency, DivisionITSystem, ITPlatform


class Command(BaseCommand):
    help = 'Imports SystemDependency objects from itsystem.json'

    def handle(self, *args, **options):
        j = json.loads(open('systemdependency.json', 'r').read())
        print('{} records'.format(len(j)))
        for obj in j:
            if DivisionITSystem.objects.filter(pk=obj['fields']['system']).exists() and ITPlatform.objects.filter(pk=obj['fields']['platform']).exists():
                sd = SystemDependency(
                    system=DivisionITSystem.objects.get(pk=obj['fields']['system']),
                    platform=ITPlatform.objects.get(pk=obj['fields']['platform']),
                    weighting=obj['fields']['weighting']
                )
                sd.save()
                print("Imported {}".format(sd))
