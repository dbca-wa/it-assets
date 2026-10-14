from assets.models import Asset, Severity, SeverityMT, State, Vulnerability
from organisation.models import DepartmentUser
from itsystems.models import ITSystemRecord

from django.test import TestCase

from mixer.backend.django import mixer

from datetime import datetime


class AssetModelTestCase(TestCase):
    def setUp(self):
        self.asset1, self.asset2, self.asset3 = RandomAssetGenerator().generate(3)
        self.asset1.save()
        self.asset2.save()
        self.asset3.save()

    def test_add_tag(self):
        """
        validates that the add_tag function works as intended
        """

        # Basic Add
        self.asset1.add_tag("test_tag_1", "test_category")
        self.asset1.add_tag("test_tag_2", "test_category_2")
        self.asset1.save()
        self.assertEqual(len(self.asset1.tags.all()), 2)
        self.assertIn("test_tag_1", self.asset1.display_tags)
        self.assertIn("test_tag_2", self.asset1.display_tags)

        # Add tag with new value but existing category
        self.asset2.add_tag("new_tag_test", "test_category")
        self.asset2.save()
        self.assertEqual(len(self.asset2.tags.all()), 1)
        self.assertIn("new_tag_test", self.asset2.display_tags)
        self.assertIn("test_category", self.asset2.display_tags)

        # Add tag with existing value but new category
        self.asset3.add_tag("test_tag_1", "diff_category")
        self.asset1.add_tag("test_tag_1", "diff_category")
        self.asset1.save()
        self.asset3.save()
        self.assertEqual(len(self.asset3.tags.all()), 1)
        self.assertIn("test_tag_1", self.asset3.display_tags)
        self.assertIn("diff_category", self.asset3.display_tags)
        self.assertEqual(len(self.asset1.tags.all()), 3)
        self.assertIn("test_tag_1", self.asset1.display_tags)
        self.assertIn("diff_category", self.asset1.display_tags)

        # Add duplicate
        self.asset1.add_tag("test_tag_1", "test_category")
        self.asset1.save()
        self.assertEqual(len(self.asset1.tags.all()), 3)
        self.assertIn("test_tag_1", self.asset1.display_tags)
        self.assertIn("test_category", self.asset1.display_tags)
        self.assertIn("test_tag_2", self.asset1.display_tags)
        self.assertIn("test_category_2", self.asset1.display_tags)
        self.assertIn("diff_category", self.asset1.display_tags)

    def test_remove_tag(self):
        """
        Validates that the remove_tag function works as intended
        """

        # Remove existing
        self.asset1.add_tag("test_tag", "test_category")
        self.asset2.add_tag("test_tag", "test_category")
        self.asset1.save()
        self.asset2.save()
        self.assertEqual(len(self.asset1.tags.all()), 1)
        self.assertEqual(len(self.asset2.tags.all()), 1)
        self.asset1.remove_tag("test_tag", "test_category")
        self.asset1.save()
        self.assertEqual(len(self.asset1.tags.all()), 0)
        self.assertEqual(len(self.asset2.tags.all()), 1)

        # Remove non-existing tag
        self.asset2.remove_tag("no_tag", "no_category")
        self.asset2.save()
        self.assertEqual(len(self.asset2.tags.all()), 1)

        # Remove tag that the asset doesn't have
        self.asset1.add_tag("new_tag", "new_category")
        self.asset1.save()
        self.assertEqual(len(self.asset1.tags.all()), 1)
        self.asset2.remove_tag("new_tag", "new_category")
        self.asset2.save()
        self.assertEqual(len(self.asset2.tags.all()), 1)

        # Remove non-existent tag with existing category
        self.asset2.remove_tag("fake_tag", "test_category")
        self.asset2.save()
        self.assertEqual(len(self.asset2.tags.all()), 1)

        # Remove existing tag non-existing category
        self.asset2.remove_tag("test_tag", "fake_category")
        self.asset2.save()
        self.assertEqual(len(self.asset2.tags.all()), 1)

    def test_has_tag(self):
        """
        Validates that the has_tag function works as intended.
        """
        self.asset1.add_tag("test_tag_1", "test_category_1")
        self.asset1.add_tag("test_tag_2", "test_category_2")
        self.asset2.add_tag("test_tag_3", "test_category_3")
        self.asset1.save()
        self.asset2.save()

        # Has tag
        self.assertTrue(self.asset1.has_tag("test_tag_1", "test_category_1"))

        # Doesn't have tag
        self.assertFalse(self.asset1.has_tag("test_tag_3", "test_category_3"))
        self.assertFalse(self.asset1.has_tag("FAKE", "FAKE_CAT"))

        # has tag and has category, but not together
        self.assertFalse(self.asset1.has_tag("test_tag_2", "test_category_1"))

        # Doesn't have tag but has category
        self.assertFalse(self.asset1.has_tag("FAKE", "test_category_1"))

        # Doesn't have category, but has tag
        self.assertFalse(self.asset1.has_tag("test_tag_1", "FAKE"))

    def test_split_tenable_os_and_version(self):
        """
        validates that the __split_tenable_os_and_version function works as intended
        """
        # pattern x.x
        os = "Oracle Linux Server 9.8"
        os_2 = "Ubuntu 16.04.7 LTS (Xenial Xerus)"
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os)
        self.assertEqual("Oracle Linux Server", os)
        self.assertEqual("9.8", ver)
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os_2)
        self.assertEqual("Ubuntu", os)
        self.assertEqual("16.04.7", ver)

        # pattern x.x.x
        os = "macOS 15.7.1"
        os_2 = "Microsoft Windows Server 2012 R2 Standard 6.3.9600 0"
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os)
        self.assertEqual("macOS", os)
        self.assertEqual("15.7.1", ver)
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os_2)
        self.assertEqual("Microsoft Windows Server 2012 R2 Standard", os)
        self.assertEqual("6.3.9600", ver)

        # pattern x.x.x.x
        os = "Ubuntu 16.04.7.123451234 LTS (Xenial Xerus)"
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os)
        self.assertEqual("Ubuntu", os)
        self.assertEqual("16.04.7", ver)

        # pattern .x & x.ABC
        os = "Linux Kernel 5.x on Red Hat Enterprise Linux"
        os_2 = "Linux Kernel .12 on Red Hat Enterprise Linux"
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os)
        self.assertEqual("Linux Kernel 5.x on Red Hat Enterprise Linux", os)
        self.assertIsNone(ver)
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os_2)
        self.assertEqual("Linux Kernel .12 on Red Hat Enterprise Linux", os)
        self.assertIsNone(ver)

        # pattern abc
        os = "Cisco Device"
        os_2 = "Microsoft Windows Server 2003 R2 Service Pack 2"
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os)
        self.assertEqual("Cisco Device", os)
        self.assertIsNone(ver)
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os_2)
        self.assertEqual("Microsoft Windows Server 2003 R2 Service Pack 2", os)
        self.assertIsNone(ver)

        # debian edge case
        os = "Debian GNU/Linux 11 (bullseye)"
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os)
        self.assertEqual("Debian GNU/Linux", os)
        self.assertEqual("11", ver)

        # pattern abc.abc
        os = "macOS x.y.z"
        os_2 = "macOS x.y"
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os)
        self.assertEqual("macOS x.y.z", os)
        self.assertIsNone(ver)
        os, ver = self.asset1._Asset__split_tenable_os_and_version(os_2)
        self.assertEqual("macOS x.y", os)
        self.assertIsNone(ver)

    def test_update_from_tenable_data(self):
        """
        Tests that update_from_tenable_data behaves as expected
        """
        webapp_data = {
            "id": "webapp_id",
            "network": {
                "fqdns": ["example.dbca.wa.gov.au"],
            },
            "sources": [{"first_seen": "2025-05-31T12:00:02.328Z", "last_seen": "2026-09-17T16:00:10.488Z", "name": "WAS"}],
            "tags": [
                {"key": "Custodian", "value": "TST"},
                {"key": "Devices", "value": "Web App"},
            ],
            "types": ["webapp"],
        }

        self.asset1.update_from_tenable_data(tenable_data=webapp_data)
        self.assertEqual(self.asset1.name, "example.dbca.wa.gov.au")
        self.assertTrue(self.asset1.has_tag(tag="TST", category="Custodian"))
        self.assertTrue(self.asset1.has_tag(tag="Web App", category="Devices"))

        server_data = {
            "id": "server_id",
            "network": {
                "fqdns": ["example-server-001.name.domain"],
                "hostnames": ["example-server-001.name.domain"],
            },
            "operating_systems": ["Oracle Linux 6.10", "Linux Kernel 3.8.13-118.19.7.el6uek.x86_64 on Oracle Linux Server release 6.10"],
            "sources": [{"first_seen": "2025-03-13T02:23:29.463Z", "last_seen": "2026-09-29T04:57:17.925Z", "name": "NESSUS_SCAN"}],
            "tags": [
                {"key": "Devices", "value": "Server"},
                {"key": "Custodian", "value": "TST2"},
            ],
            "types": ["host"],
        }

        self.asset2.update_from_tenable_data(tenable_data=server_data)
        self.assertEqual(self.asset2.name, "example-server-001")
        self.assertTrue(self.asset2.has_tag(tag="TST2", category="Custodian"))
        self.assertTrue(self.asset2.has_tag(tag="Server", category="Devices"))
        self.assertEqual(self.asset2.os, "Oracle Linux")
        self.assertEqual(self.asset2.os_version, "6.10")

        # device
        user_device = {
            "agent_names": ["device-agent_name"],
            "id": "user_device_id",
            "network": {
                "hostnames": ["example-device-name"],
            },
            "operating_systems": ["Microsoft Windows 11 Enterprise 10.0.26200 0"],
            "sources": [{"first_seen": "2026-09-24T03:24:21.323Z", "last_seen": "2026-10-01T01:01:24.909Z", "name": "NESSUS_AGENT"}],
            "tags": [
                {"key": "Devices", "value": "User Device"},
            ],
            "types": ["host"],
        }

        self.asset3.update_from_tenable_data(tenable_data=user_device)
        self.assertEqual(self.asset3.name, "example-device-name")
        self.assertTrue(self.asset3.has_tag(tag="User Device", category="Devices"))
        self.assertEqual(self.asset3.os, "Microsoft Windows 11 Enterprise")
        self.assertEqual(self.asset3.os_version, "10.0.26200")

        # Switch
        switch_data = {
            "id": "switch_id",
            "network": {
                "fqdns": ["example-switch.name.domain"],
            },
            "operating_systems": [
                "CISCO IOS 15\nCISCO IOS 12\nCisco IOS XE\nCISCO PIX",
                "CISCO IOS 12",
                "CISCO PIX",
                "Cisco IOS XE",
                "CISCO IOS 15",
            ],
            "sources": [{"first_seen": "2025-08-04T12:43:01.796Z", "last_seen": "2026-09-29T04:53:01.524Z", "name": "NESSUS_SCAN"}],
            "tags": [
                {"key": "Devices", "value": "Switch"},
            ],
            "types": ["host"],
        }

        self.asset1.update_from_tenable_data(tenable_data=switch_data)
        self.assertEqual(self.asset1.name, "example-switch")
        self.assertEqual(self.asset1.os, "CISCO IOS 15\nCISCO IOS 12\nCisco IOS XE\nCISCO PIX")
        self.assertIsNone(self.asset1.os_version)
        self.assertTrue(self.asset1.has_tag(tag="Switch", category="Devices"))

        other_data = {
            "id": "other_id",
            "operating_systems": ["XEROX"],
            "sources": [{"first_seen": "2026-04-29T04:41:22.032Z", "last_seen": "2026-09-30T03:10:24.967Z", "name": "NESSUS_SCAN"}],
            "tags": [
                {"key": "OS", "value": "Others"},
            ],
            "types": ["host"],
        }

        self.asset1.update_from_tenable_data(tenable_data=other_data)
        self.assertIsNone(self.asset1.name)
        self.assertEqual(self.asset1.os, "XEROX")
        self.assertIsNone(self.asset1.os_version)
        self.assertTrue(self.asset1.has_tag(tag="Others", category="OS"))

