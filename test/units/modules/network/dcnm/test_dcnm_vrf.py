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
from .dcnm_module import TestDcnmModule, set_module_args, loadPlaybookData

import json, copy

class TestDcnmVrfModule(TestDcnmModule):

    module = dcnm_vrf

    test_data = loadPlaybookData('dcnm_vrf')

    mock_ip_sn = test_data.get('mock_ip_sn')
    playbook_config_input_validation = test_data.get('playbook_config_input_validation')
    playbook_config = test_data.get('playbook_config')
    playbook_config_update = test_data.get('playbook_config_update')
    playbook_config_update_vlan = test_data.get('playbook_config_update_vlan')
    playbook_config_override = test_data.get('playbook_config_override')
    playbook_config_incorrect_vrfid = test_data.get('playbook_config_incorrect_vrfid')
    playbook_config_replace = test_data.get('playbook_config_replace')
    playbook_config_replace_no_atch = test_data.get('playbook_config_replace_no_atch')
    mock_vrf_attach_object_del_not_ready = test_data.get('mock_vrf_attach_object_del_not_ready')
    mock_vrf_attach_object_del_oos = test_data.get('mock_vrf_attach_object_del_oos')
    mock_vrf_attach_object_del_ready = test_data.get('mock_vrf_attach_object_del_ready')

    attach_success_resp = test_data.get('attach_success_resp')
    deploy_success_resp = test_data.get('deploy_success_resp')
    get_have_failure = test_data.get('get_have_failure')
    error1 = test_data.get('error1')
    error2 = test_data.get('error2')
    error3 = test_data.get('error3')
    delete_success_resp = test_data.get('delete_success_resp')

    def init_data(self):
        # Some of the mock data is re-initialized after each test as previous test might have altered portions
        # of the mock data.

        self.mock_vrf_object = copy.deepcopy(self.test_data.get('mock_vrf_object'))
        self.mock_vrf_attach_object = copy.deepcopy(self.test_data.get('mock_vrf_attach_object'))
        self.mock_vrf_attach_object_pending = copy.deepcopy(self.test_data.get('mock_vrf_attach_object_pending'))
        self.mock_vrf_object_dcnm_only = copy.deepcopy(self.test_data.get('mock_vrf_object_dcnm_only'))
        self.mock_vrf_attach_object_dcnm_only = copy.deepcopy(self.test_data.get('mock_vrf_attach_object_dcnm_only'))


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

        if 'vrf_blank_fabric' in self._testMethodName:
            self.run_dcnm_ip_sn.side_effect = [{}]
        else:
            self.run_dcnm_ip_sn.side_effect = [self.mock_ip_sn]

        if 'get_have_failure' in self._testMethodName:
            self.run_dcnm_send.side_effect = [self.get_have_failure]

        elif '_check_mode' in self._testMethodName:
            self.run_dcnm_send.side_effect = [{'DATA':{}}, {}]

        elif '_merged_new' in self._testMethodName:
            self.run_dcnm_send.side_effect = [{'DATA': {}}, {}, self.attach_success_resp, self.deploy_success_resp]

        elif 'error1' in self._testMethodName:
            self.run_dcnm_send.side_effect = [{'DATA': {}}, {}, self.error1, self.deploy_success_resp]

        elif 'error2' in self._testMethodName:
            self.run_dcnm_send.side_effect = [{'DATA': {}}, {}, self.error2, self.deploy_success_resp]

        elif 'error3' in self._testMethodName:
            self.run_dcnm_send.side_effect = [{'DATA': {}}, {}, self.attach_success_resp, self.error3]

        elif '_merged_duplicate' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        elif '_merged_with_incorrect' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        elif '_merged_with_update' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object,
                                              self.attach_success_resp, self.deploy_success_resp]

        elif '_merged_redeploy' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object_pending,
                                              self.deploy_success_resp]

        elif 'replace_with_no_atch' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object,
                                              self.attach_success_resp, self.deploy_success_resp,
                                              self.delete_success_resp]

        elif 'replace_with_changes' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object,
                                              self.attach_success_resp, self.deploy_success_resp,
                                              self.delete_success_resp]

        elif 'replace_without_changes' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        elif 'override_with_additions' in self._testMethodName:
            self.run_dcnm_send.side_effect = [{'DATA':{}}, {}, self.attach_success_resp,
                                              self.deploy_success_resp]

        elif 'override_with_deletions' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object, {},
                                              self.attach_success_resp, self.deploy_success_resp,
                                              self.mock_vrf_attach_object_del_not_ready,
                                              self.mock_vrf_attach_object_del_ready,
                                              self.delete_success_resp]

        elif 'override_without_changes' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        elif 'delete_std' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object,
                                              self.attach_success_resp, self.deploy_success_resp,
                                              self.mock_vrf_attach_object_del_not_ready,
                                              self.mock_vrf_attach_object_del_ready,
                                              self.delete_success_resp]

        elif 'delete_failure' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object,
                                              self.attach_success_resp, self.deploy_success_resp,
                                              self.mock_vrf_attach_object_del_not_ready,
                                              self.mock_vrf_attach_object_del_oos]

        elif 'delete_dcnm_only' in self._testMethodName:
            self.init_data()
            obj1 = copy.deepcopy(self.mock_vrf_attach_object_del_not_ready)
            obj2 = copy.deepcopy(self.mock_vrf_attach_object_del_ready)

            obj1['DATA'][0].update({'vrfName': 'test_vrf_dcnm'})
            obj2['DATA'][0].update({'vrfName': 'test_vrf_dcnm'})

            self.run_dcnm_send.side_effect = [self.mock_vrf_object_dcnm_only, self.mock_vrf_attach_object_dcnm_only,
                                              self.attach_success_resp, self.deploy_success_resp,
                                              obj1,
                                              obj2,
                                              self.delete_success_resp]

        elif 'query' in self._testMethodName:
            self.init_data()
            self.run_dcnm_send.side_effect = [self.mock_vrf_object, self.mock_vrf_attach_object]

        else:
            pass

    def test_00dcnm_vrf_blank_fabric(self):
        set_module_args(dict(state='merged',
                             fabric='test_fabric', config=self.playbook_config))
        result = self.execute_module(changed=False, failed=True)
        self.assertEqual(result.get('msg'), 'Fabric test_fabric missing on DCNM or does not have any switches')

    def test_01dcnm_vrf_get_have_failure(self):
        set_module_args(dict(state='merged',
                             fabric='test_fabric', config=self.playbook_config))
        result = self.execute_module(changed=False, failed=True)
        self.assertEqual(result.get('msg'), 'Fabric test_fabric not present on DCNM')

    def test_02dcnm_vrf_merged_redeploy(self):
        set_module_args(dict(state='merged',
                             fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=True, failed=False)

    def test_03dcnm_vrf_check_mode(self):
        set_module_args(dict(_ansible_check_mode=True, state='merged',
                             fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=True, failed=False)

    def test_04dcnm_vrf_merged_new(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=True, failed=False)

    def test_05dcnm_vrf_merged_duplicate(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=False, failed=False)

    def test_06dcnm_vrf_merged_with_incorrect_vrfid(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config_incorrect_vrfid))
        result = self.execute_module(changed=False, failed=True)
        self.assertEqual(result.get('msg'), 'vrf_id for VRF:test_vrf_1 cant be updated to a different value')

    def test_07dcnm_vrf_merged_with_update(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config_update))
        self.execute_module(changed=True, failed=False)

    def test_08dcnm_vrf_merged_with_update_vlan(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config_update_vlan))
        self.execute_module(changed=True, failed=False)

    def test_09dcnm_vrf_error1(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=False, failed=True)

    def test_10dcnm_vrf_error2(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=False, failed=True)

    def test_11dcnm_vrf_error3(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=False, failed=False)

    def test_12dcnm_vrf_replace_with_changes(self):
        set_module_args(dict(state='replaced', fabric='test_fabric', config=self.playbook_config_replace))
        self.execute_module(changed=True, failed=False)

    def test_13dcnm_vrf_replace_with_no_atch(self):
        set_module_args(dict(state='replaced', fabric='test_fabric', config=self.playbook_config_replace_no_atch))
        self.execute_module(changed=True, failed=False)

    def test_14dcnm_vrf_replace_without_changes(self):
        set_module_args(dict(state='replaced', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=False, failed=False)

    def test_15dcnm_vrf_override_with_additions(self):
        set_module_args(dict(state='overridden', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=True, failed=False)

    def test_16dcnm_vrf_override_with_deletions(self):
        set_module_args(dict(state='overridden', fabric='test_fabric', config=self.playbook_config_override))
        self.execute_module(changed=True, failed=False)

    def test_17dcnm_vrf_override_without_changes(self):
        set_module_args(dict(state='overridden', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=False, failed=False)

    def test_18dcnm_vrf_delete_std(self):
        set_module_args(dict(state='deleted', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=True, failed=False)

    def test_19dcnm_vrf_delete_dcnm_only(self):
        set_module_args(dict(state='deleted', fabric='test_fabric', config=[]))
        self.execute_module(changed=True, failed=False)

    def test_20dcnm_vrf_delete_failure(self):
        set_module_args(dict(state='deleted', fabric='test_fabric', config=self.playbook_config))
        result = self.execute_module(changed=False, failed=True)
        self.assertEqual(result.get('msg'), 'Deletion of VRFs test_vrf_1 has failed')

    def test_21dcnm_vrf_query(self):
        set_module_args(dict(state='query', fabric='test_fabric', config=self.playbook_config))
        self.execute_module(changed=False, failed=False)

    def test_22dcnm_vrf_validation(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=self.playbook_config_input_validation))
        self.execute_module(changed=False, failed=True)

    def test_23dcnm_vrf_validation_no_config(self):
        set_module_args(dict(state='merged', fabric='test_fabric', config=[]))
        result = self.execute_module(changed=False, failed=True)
        self.assertEqual(result.get('msg'), 'config: element is mandatory for this state merged')