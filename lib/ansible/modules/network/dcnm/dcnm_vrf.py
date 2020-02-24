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

import json
from ansible.module_utils.network.dcnm.dcnm import dcnm_send
from ansible.module_utils.basic import AnsibleModule

__copyright__ = "Copyright (c) 2020 Cisco and/or its affiliates."
__author__ = "Shrishail Kariyappanavar"


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: dcnm_vrf
short_description: Send REST API requests to DCNM controller for VRF operations
version_added: "2.10"
description:
    - "Send REST API requests to DCNM controller for VRF operations - Create, Attach, Deploy"
options:
  action:
    description:
    - 'Intended VRF operation - Create, Attach or Deploy'
    choices: ['Create', 'Attach', 'Deploy']
    required: yes
    type: str
  fabric:
    description:
    - 'Name of the target fabric for VRF operations'
    type: str
    required: yes
  vrf_name:
    description:
    - 'Name of the VRF being created'
    type: str
    required: yes
  vrf_template:
    description:
    - 'Name of the config template to be used'
    type: str
    required: no
    default: Default_VRF_Universal
  vrf_extension_template:
    description:
    - 'Name of the extension config template to be used'
    type: str
    required: no
    default: Default_VRF_Extension_Universal
  vrf_template_config:
    description:
    - 'Any additional configs to be supplied'
    type: str
    required: no
  vrf_id:
    description:
    - 'Unique ID for the VRF'
    type: int
    required: yes
  serial_numbers_vlans:
    description:
    - 'Serial number of the target switch for the VRF and VLAN ID to be used'
    type: list
    required: yes
  deployment:
    description:
    - 'Deploy after attach or just attach'
    type: bool
    required: no
    default: False
author:
    -  Shrishail Kariyappanavar(@nkshrishail)
'''

EXAMPLES = '''
- name: Create VRF
  dcnm_vrf:
    action: create
    fabric: vxlan-fabric
    vrf_name: ansible-vrf
    vrf_template: Default_VRF_Universal
    vrf_extension_template: Default_VRF_Extension_Universal
    vrf_template_config: ""
    vrf_id: 9000010

- name: Attach VRF to single switch
  dcnm_vrf:
    action: attach
    fabric: vxlan-fabric
    vrf_name: ansible-vrf
    serial_numbers_vlans:
      - XXXXYYYY: 103
    deployment: False

- name: Attach VRF to multiple switches
  dcnm_vrf:
    action: attach
    fabric: vxlan-fabric
    vrf_name: ansible-vrf
    serial_numbers_vlans:
      - XXXXYYYY: 103
      - YYYYXXXX: 104
      - ZZZXXXYY: 103
    deployment: False

- name: Deploy VRF
  dcnm_vrf:
    action: deploy
    fabric: vxlan-fabric
    vrf_name: ansible-vrf
'''


def check_vrf_exists(module):

    fabric = module.params['fabric']
    vrf = module.params['vrf_name']
    path = '/rest/top-down/fabrics/{}/vrfs/{}'.format(fabric, vrf)

    response = dcnm_send(module, 'GET', path)

    if isinstance(response, dict):
        if response.get('vrfName') == vrf:
            return True

    if isinstance(response, list):
        if response and response[0]:
            if response[0].get('ERROR') == 'Bad Request':
                return False

    return False


def vrf_create_payload(module):

    payload = dict()
    payload['fabric'] = module.params['fabric']
    payload['vrfName'] = module.params['vrf_name']
    payload['vrfTemplate'] = module.params['vrf_template']
    payload['vrfExtensionTemplate'] = module.params['vrf_extension_template']
    payload['vrfTemplateConfig'] = module.params['vrf_template_config']
    payload['vrfId'] = module.params['vrf_id']

    json_data = json.dumps(payload)

    return json_data


def vrf_attach_payload(module):

    payload_list = list()
    payload = dict()
    payload['vrfName'] = module.params['vrf_name']
    payload['lanAttachList'] = list()

    for serials in module.params['serial_numbers_vlans']:
        for serial, vlan in serials.items():
            device_payload = dict()
            device_payload['fabric'] = module.params['fabric']
            device_payload['vrfName'] = module.params['vrf_name']
            device_payload['serialNumber'] = serial
            device_payload['vlan'] = vlan
            device_payload['deployment'] = module.params['deployment']
            device_payload['extensionValues'] = ""
            device_payload['instanceValues'] = ""
            device_payload['freeformConfig'] = ""

        payload['lanAttachList'].append(device_payload)

    payload_list.append(payload)
    json_data = json.dumps(payload_list)

    return json_data


def vrf_deploy_payload(module):

    payload = dict()
    payload['vrfNames'] = module.params['vrf_name']

    json_data = json.dumps(payload)

    return json_data



def main():
    """ main entry point for module execution
    """

    element_spec = dict(
        action=dict(required=True, choices=['create', 'attach', 'deploy']),
        fabric=dict(required=True, type='str'),
        vrf_name=dict(required=True, type='str'),
        vrf_template=dict(default='Default_VRF_Universal', type='str'),
        vrf_extension_template=dict(default='Default_VRF_Extension_Universal', type='str'),
        vrf_template_config=dict(default='', type='str'),
        vrf_id=dict(type=int),
        serial_numbers_vlans=dict(type='list'),
        deployment=dict(default=False, type='bool')
    )

    required_one_of = [['vrf_id', 'vrf_name']]
    mutually_exclusive = [['vrf_id'],
                          ['serial_numbers_vlans']]

    module = AnsibleModule(argument_spec=element_spec,
                           required_one_of=required_one_of,
                           mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)

    result = dict(
        changed=False,
        response=dict()
    )

    action = module.params['action']
    fabric = module.params['fabric']

    method = 'POST'
    path = '/rest/top-down/fabrics/{}/vrfs'.format(fabric)

    if action == 'create':
        if not check_vrf_exists(module):
            json_data = vrf_create_payload(module)
            result['response'] = dcnm_send(module, method, path, json_data)
            result['changed'] = True
        else:
            result['changed'] = False
    elif action == 'attach':
        json_data = vrf_attach_payload(module)
        path += '/attachments'
        result['response'] = dcnm_send(module, method, path, json_data)
        result['changed'] = True
    else:
        json_data = vrf_deploy_payload(module)
        path += '/deployments'
        result['response'] = dcnm_send(module, method, path, json_data)
        result['changed'] = True

    res = result['response']

    if res and isinstance(res, list) and res[0].get('ERROR'):
        vrf_dupe = "VRF ID is already in use" if (action == 'create') else ''
        module.fail_json(msg=[res[0], vrf_dupe])

    if res and isinstance(res, dict):
        if action == 'attach' and 'is in use already' in str(res.values()):
            result['changed'] = False
            module.fail_json(msg=res)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
