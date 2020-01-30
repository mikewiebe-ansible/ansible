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
from ansible.module_utils.connection import Connection
from ansible.module_utils.basic import AnsibleModule

__copyright__ = "Copyright (c) 2019 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.0"
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
  vrfName:
    description:
    - 'Name of the VRF being created'
    type: str
    required: yes
  vrfTemplate:
    description:
    - 'Name of the config template to be used'
    type: str
    required: no
    default: Default_VRF_Universal
  vrfExtensionTemplate:
    description:
    - 'Name of the extension config template to be used'
    type: str
    required: no
    default: Default_VRF_Extension_Universal
  vrfTemplateConfig:
    description:
    - 'Any additional configs to be supplied'
    type: str
    required: no
  vrfId:
    description:
    - 'Unique ID for the VRF'
    type: int
    required: yes
  serialNumbersVlans:
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
    vrfName: ansible-vrf
    vrfTemplate: Default_VRF_Universal
    vrfExtensionTemplate: Default_VRF_Extension_Universal
    vrfTemplateConfig: ""
    vrfId: 9000010

- name: Attach VRF to single switch
  dcnm_vrf:
    action: attach
    fabric: vxlan-fabric
    vrfName: ansible-vrf
    serialNumbersVlans:
      - XXXXYYYY: 103
    deployment: False

- name: Attach VRF to multiple switches
  dcnm_vrf:
    action: attach
    fabric: vxlan-fabric
    vrfName: ansible-vrf
    serialNumbersVlans:
      - XXXXYYYY: 103
      - YYYYXXXX: 104
      - ZZZXXXYY: 103
    deployment: False

- name: Deploy VRF
  dcnm_vrf:
    action: deploy
    fabric: vxlan-fabric
    vrfName: ansible-vrf
'''


def check_vrf_exists(module, conn):

    fabric = module.params['fabric']
    vrf = module.params['vrfName']
    path = '/rest/top-down/fabrics/' + fabric + '/vrfs/' + vrf

    response = conn.send_request('GET', path)

    if isinstance(response, dict):
        if response['vrfName'] == vrf:
            return True

    if isinstance(response, list):
        if response[0]:
            if response[0].get('ERROR') == 'Bad Request':
                return False


def vrf_create_payload(module):

    payload = dict()
    payload['fabric'] = module.params['fabric']
    payload['vrfName'] = module.params['vrfName']
    payload['vrfTemplate'] = module.params['vrfTemplate']
    payload['vrfExtensionTemplate'] = module.params['vrfExtensionTemplate']
    payload['vrfTemplateConfig'] = module.params['vrfTemplateConfig']
    payload['vrfId'] = module.params['vrfId']

    json_data = json.dumps(payload)

    return json_data


def vrf_attach_payload(module):

    payload_list = list()
    payload = dict()
    payload['vrfName'] = module.params['vrfName']
    payload['lanAttachList'] = list()

    for serials in module.params['serialNumbersVlans']:
        for serial, vlan in serials.items():
            device_payload = dict()
            device_payload['fabric'] = module.params['fabric']
            device_payload['vrfName'] = module.params['vrfName']
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
    payload['vrfNames'] = module.params['vrfName']

    json_data = json.dumps(payload)

    return json_data


def main():
    """ main entry point for module execution
    """

    element_spec = dict(
        action=dict(required=True, choices=['create', 'attach', 'deploy']),
        fabric=dict(required=True, type='str'),
        vrfName=dict(required=True, type='str'),
        vrfTemplate=dict(default='Default_VRF_Universal', type='str'),
        vrfExtensionTemplate=dict(default='Default_VRF_Extension_Universal', type='str'),
        vrfTemplateConfig=dict(default='', type='str'),
        vrfId=dict(type=int),
        serialNumbersVlans=dict(type='list'),
        deployment=dict(default=False, type='bool')
    )

    required_one_of = [['vrfId', 'vrfName']]
    mutually_exclusive = [['vrfId'],
                          ['serialNumbersVlans']]

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
    create_path = '/rest/top-down/fabrics/' + fabric + '/vrfs'
    attach_path = '/rest/top-down/fabrics/' + fabric + '/vrfs/attachments'
    deploy_path = '/rest/top-down/fabrics/' + fabric + '/vrfs/deployments'

    conn = Connection(module._socket_path)

    if action == 'create':
        if not check_vrf_exists(module, conn):
            json_data = vrf_create_payload(module)
            result['response'] = conn.send_request(method, create_path, json_data)
            result['changed'] = True
        else:
            result['changed'] = False
    elif action == 'attach':
        json_data = vrf_attach_payload(module)
        result['response'] = conn.send_request(method, attach_path, json_data)
        result['changed'] = True
    else:
        json_data = vrf_deploy_payload(module)
        result['response'] = conn.send_request(method, deploy_path, json_data)
        result['changed'] = True

    if isinstance(result['response'], list):
        if result['response']:
            resp = list()
            if result['response'][0].get('ERROR'):
                resp.append(result['response'][0])
                if action == 'create':
                    resp.append("VRF ID is already in use")
                module.fail_json(msg=resp)

    if isinstance(result['response'], dict):
        if action == 'attach':
            if 'is in use already' in str(result['response'].values()):
                result['changed'] = False
                module.fail_json(msg=result['response'])

    module.exit_json(**result)


if __name__ == '__main__':
    main()
