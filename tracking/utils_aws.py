from django.conf import settings
import json
import logging
import os
from .models import EC2Instance, Computer

LOGGER = logging.getLogger('sync_tasks')


def aws_load_instances():
    """Update the database with EC2 Instance information.
    """
    from registers.models import ITSystemHardware  # Prevent circular import.

    # Serialise the instance data.
    ec2_info = open(os.path.join(settings.AWS_JSON_PATH, 'aws_ec2_describe_instances.json'))
    ec2_info = json.loads(ec2_info.read())
    ssm_info = open(os.path.join(settings.AWS_JSON_PATH, 'aws_ssm_instance_information.json'))
    ssm_info = json.loads(ssm_info.read())
    inst_ssm = {i['InstanceId']: i for i in ssm_info['InstanceInformationList']}
    inst_ec2 = {}
    for i in ec2_info['Reservations']:
        for j in i['Instances']:
            inst_ec2[j['InstanceId']] = j

    for k, v in inst_ec2.items():
        try:
            if EC2Instance.objects.filter(ec2id=k).exists():
                ec2 = EC2Instance.objects.get(ec2id=k)
            else:
                ec2 = EC2Instance(ec2id=k)
            # Parse the silly 'Tags' output.
            name = None
            tags = {}
            for t in v['Tags']:
                if t['Key'].lower() == 'name':
                    name = t['Value']
                tags[t['Key']] = t['Value']

            ec2.name = name
            ec2.tags = tags
            ec2.save()
            LOGGER.info('EC2 instance {} ({}) updated'.format(ec2.ec2id, ec2.name))
        except Exception as e:
            LOGGER.error('Error while loading EC2 instance information')
            LOGGER.exception(e)

        # If the instance name matches one single Computer, create a FK link.
        comps = Computer.objects.filter(hostname__istartswith=ec2.name)
        if comps.exists() and comps.count() == 1:
            c = comps[0]
            c.ec2_instance = ec2
            c.save()

    for k, v in inst_ssm.items():
        if k.startswith('i'):  # Don't check objects without an EC2 instance ID.
            try:
                if EC2Instance.objects.filter(ec2id=k).exists():
                    ec2 = EC2Instance.objects.get(ec2id=k)
                else:
                    ec2 = EC2Instance(ec2id=k)

                ec2.agent_version = v['AgentVersion']
                ec2.save()
                LOGGER.info('EC2 instance {} ({}) updated'.format(ec2.ec2id, ec2.name))
            except Exception as e:
                LOGGER.error('Error while loading EC2 instance information')
                LOGGER.exception(e)

    # Update patch_group values on ITSystemHardware objects.
    for i in ITSystemHardware.objects.all():
        i.set_patch_group()
