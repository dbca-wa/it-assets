from itassets.test_api import ApiTestCase, random_dbca_email
from mixer.backend.django import mixer

from tracking.models import FreshdeskTicket, FreshdeskContact ,EC2Instance

from datetime import datetime
import json
from uuid import uuid1


class FreshdeskTicketResourceTestCase(ApiTestCase):

    def setUp(self):
        """Generate from FreshdeskTicket objects.
        """
        super(FreshdeskTicketResourceTestCase, self).setUp()
        mixer.cycle(5).blend(
            FreshdeskContact, email=random_dbca_email)
        mixer.cycle(5).blend(
            FreshdeskTicket,
            subject=mixer.RANDOM, description_text=mixer.RANDOM, type='Test',
            freshdesk_requester=mixer.SELECT,
            it_system=mixer.SELECT,
            custom_fields={
                'support_category': None, 'support_subcategory': None},
        )
        self.ticket = FreshdeskTicket.objects.first()

    def test_list(self):
        """Test the FreshdeskTicketResource list response
        """
        url = '/api/freshdesk_tickets/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ticket.freshdesk_requester.email)

    def test_list_filtering(self):
        """Test the FreshdeskTicketResource filtered list response
        """
        self.ticket.type = 'Incident'
        self.ticket.save()
        url = '/api/freshdesk_tickets/?type=Test'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.ticket.subject)

    def test_detail(self):
        """Test the FreshdeskTicketResource detail response
        """
        url = '/api/freshdesk_tickets/{}/'.format(self.ticket.ticket_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

class EC2InstanceResourceTestCase(ApiTestCase):

    def test_list(self):
        url = '/api/ec2_instances/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_list_filter(self):

        url = '/api/ec2_instances/?name=Test'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.user1.name)




    # need a liitle more info to complete
    # def test_create(self):
    #     url = '/api/ec2_instances/'
    #     name = str(uuid1())[:8]
    #     data = {
    #         'ec2id' : 'i-9fd95c40' ,
    #         'name' : '{}'.format(name),
    #         'launch_time' : datetime.now().isoformat(),
    #         'running' : True,
    #         }
    #     response = self.client.post(url, json.dumps(data), content_type='application/json')
    #     self.assertEqual(response.status_code, 201)
