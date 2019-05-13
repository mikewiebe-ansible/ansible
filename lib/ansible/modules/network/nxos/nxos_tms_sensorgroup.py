#!/usr/bin/python
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
#

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = '''
---
module: nxos_tms_sensorgroup
extends_documentation_fragment: nxos
version_added: "2.9"
short_description: Telemetry Monitoring Service (TMS) sensor-group configuration
description:
  - Manages Telemetry Monitoring Service (TMS) sensor-group configuration.

author: Mike Wiebe (@mikewiebe)
notes:
    - Tested against <TBD>
    - Not supported on N3K/N5K/N6K/N7K
    - Module will automatically enable 'feature telemetry' if it is disabled.
options:
  identifier:
    description:
      - Sensor group identifier.
      - Value must be a int representing the sensor group identifier.
    required: true
    type: int
  data_source:
    description:
      - Telemetry data source.
      - Valid value is a str representing the data source.
    required: false
    choices: ['NX-API', 'DME']
  path:
    description:
      - Telemetry sensor path.
      - Value must be a dict defining values for keys: name, depth, filter_condition, query_condition.
    required: false
    type: dict
  state:
    description:
      - Maka configuration present or absent on the device.
    required: false
    choices: ['present', 'absent']
    default: ['present']
'''
EXAMPLES = '''
- nxos_tms_sensorgroup:
    identifier: 2
    data_source: nxapi
    path:
      name: 'sys/bgp/inst/dom-default/peer-[10.10.10.11/ent-[10.10.10.11]]'
      depth: 0
      filter_condition: 'or(eq(ethpmPhysIf.operSt,"down"),eq(ethpmPhysIf.operSt,"up"))'
      query_condition: query_condition
'''

RETURN = '''
cmds:
    description: commands sent to the device
    returned: always
    type: list
    sample: ["telemetry", "sensor-group 4", "data-source NX-API"]
'''

import re, yaml
from ansible.module_utils.network.nxos.nxos import NxosCmdRef
from ansible.module_utils.network.nxos.nxos import nxos_argument_spec, check_args
from ansible.module_utils.network.nxos.nxos import load_config, run_commands
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.common.config import CustomNetworkConfig

TMS_CMD_REF = """
# The cmd_ref is a yaml formatted list of module commands.
# A leading underscore denotes a non-command variable; e.g. _template.
# TBD: Use Structured
#    TMS does not have convenient json data so this cmd_ref uses raw cli configs.
---
_template: # _template holds common settings for all commands
  # Enable feature telemetry if disabled
  feature: telemetry
  # Common get syntax for TMS commands
  get_command: show run telemetry all
  # Parent configuration for TMS commands
  context:
    - telemetry

identifier:
  _exclude: ['N3K', 'N5K', 'N6k', 'N7k']
  kind: int
  getval: sensor-group (\S+)$
  setval: 'sensor-group {0}'
  default: ~

data_source:
  _exclude: ['N3K', 'N5K', 'N6k', 'N7k']
  kind: str
  getval: data-source (\S+)$
  setval: 'data-source {0}'
  default: ~
  context: ['telemetry', 'setval::identifier']

path:
  _exclude: ['N3K', 'N5K', 'N6k', 'N7k']
  kind: dict
  getval: path (?P<name>\S+) depth (?P<depth>\S+) query-condition (?P<query_condition>\S+) filter-condition (?P<filter_condition>\S+)$
  setval: path {name} depth {depth} query-condition {query_condition} filter-condition {filter_condition}
  default:
    name: ~
    depth: ~
    query_condition: ~
    filter_condition: ~
  context: ['telemetry', 'setval::identifier']
"""


def main():
    argument_spec = dict(
        identifier=dict(required=True, type='int'),
        data_source=dict(choices=['NX-API', 'DME'], required=False),
        path=dict(required=False, type='dict'),
        state=dict(choices=['present', 'absent'], default='present', required=False),
    )
    argument_spec.update(nxos_argument_spec)
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    warnings = list()
    check_args(module, warnings)

    cmd_ref = NxosCmdRef(module, TMS_CMD_REF)
    cmd_ref.get_existing()
    cmd_ref.get_playvals()
    cmds = cmd_ref.get_proposed()

    result = {'changed': False, 'commands': cmds, 'warnings': warnings,
              'check_mode': module.check_mode}
    if cmds:
        result['changed'] = True
        if not module.check_mode:
            load_config(module, cmds)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
