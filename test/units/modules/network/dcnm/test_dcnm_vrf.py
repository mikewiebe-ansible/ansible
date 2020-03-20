# (c) 2020 Red Hat Inc.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from units.compat.mock import patch

from ansible.modules.network.dcnm import dcnm_vrf
from .dcnm_module import TestDcnmModule, set_module_args


class TestDcnmVrfModule(TestDcnmModule):

    module = dcnm_vrf

    mock_ip_sn = {'10.10.10.224': 'XYZKSJHSMK1',
                  '10.10.10.225': 'XYZKSJHSMK2'}

    mock_config=\
        [{'vrf_name': 'test_vrf_1',
        'vrf_id': '9008011',
        'vrf_template': 'Default_VRF_Universal',
        'vrf_extension_template': 'Default_VRF_Extension_Universal',
        'source': 'None',
        'service_vrf_template': 'None',
        'attach': [
            {'ip_address': '10.10.10.224',
            'vlan_id': '202',
            'deploy': 'true'
            },
            {'ip_address': '10.10.10.225',
            'vlan_id': '203',
            'deploy': 'true'
            }
        ],
        'deploy': 'true'
        }]

    mock_config_override = \
        [{'vrf_name': 'test_vrf_2',
          'vrf_id': '9008012',
          'vrf_template': 'Default_VRF_Universal',
          'vrf_extension_template': 'Default_VRF_Extension_Universal',
          'source': 'None',
          'service_vrf_template': 'None',
          'attach': [
              {'ip_address': '10.10.10.224',
               'vlan_id': '302',
               'deploy': 'true'
               },
              {'ip_address': '10.10.10.225',
               'vlan_id': '303',
               'deploy': 'true'
               }
          ],
          'deploy': 'true'
          }]

    mock_config_incorrect_vrfid = \
        [{'vrf_name': 'test_vrf_1',
          'vrf_id': '9008012',
          'vrf_template': 'Default_VRF_Universal',
          'vrf_extension_template': 'Default_VRF_Extension_Universal',
          'source': 'None',
          'service_vrf_template': 'None',
          'attach': [
              {'ip_address': '10.10.10.224',
               'vlan_id': '202',
               'deploy': 'true'
               },
              {'ip_address': '10.10.10.225',
               'vlan_id': '203',
               'deploy': 'true'
               }
          ],
          'deploy': 'true'
          }]

    mock_config_replace = \
        [{'vrf_name': 'test_vrf_1',
          'vrf_id': '9008011',
          'vrf_template': 'Default_VRF_Universal',
          'vrf_extension_template': 'Default_VRF_Extension_Universal',
          'source': 'None',
          'service_vrf_template': 'None',
          'attach': [
              {'ip_address': '10.10.10.225',
               'vlan_id': '203',
               'deploy': 'true'
               }
          ],
          'deploy': 'true'
          }]

    mock_vrf_attach_object_del_not_ready = \
        {'DATA': [
            {
                "vrfName": "test_vrf_1",
                "lanAttachList": [
                    {
                        "lanAttachState": "DEPLOYED"
                    },
                    {
                        "lanAttachState": "DEPLOYED"
                    }
                ]
            }
        ]
        }

    mock_vrf_attach_object_del_ready = \
        {'DATA': [
            {
                "vrfName": "test_vrf_1",
                "lanAttachList": [
                    {
                        "lanAttachState": "NA"
                    },
                    {
                        "lanAttachState": "NA"
                    }
                ]
            }
        ]
        }


    def init_data(self):

        self.mock_vrf_object = \
            {'ERROR': '',
             'RETURN_CODE': '',
             'DATA': [
                 {
                     "fabric": "test_fabric",
                     "vrfName": "test_vrf_1",
                     "vrfTemplate": "Default_VRF_Universal",
                     "vrfExtensionTemplate": "Default_VRF_Extension_Universal",
                     "serviceVrfTemplate": 'None',
                     "source": 'None',
                     "vrfStatus": "DEPLOYED",
                     "vrfId": "9008011"
                 }
             ]
             }

        self.mock_vrf_attach_object = \
            {'DATA': [
                {
                    "vrfName": "test_vrf_1",
                    "lanAttachList": [
                        {
                            "vrfName": "test_vrf_1",
                            "switchName": "n9kv_leaf1",
                            "lanAttachState": "DEPLOYED",
                            "isLanAttached": "true",
                            "switchSerialNo": "XYZKSJHSMK1",
                            "switchRole": "leaf",
                            "fabricName": "test-fabric",
                            "ipAddress": "10.10.10.224",
                            "vlanId": "202",
                            "vrfId": "9008011"
                        },
                        {
                            "vrfName": "test_vrf_1",
                            "switchName": "n9kv_leaf2",
                            "lanAttachState": "DEPLOYED",
                            "isLanAttached": "true",
                            "switchSerialNo": "XYZKSJHSMK2",
                            "switchRole": "leaf",
                            "fabricName": "test-fabric",
                            "ipAddress": "10.10.10.225",
                            "vlanId": "203",
                            "vrfId": "9008011"
                        }
                    ]
                }
            ]
            }


    def setUp(self):
        super(TestDcnmVrfModule, self).setUp()

        self.mock_dcnm_ip_sn = patch('ansible.modules.network.dcnm.dcnm_vrf.get_fabric_inventory_details')
        self.run_dcnm_ip_sn = self.mock_dcnm_ip_sn.start()

        self.mock_dcnm_send = patch('ansible.modules.network.dcnm.dcnm_vrf.dcnm_send')
        self.run_dcnm_send = self.mock_dcnm_send.start()

    def tearDown(self):
        super(TestDcnmVrfModule, self).tearDown()
        self.mock_dcnm_send.stop()
        self.mock_dcnm_ip_sn.stop()

    def load_fixtures(self, response=None, device=''):
        attach_success_resp = dict({'vrf-on-switch':'SUCCESS'})
        deploy_success_resp = dict({"status":""})
        delete_success_resp = {}

        self.run_dcnm_ip_sn.side_effect = [self.mock_ip_sn]
        if '_merged_new' in self._testMethodName:
            self.run_dcnm_send.side_effect = [{'DATA':{}}, {}, attach_success_resp, deploy_success_resp]

        elif '_merged_duplicate' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        elif '_merged_with_incorrect' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        elif 'replace_with_changes' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object,
                                              attach_success_resp, deploy_success_resp, delete_success_resp]

        elif 'replace_without_changes' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        elif 'override_with_additions' in self._testMethodName:
            self.run_dcnm_send.side_effect = [{'DATA':{}}, {}, attach_success_resp, deploy_success_resp]

        elif 'override_with_deletions' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object, {},
                                              attach_success_resp, deploy_success_resp,
                                              self.mock_vrf_attach_object_del_not_ready,
                                              self.mock_vrf_attach_object_del_ready,
                                              delete_success_resp]

        elif 'override_without_changes' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        elif 'dcnm_vrf_delete' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object,
                                              attach_success_resp, deploy_success_resp,
                                              self.mock_vrf_attach_object_del_not_ready,
                                              self.mock_vrf_attach_object_del_ready,
                                              delete_success_resp]

        else:
            pass


    def test_01dcnm_vrf_merged_new(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.mock_config))
        result = self.execute_module(changed=True, failed=False)
        self.assertTrue(result.get('changed'))

    def test_02dcnm_vrf_merged_duplicate(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.mock_config))
        result = self.execute_module(changed=False, failed=False)
        self.assertFalse(result.get('changed'))

    def test_03dcnm_vrf_merged_with_incorrect_vrfid(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.mock_config_incorrect_vrfid))
        result = self.execute_module(changed=False, failed=True)
        self.assertEqual(result.get('msg'), 'vrf_id for VRF:test_vrf_1 cant be updated to a different value')

    def test_04dcnm_vrf_replace_with_changes(self):
        set_module_args(dict(state='replaced', fabric='test_fabric', config=self.mock_config_replace))
        result = self.execute_module(changed=True, failed=False)
        self.assertTrue(result.get('changed'))

    def test_05dcnm_vrf_replace_without_changes(self):
        set_module_args(dict(state='replaced', fabric='test_fabric', config=self.mock_config))
        result = self.execute_module(changed=False, failed=False)
        self.assertFalse(result.get('changed'))

    def test_06dcnm_vrf_override_with_additions(self):
        set_module_args(dict(state='overridden', fabric='test_fabric', config=self.mock_config))
        result = self.execute_module(changed=True, failed=False)
        self.assertTrue(result.get('changed'))

    def test_07dcnm_vrf_override_with_deletions(self):
        set_module_args(dict(state='overridden', fabric='test_fabric', config=self.mock_config_override))
        result = self.execute_module(changed=True, failed=False)
        self.assertTrue(result.get('changed'))

    def test_08dcnm_vrf_override_without_changes(self):
        set_module_args(dict(state='overridden', fabric='test_fabric', config=self.mock_config))
        result = self.execute_module(changed=False, failed=False)
        self.assertFalse(result.get('changed'))

    def test_09dcnm_vrf_delete(self):
        set_module_args(dict(state='deleted', fabric='test_fabric', config=self.mock_config))
        result = self.execute_module(changed=True, failed=False)
        self.assertTrue(result.get('changed'))
