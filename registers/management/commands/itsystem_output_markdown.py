from django.core.management.base import BaseCommand
import os

from registers.models import ITSystem


class Command(BaseCommand):
    help = 'Outputs details of IT Systems to a directory of of Markdown files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all', action='store_true', dest='all', help='Output non-production systems also')

    def handle(self, *args, **options):
        all = False
        if options['all']:
            all = True

        if all:
            it_systems = ITSystem.objects.all().order_by('system_id')
        else:  # Default to prod/prod-legacy IT systems only.
            it_systems = ITSystem.objects.filter(**ITSystem.ACTIVE_FILTER).order_by('system_id')

        if not os.path.exists('markdown_output'):
            os.mkdir('markdown_output')

        for i in it_systems:
            f = open('markdown_output/{}.md'.format(i.system_id), 'w')
            f.write(i.get_detail_markdown())
