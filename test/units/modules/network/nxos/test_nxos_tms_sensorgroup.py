# (c) 2019 Red Hat Inc.
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
from ansible.modules.network.nxos import nxos_tms_sensorgroup
from ansible.module_utils.network.nxos.nxos import NxosCmdRef
from .nxos_module import TestNxosModule, load_fixture, set_module_args

# TBD: These imports / import checks are only needed as a workaround for
# shippable, which fails this test due to import yaml & import ordereddict.
import pytest
from ansible.module_utils.network.nxos.nxos import nxosCmdRef_import_check
msg = nxosCmdRef_import_check()


@pytest.mark.skipif(len(msg), reason=msg)
class TestNxosTmsSensorgroupModule(TestNxosModule):

    module = nxos_tms_sensorgroup

    def setUp(self):
        super(TestNxosTmsSensorgroupModule, self).setUp()

        self.mock_load_config = patch('ansible.modules.network.nxos.nxos_tms_sensorgroup.load_config')
        self.load_config = self.mock_load_config.start()

        self.mock_execute_show_command = patch('ansible.module_utils.network.nxos.nxos.NxosCmdRef.execute_show_command')
        self.execute_show_command = self.mock_execute_show_command.start()

        self.mock_get_platform_shortname = patch('ansible.module_utils.network.nxos.nxos.NxosCmdRef.get_platform_shortname')
        self.get_platform_shortname = self.mock_get_platform_shortname.start()

    def tearDown(self):
        super(TestNxosTmsSensorgroupModule, self).tearDown()
        self.mock_load_config.stop()
        self.execute_show_command.stop()
        self.get_platform_shortname.stop()

    def load_fixtures(self, commands=None, device=''):
        self.load_config.return_value = None

    def test_tms_sensorgroup_present_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        self.execute_show_command.return_value = None
        set_module_args(dict(
            identifier='77',
            data_source='DME',
            path={'name': 'sys/bgp', 'depth': 0, 'query_condition': 'query_condition_xyz', 'filter_condition': 'filter_condition_xyz'}
        ))
        self.execute_module(changed=True, commands=[
            'feature telemetry',
            'telemetry',
            'sensor-group 77',
            'data-source DME',
            'path sys/bgp depth 0 query-condition query_condition_xyz filter-condition filter_condition_xyz',
        ])

    def test_tms_sensorgroup_present_variable_args1_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        # Only path key name provided
        self.execute_show_command.return_value = None
        set_module_args(dict(
            identifier='77',
            data_source='DME',
            path={'name': 'sys/bgp'}
        ))
        self.execute_module(changed=True, commands=[
            'feature telemetry',
            'telemetry',
            'sensor-group 77',
            'data-source DME',
            'path sys/bgp',
        ])

    def test_tms_sensorgroup_present_variable_args2_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        # Only path keys name and depth provided
        self.execute_show_command.return_value = None
        set_module_args(dict(
            identifier='77',
            data_source='DME',
            path={'name': 'sys/bgp', 'depth': 0}
        ))
        self.execute_module(changed=True, commands=[
            'feature telemetry',
            'telemetry',
            'sensor-group 77',
            'data-source DME',
            'path sys/bgp depth 0',
        ])

    def test_tms_sensorgroup_present_variable_args3_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        # Only path keys name, depth and query_condition provided
        self.execute_show_command.return_value = None
        set_module_args(dict(
            identifier='77',
            data_source='DME',
            path={'name': 'sys/bgp', 'depth': 0, 'query_condition': 'query_condition_xyz'}
        ))
        self.execute_module(changed=True, commands=[
            'feature telemetry',
            'telemetry',
            'sensor-group 77',
            'data-source DME',
            'path sys/bgp depth 0 query-condition query_condition_xyz',
        ])

    def test_tms_sensorgroup_present_variable_args4_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        # Only path keys name, depth and filter_condition provided
        self.execute_show_command.return_value = None
        set_module_args(dict(
            identifier='77',
            data_source='DME',
            path={'name': 'sys/bgp', 'depth': 0, 'filter_condition': 'filter_condition_xyz'}
        ))
        self.execute_module(changed=True, commands=[
            'feature telemetry',
            'telemetry',
            'sensor-group 77',
            'data-source DME',
            'path sys/bgp depth 0 filter-condition filter_condition_xyz',
        ])

    def test_tms_sensorgroup_present_path_environment_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        # Only path keys name, depth and filter_condition provided
        self.execute_show_command.return_value = None
        set_module_args(dict(
            identifier='77',
            data_source='YANG',
            path={'name': 'environment'}
        ))
        self.execute_module(changed=True, commands=[
            'feature telemetry',
            'telemetry',
            'sensor-group 77',
            'data-source YANG',
            'path environment',
        ])

    def test_tms_sensorgroup_present_path_interface_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        # Only path keys name, depth and filter_condition provided
        self.execute_show_command.return_value = None
        set_module_args(dict(
            identifier='77',
            data_source='NATIVE',
            path={'name': 'interface'}
        ))
        self.execute_module(changed=True, commands=[
            'feature telemetry',
            'telemetry',
            'sensor-group 77',
            'data-source NATIVE',
            'path interface',
        ])

    def test_tms_sensorgroup_present_path_resources_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        # Only path keys name, depth and filter_condition provided
        self.execute_show_command.return_value = None
        set_module_args(dict(
            identifier='77',
            data_source='NX-API',
            path={'name': 'resources'}
        ))
        self.execute_module(changed=True, commands=[
            'feature telemetry',
            'telemetry',
            'sensor-group 77',
            'data-source NX-API',
            'path resources',
        ])

    def test_tms_sensorgroup_vxlan_idempotent_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is not present.
        # Only path keys name, depth and filter_condition provided
        self.execute_show_command.return_value = load_fixture('nxos_tms', 'N9K.cfg')
        set_module_args(dict(
            identifier='56',
            path={'name': 'vxlan'}
        ))
        self.execute_module(changed=False)

    def test_tms_sensorgroup_idempotent_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is present.
        self.execute_show_command.return_value = load_fixture('nxos_tms', 'N9K.cfg')
        set_module_args(dict(
            identifier='2',
            data_source='DME',
            path={'name': 'sys/ospf', 'depth': 0, 'query_condition': 'qc', 'filter_condition': 'fc'}
        ))
        self.execute_module(changed=False)

    def test_tms_sensorgroup_idempotent_variable1_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is present with path key name.
        self.execute_show_command.return_value = load_fixture('nxos_tms', 'N9K.cfg')
        set_module_args(dict(
            identifier='2',
            data_source='DME',
            path={'name': 'sys/bgp/inst/dom-default/peer-[10.10.10.11]/ent-[10.10.10.11]'}
        ))
        self.execute_module(changed=False)

    def test_tms_sensorgroup_idempotent_variable2_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is present with path key name and depth.
        self.execute_show_command.return_value = load_fixture('nxos_tms', 'N9K.cfg')
        set_module_args(dict(
            identifier='2',
            data_source='DME',
            path={'name': 'boo', 'depth': 0}
        ))
        self.execute_module(changed=False)

    def test_tms_sensorgroup_absent_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is present.
        # Make absent with all playbook keys provided
        self.execute_show_command.return_value = load_fixture('nxos_tms', 'N9K.cfg')
        set_module_args(dict(
            state='absent',
            identifier='2',
            data_source='DME',
            path={'name': 'sys/ospf', 'depth': 0, 'query_condition': 'qc', 'filter_condition': 'fc'}
        ))
        self.execute_module(changed=True, commands=[
            'telemetry',
            'no sensor-group 2'
        ])

    def test_tms_sensorgroup_absent2_n9k(self):
        # Assumes feature telemetry is enabled
        # TMS sensorgroup config is present.
        # Make absent with only identifier playbook keys provided
        self.execute_show_command.return_value = load_fixture('nxos_tms', 'N9K.cfg')
        set_module_args(dict(
            state='absent',
            identifier='2',
        ))
        self.execute_module(changed=True, commands=[
            'telemetry',
            'no sensor-group 2'
        ])
