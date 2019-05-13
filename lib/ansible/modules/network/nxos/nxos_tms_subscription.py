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
module: nxos_tms_subscription
extends_documentation_fragment: nxos
version_added: "2.9"
short_description: Telemetry Monitoring Service (TMS) subscription configuration
description:
  - Manages Telemetry Monitoring Service (TMS) subscription configuration.

author: Mike Wiebe (@mikewiebe)
notes:
    - Tested against <TBD>
    - Not supported on N3K/N5K/N6K/N7K
    - Module will automatically enable 'feature telemetry' if it is disabled.
options:
  identifier:
    description:
      - Subscription identifier.
      - Value must be a int representing the subscription identifier.
    required: true
    type: int
  destination_group:
    description:
      - Associated destination group.
      - Value must be a int representing the associated destination group.
    required: false
    type: int
  sensor_group:
    description:
      - Associated sensor group.
      - Value must be a dict defining values for keys: id, sample_interval.
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
- nxos_tms_destgroup:
    identifier: 5
    destination_group: 4
    sensor_group:
      id: 3
      sampe_interval: 1000
'''

RETURN = '''
cmds:
    description: commands sent to the device
    returned: always
    type: list
    sample: ["telemetry", "subscription 5", "dst-grp 5"]
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
  getval: subscription (\S+)$
  setval: 'subscription {0}'
  default: ~

destination_group:
  _exclude: ['N3K', 'N5K', 'N6k', 'N7k']
  kind: int
  getval: dst-grp (\S+)$
  setval: 'dst-grp {0}'
  default: ~
  context: ['telemetry', 'setval::identifier']

sensor_group:
  _exclude: ['N3K', 'N5K', 'N6k', 'N7k']
  kind: dict
  getval: snsr-grp (?P<id>\S+) sample-interval (?P<sample_interval>\S+)$
  setval: snsr-grp {id} sample-interval {sample_interval}
  default:
    id: ~
    sample_interval: ~
  context: ['telemetry', 'setval::identifier']
"""


def main():
    argument_spec = dict(
        identifier=dict(required=True, type='int'),
        destination_group=dict(required=True, type='int'),
        sensor_group=dict(required=False, type='dict'),
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
