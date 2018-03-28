from django.core.management.base import BaseCommand, CommandError
from django.core.files import File

import os

from tracking.models import SourceFile
from tracking.utils import logger_setup


class Command(BaseCommand):
    args = """<file_type file1 [file2 ...]>"""
    help = """Takes a list of files from the command line and copies their contents to the SourceFile table.
Options for file_type: {}""".format(', '.join(SourceFile.FILE_TYPES.keys()))

    def handle(self, *args, **options):
        logger = logger_setup('mgmt_load_source_file')
        if (len(args) < 2):
            raise CommandError('See "./manage.py help load_source_file" for usage')

        if args[0] not in SourceFile.FILE_TYPES:
            raise CommandError('"{}" is not a valid file type. Options are: {}'.format(args[0], ', '.join(SourceFile.FILE_TYPES.keys())))

        file_type = SourceFile.FILE_TYPES[args[0]]

        files = args[1:]
        for f in files:
            if not os.path.isfile(f):
                raise CommandError('"{}" is not a file path, aborting'.format(f))

        for f in files:
            if os.path.getsize(f) > 0:
                source_file, created = SourceFile.objects.get_or_create(file_type=file_type, file_name=os.path.basename(f))
                if not created:
                    source_file.data.delete()
                source_file.data.save(os.path.basename(f), File(open(f, 'rb')), save=True)

                logger.info('SourceFile id {} ({}, {}) updated'.format(source_file.id, args[0], os.path.basename(f)))
            else:
                logger.info('SourceFile id {} IGNORED: File size zero'.format(os.path.basename(f)))

