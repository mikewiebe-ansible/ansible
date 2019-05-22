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
module: nxos_tms_global
extends_documentation_fragment: nxos
version_added: "2.9"
short_description: Telemetry Monitoring Service (TMS) global-level configuration
description:
  - Manages Telemetry Monitoring Service (TMS) global-level configuration.

author: Mike Wiebe (@mikewiebe)
notes:
    - Tested against <TBD>
    - Not supported on N3K/N5K/N6K/N7K
    - Module will automatically enable 'feature telemetry' if it is disabled.
options:
  # Top-level commands
  certificate:
    description:
      - Certificate SSL/TLS and hostname values.
      - Value must be a dict defining values for keys: key and hostname.
    required: false
    type: dict
  destination_profile_compression:
    description:
      - Destination compression method.
    required: false
    choices: ['gzip']
  destination_profile_vrf:
    description:
      - Destination VRF.
        Valid value is a str representing the vrf name.
    required: false
    type: str
  purge:
    description:
      - Remove any nxos_tms_global configuration that does not match playbook
    required: false
    type: bool
    default: false
  state:
    description:
      - Make configuration present or absent on the device.
    required: false
    choices: ['present', 'absent']
    default: ['present']
'''
EXAMPLES = '''
- nxos_tms_global:
    certificate:
      key: /bootflash/server.key
      hostname: localhost
    destination_profile_compression: gzip
    destination_profile_vrf: management
'''

RETURN = '''
cmds:
    description: commands sent to the device
    returned: always
    type: list
    sample: ["telemetry", "certificate /bootflash/server.key localhost"]
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
# TMS does not have convenient json data so this cmd_ref uses raw cli configs.
---
_template: # _template holds common settings for all commands
  # Enable feature telemetry if disabled
  feature: telemetry
  # Common get syntax for TMS commands
  get_command: show run telemetry all
  # Parent configuration for TMS commands
  context:
    - telemetry

certificate:
  _exclude: ['N3K', 'N5K', 'N6k', 'N7k']
  kind: dict
  getval: certificate (?P<key>\S+) (?P<hostname>\S+)$
  setval: certificate {key} {hostname}
  default:
    key: ~
    hostname: ~

destination_profile_compression:
  _exclude: ['N3K', 'N5K', 'N6k', 'N7k']
  kind: str
  getval: use-compression (\S+)$
  setval: 'use-compression {1}'
  default: ~
  context: [telemetry, destination-profile]

destination_profile_vrf:
  _exclude: ['N3K', 'N5K', 'N6k', 'N7k']
  kind: str
  getval: use-vrf (\S+)$
  setval: 'use-vrf {1}'
  default: ~
  context: [telemetry, destination-profile]
"""


def main():
    argument_spec = dict(
        certificate=dict(required=False, type='dict'),
        destination_profile_compression=dict(required=False, type='str', choices=['gzip']),
        destination_profile_vrf=dict(required=False, type='str'),
        purge=dict(default=False, type='bool'),
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