class VulnerabilityModelTestCase(TestCase):

    def test_update_from_raw_vuln_data(self):
        gen = RandomAssetGenerator()
        asset1, asset2 = gen.generate(2)

        # Sample tenable vulnerability with random data
        raw = {
            'port': {
                'port': 1, 'protocol': 'TCP'
                },
            'scan': {
                'uuid': 'example_scan_uuid',
                'target': '1.1.1.1',
                'started_at': '2026-10-09T10:02:28.348Z',
                'schedule_uuid': 'example_schedule_uuid'
                },
            'asset': {
                'fqdn': 'test_asset.example.domain',
                'ipv4': '1.2.3.4',
                'uuid': asset1.tenable_id,
                'tracked': True,
                'hostname': 'test_asset',
                'bios_uuid': 'example_bios_uuid',
                'agent_uuid': 'example_agent_uuid',
                'network_id': '0000000000000000',
                'device_type': 'general-purpose',
                'mac_address': '01:02:03:04:05',
                'netbios_name': 'TEST_ASSET',
                'last_scan_target': '10.6.20.16',
                'operating_system': ['Microsoft Windows Server 2019 Standard 10.0.17763 0'],
                'last_authenticated_results': '2026-10-09T11:03:02.078Z'
                },
            'state': 'OPEN',
            'output': 'example plugin output',
            'plugin': {
                'id': 1234,
                'cpe': ['cpename'],
                'name': 'plugin name example',
                'type': 'local',
                'xrefs': [],
                'family': 'Windows',
                'version': '1.12',
                'see_also': ['http://www.nessus.org/random_url'],
                'solution': 'this is an example solution',
                'synopsis': 'This is an example synopsis',
                'family_id': 1,
                'has_patch': False,
                'cvss_vector': {
                    'raw': 'raw/vector:/thingy',
                    'access_vector': 'Local',
                    'authentication': 'None required',
                    'integrity_impact': 'Complete',
                    'access_complexity': 'Low',
                    'availability_impact': 'Complete',
                    'confidentiality_impact': 'Complete'
                },
                'description': 'example plugin description',
                'in_the_news': False,
                'risk_factor': 'high',
                'cvss3_vector': {
                    'raw': 'blahblahblah',
                    'access_vector': 'Local',
                    'integrity_impact': 'High',
                    'access_complexity': 'Low',
                    'availability_impact': 'High',
                    'confidentiality_impact': 'High'
                },
                'has_workaround': False,
                'cvss_base_score': 7.2,
                'cvss3_base_score': 8.4,
                'publication_date': '2013-03-06T00:00:00Z',
                'exploit_available': False,
                'modification_date': '2025-03-14T00:00:00Z',
                'checks_for_malware': False,
                'exploited_by_nessus': False,
                'cvss_temporal_vector': {},
                'exploited_by_malware': False,
                'cvss3_temporal_vector': {},
                'unsupported_by_vendor': False,
                'exploit_framework_core': False,
                'exploit_framework_canvas': False,
                'checks_for_default_account': False,
                'exploit_framework_d2_elliot': False,
                'exploit_framework_exploithub': False,
                'exploit_framework_metasploit': False,
                'vpr':{
                    'drivers': {
                        'age_of_vuln': {
                            'lower_bound': 60,
                            'upper_bound': 230
                        },
                    },
                },
            },
            'source': 'AGENT',
            'indexed': '2026-10-09T11:13:38.924904Z',
            'severity': 'high',
            'finding_id': 'random_finding_id',
            'last_found': '2026-10-09T11:03:02.078Z',
            'first_found': '2025-03-13T02:23:29.463Z',
            'severity_id': 3,
            'severity_default_id': 3,
            'severity_modification_type': 'NONE'
        }



        # Add the vuln
        asset1.update_from_tenable_data(vuln_data=[raw])

        # ===========================================
        #               General Tests
        #============================================
        new_vuln = asset1.get_active_vulns().first()
        # Top level tests
        self.assertEqual(new_vuln.finding_id,raw['finding_id'])
        # Plugin test
        self.assertEqual(new_vuln.cvss3_base_score, raw['plugin']['cvss3_base_score'])
        # Vuln Age test
        self.assertEqual(new_vuln.vuln_age,'60-230 days')
        # date conversion test
        self.assertEqual(new_vuln.first_found,datetime.fromisoformat(raw['first_found']))
        # Choice value tests
        self.assertEqual(new_vuln.get_severity_display(), "High")
        self.assertEqual(new_vuln.severity, Severity.HIGH)
        self.assertEqual(new_vuln.get_severity_modification_type_display(), "None")
        self.assertEqual(new_vuln.severity_modification_type, SeverityMT.NONE)
        self.assertEqual(new_vuln.get_state_display(), "Open")
        self.assertEqual(new_vuln.state, State.OPEN)

        # ==============================================
        #          Stat & vuln assignment tests
        #===============================================

        # Adding critical vuln - should bump both total and critical stats
        # Also bundles in new vuln age test value
        raw['severity_id'] = Severity.CRITICAL
        raw['plugin']['vpr']['drivers']['age_of_vuln']['lower_bound'] = 800

        # Runs it twice to test update vs replacement
        asset1.update_from_tenable_data(vuln_data=[raw, raw])

        # Test that a new vuln wasn't added, just reclassified to critical
        self.assertEqual(asset1.total_critical_vulns, 1)
        self.assertEqual(asset1.total_active_vulns, 1)
        self.assertEqual(len(Vulnerability.objects.all()),1)
        self.assertEqual(len(asset1.get_vulns()),1)
        self.assertEqual(len(asset1.get_active_vulns()),1)
        self.assertEqual(len(Vulnerability.objects.all()),1)
        self.assertTrue(asset1.has_vuln(finding_id=raw['finding_id']))

        # age of vuln alt value check
        new_vuln = asset1.get_active_vulns().first()
        self.assertEqual(new_vuln.vuln_age, "More than 730 days")

        # Adding 3 non-active vulns - shouldn't impact the active count, but should impact the general count
        raw['finding_id'] = "different_finding_id"
        raw['state'] = 'FIXED'
        asset1.update_from_tenable_data(vuln_data=[raw])
        raw['finding_id'] = "even_more_different_finding_id"
        raw['state'] = 'OPEN'
        raw['severity_id'] = Severity.INFO
        asset1.update_from_tenable_data(vuln_data=[raw])
        raw['finding_id'] = "extremely_diff_finding_id"
        raw['severity_id'] = Severity.CRITICAL
        raw["severity_modification_type"] = "ACCEPTED"
        asset1.update_from_tenable_data(vuln_data=[raw])

        # Verifies that all 3 vulns were added, but only 1 vuln is active + critical
        self.assertEqual(asset1.total_critical_vulns, 1)
        self.assertEqual(asset1.total_active_vulns, 1)
        self.assertEqual(asset1.total_vulns, 4)
        self.assertEqual(len(Vulnerability.objects.all()),4)
        self.assertEqual(len(asset1.get_vulns()),4)
        self.assertEqual(len(asset1.get_active_vulns()),1)

        # has_vuln check
        self.assertTrue(asset1.has_vuln(finding_id='different_finding_id'))
        self.assertTrue(asset1.has_vuln(finding_id='even_more_different_finding_id'))
        self.assertTrue(asset1.has_vuln(finding_id='extremely_diff_finding_id'))
        self.assertTrue(asset1.has_vuln(finding_id='random_finding_id'))



    def test_vuln_age(self):
        pass


class RandomVulnGenerator:
 pass

class RandomAssetGenerator:
    tenable_id_inc = 0

    def __create(self):
        self.tenable_id_inc += 1
        return mixer.blend(
            Asset,
            tenable_id=self.tenable_id_inc,
            name=mixer.RANDOM,
            os=mixer.RANDOM("Windows", "Linux", "MaxOS", "Other"),
            os_version=mixer.RANDOM,
            description=mixer.RANDOM("16", "24.04", "10.1.8", "0.0.1"),
            contacts=mixer.blend(DepartmentUser),
            systems=mixer.blend(ITSystemRecord),
        )

    def generate(self, generations: int) -> tuple[Asset]:
        return tuple([self.__create() for i in range(generations)])
