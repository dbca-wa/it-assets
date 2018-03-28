from itassets.test_api import ApiTestCase, random_dbca_email
from mixer.backend.django import mixer

from tracking.models import FreshdeskTicket, FreshdeskContact


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
