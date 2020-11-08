from django.core.management.base import BaseCommand
from organisation.models import DepartmentUser
from registers.models import ITSystem
from registers.utils import sharepoint_user_information_list, sharepoint_it_system_register_list


class Command(BaseCommand):
    help = 'Queries Sharepoint for the IT System Register and syncs it locally'

    def handle(self, *args, **options):
        self.stdout.write('Querying Sharepoint for user information')
        users = sharepoint_user_information_list()

        # Create a dict of user emails using Id as the key.
        users_dict = {}
        for user in users:
            users_dict[user['Id']] = user['EMail']

        self.stdout.write('Querying Sharepoint for IT System Register')
        it_systems = sharepoint_it_system_register_list()

        prod_systems = ITSystem.objects.filter(status__in=[0, 2])
        for system in it_systems:
            self.stdout.write('Checking {}'.format(system['Title']))
            system_id = system['Title'].split()[0]
            name = system['Title'].partition(' - ')[-1]

            if ITSystem.objects.filter(system_id=system_id).exists():
                it_system = ITSystem.objects.get(system_id=system_id)
                update = False
                prod_systems = prod_systems.exclude(pk=it_system.pk)

                # Name
                if name and name != it_system.name:
                    it_system.name = name
                    update = True
                    self.stdout.write(self.style.SUCCESS('Changing {} name to {}'.format(it_system, name)))

                # Status
                status = system['Status']
                if status == 'Production' and status != it_system.get_status_display():
                    it_system.status = 0
                    update = True
                    self.stdout.write(self.style.SUCCESS('Changing {} status to Production'.format(it_system)))
                elif status == 'Production (Legacy)' and status != it_system.get_status_display():
                    it_system.status = 2
                    update = True
                    self.stdout.write(self.style.SUCCESS('Changing {} status to Production (Legacy)'.format(it_system)))

                # System owner
                if system['SystemOwnerId']:
                    owner_email = users_dict[system['SystemOwnerId']]
                else:
                    owner_email = None
                if owner_email:
                    if DepartmentUser.objects.filter(email__iexact=owner_email).exists():
                        # Change the system owner if reqd
                        du = DepartmentUser.objects.filter(email__iexact=owner_email).first()
                        if du != it_system.owner:
                            it_system.owner = du
                            update = True
                            self.stdout.write(self.style.SUCCESS('Changing {} owner to {}'.format(it_system, du)))
                    else:
                        # Warn about user not being found
                        self.stdout.write(self.style.WARNING('Owner {} not found ({})'.format(owner_email, it_system)))
                else:
                    if it_system.owner:
                        # No owner - clear the owner value.
                        it_system.owner = None
                        update = True
                        self.stdout.write(self.style.WARNING('No owner recorded for {}, clearing'.format(it_system)))

                # Technology custodian
                if system['TechnicalCustodianId']:
                    custodian_email = users_dict[system['TechnicalCustodianId']]
                else:
                    custodian_email = None
                if custodian_email:
                    if DepartmentUser.objects.filter(email__iexact=custodian_email).exists():
                        # Change the tech custodian if reqd
                        du = DepartmentUser.objects.filter(email__iexact=custodian_email).first()
                        if du != it_system.technology_custodian:
                            it_system.technology_custodian = du
                            update = True
                            self.stdout.write(self.style.SUCCESS('Changing {} technology custodian to {}'.format(it_system, du)))
                    else:
                        # Warn about user not being found
                        self.stdout.write(self.style.WARNING('Tech custodian {} not found ({})'.format(custodian_email, it_system)))
                else:
                    if it_system.technology_custodian:
                        # No custodian - clear the value.
                        it_system.technology_custodian = None
                        update = True
                        self.stdout.write(self.style.WARNING('No tech custodian recorded for {}, clearing'.format(it_system)))

                # Information custodian
                if system['InformationCustodianId']:
                    info_email = users_dict[system['InformationCustodianId']]
                else:
                    info_email = None
                if info_email:
                    if DepartmentUser.objects.filter(email__iexact=info_email).exists():
                        # Change the info custodian if reqd
                        du = DepartmentUser.objects.filter(email__iexact=info_email).first()
                        if du != it_system.information_custodian:
                            it_system.information_custodian = du
                            update = True
                            self.stdout.write(self.style.SUCCESS('Changing {} info custodian to {}'.format(it_system, du)))
                    else:
                        # Warn about user not being found
                        self.stdout.write(self.style.WARNING('Info custodian {} not found ({})'.format(info_email, it_system)))
                else:
                    if it_system.information_custodian:
                        # No custodian - clear the value.
                        it_system.information_custodian = None
                        update = True
                        self.stdout.write(self.style.WARNING('No info custodian recorded for {}, clearing'.format(it_system)))

                # Seasonality
                season = system['Seasonality']
                if season and season != it_system.get_seasonality_display():
                    for i in ITSystem.SEASONALITY_CHOICES:
                        if season == i[1]:
                            it_system.seasonality = i[0]
                            update = True
                            self.stdout.write(self.style.SUCCESS('Changing {} seasonality to {}'.format(it_system, season)))

                # Availability
                avail = system['Availability']
                if avail and avail != it_system.get_availability_display():
                    for i in ITSystem.AVAILABILITY_CHOICES:
                        if avail == i[1]:
                            it_system.availability = i[0]
                            update = True
                            self.stdout.write(self.style.SUCCESS('Changing {} availability to {}'.format(it_system, avail)))

                # Link
                if system['Link0'] and system['Link0']['Url']:
                    link = system['Link0']['Url']
                else:
                    link = None
                if link and link.strip() != it_system.link:
                    it_system.link = link.strip()
                    update = True
                    self.stdout.write(self.style.SUCCESS('Changing {} link to {}'.format(it_system, link)))

                # Description
                desc = system['Description']
                if desc and desc != it_system.description:
                    it_system.description = desc
                    update = True
                    self.stdout.write(self.style.SUCCESS('Changing {} description to {}'.format(it_system, desc)))

                # Finally, save any changes.
                if update:
                    it_system.save()

            else:
                self.stdout.write(self.style.WARNING('Failed matching {} (possible new system)'.format(name)))

        if prod_systems:
            self.stdout.write(self.style.WARNING('These systems not found in upload (status changed to Unknown): {}'.format(', '.join(i.name for i in prod_systems))))
            for it_system in prod_systems:
                it_system.status = 4
                it_system.save()
