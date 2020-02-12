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
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection
from ansible.module_utils.network.common.utils import dict_diff

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}

DOCUMENTATION = '''
---
Will fill it up.
'''

EXAMPLES = '''
# TBD: THIS FORMAT WILL LIKELY CHANGE TO RMB
- name: foo
  dcnm_network:
    state: merged
    fabric: cvh3
    net_name: c1
    net_id: 31120                 # VNI, optional: can autogenerate
    vrf: MyVRF_50000
    # template: Default_Network_Universal                 # optional
    # template_ext: Default_Network_Extension_Universal   # optional
    # gw_ip: '201.1.1.1/24'
    vlan_id: 2305                 # optional: can be empty
    attach:
      - 10.122.192.197:
        ports:
          - "Ethernet1/1,Ethernet1/2"
        deploy: false
'''

import datetime
def logit(msg):
    with open('/tmp/logit.txt', 'a') as of:
        of.write("---- _network: %s\n" % (msg))

def send(net_obj, method, path, payload=None):
    logit('send: path: %s' %path)
    if payload:
        resp = net_obj['conn'].send_request(method, path, payload)
    else:
        resp = net_obj['conn'].send_request(method, path)
    if isinstance(resp, dict):
        return resp
    elif isinstance(resp, list):
        if resp[0].get('ERROR') == 'Bad Request':
            # object does not exist
            return {}
        else:
            return resp
    else:
        import epdb;epdb.serve()
        raise Exception('foo')

def get_facts(net_obj):
    """Check for existing network, attached state, and deployed state."""
    conn = net_obj['conn']
    params = net_obj['params']

    path = '/rest/top-down/fabrics/{}/networks/{}/status'.format(params['fabric'], params['net_name'])
    net_obj['have'] = send(net_obj, 'GET', path)
    logit('get_facts:response: %s' %net_obj['have'])

    # FOLLOWING CODE CAN BE REMOVED
    # Check for existing network
    # path = net_obj['path'] + '/' + net_name
    # have['net'] = send(net_obj, 'GET', path)
    # logit('get_net:response: %s' %have['net'])
    #
    # Check for attach state
    # if have['net']:
    #     attach_path = path + '/' + 'attachments'
    #     have['attach'] = send(net_obj, 'GET', attach_path)
    #     logit('attch:response: %s' %have['attach'])

        # Check for deployed state ## HOW?

    # NET FACTS
    # { "fabric": "cvh3", "networkName": "c1", "displayName": "c1", "networkId": 31120,
    # "networkTemplate": "Default_Network_Universal", "networkExtensionTemplate": "Default_Network_Extension_Universal",
    # "networkTemplateConfig": "{\"suppressArp\":\"false\",\"secondaryGW2\":\"\",\"secondaryGW1\":\"\",\"loopbackId\":\"\",\"vlanId\":\"2308\",\"gatewayIpAddress\":\"\",\"enableL3OnBorder\":\"false\",\"networkName\":\"c1\",\"vlanName\":\"\",\"enableIR\":\"false\",\"mtu\":\"\",\"rtBothAuto\":\"false\",\"isLayer2Only\":\"false\",\"intfDescription\":\"\",\"segmentId\":\"31120\",\"mcastGroup\":\"239.1.1.3\",\"gatewayIpV6Address\":\"\",\"trmEnabled\":\"false\",\"dhcpServerAddr2\":\"\",\"dhcpServerAddr1\":\"\",\"tag\":\"12345\",\"nveId\":\"1\",\"vrfDhcp\":\"\",\"vrfName\":\"MyVRF_50000\"}",
    # "vrf": "MyVRF_50000", "serviceNetworkTemplate": null, "source": null }

    # ATTACH FACTS
    # [{"networkName":"c1","lanAttachList":[{"networkName":"c1","switchName":"dt-n9k5-1","switchRole":"leaf","fabricName":"cvh3","lanAttachState":"PENDING","isLanAttached":true,"portNames":"Ethernet1/5","switchSerialNo":"SAL1821T9EF","switchDbId":336700,"ipAddress":"10.122.197.192","networkId":31120,"vlanId":2308}]}]

def normalize_inputs(net_obj):
    """Normalize the 'have' and 'want' data, then create a diff"""

    have = net_obj.get('have', {})
    logit('have: %s' %have)
    cfg = json.loads(have.get('networkTemplateConfig', {}))
    have_norm = {
       'fabric': have['fabric'],
       'template': have['networkTemplate'],
       'template_ext': have['networkExtensionTemplate'],
       'net_name': cfg.get('networkName'),
       'net_id': cfg.get('networkId'),
       'vlan_id': cfg.get('vlanId'),
       'vrf': cfg.get('vrf'),
       'gw_ip': cfg.get('gatewayIpAddress'),
    }
    # DCNM sets empty integer fields to ''; set them to None to match 'want' params.
    for k in ['net_id', 'vlan_id']:
        have_norm[k] = int(have_norm[k]) if have_norm[k] else None
    logit('normal: %s' %have_norm)

    want = dict((k, net_obj['params'].get(k)) for k in have_norm.keys())
    logit('want: %s' %want)

    diff = dict_diff(want, have_norm)
    logit('diff: %s' %diff)
    net_obj['have'] = have_norm
    net_obj['diff'] = diff
    # import epdb; epdb.serve()

def deleted(net_obj):
    # TODO: un-deploy / un-attach ??
    fabric = net_obj['params']['fabric']
    net_name = net_obj['params']['net_name']
    path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, net_name)
    resp = send(net_obj, 'DELETE', path)
    logit('delete:response: %s' %resp)
    return resp

def merged(net_obj):
    # TODO: add attach/deploy calls to end of method
    # TODO: if vlan_id is empty then DCNM will automatically pick the next vlan from the fabric;
    #       however,net_id/VNI can also be automatically populated, in which case use
    #       POST /rest/managed-pool/fabrics/{{fabric}}/segments/ids
    #       to get the next avail VNI e.g. get_vni()

    # TODO: ADD DIFF LOGIC TO DETERMINE IF MERGED SHOULD BE SKIPPED
    fabric = net_obj['params']['fabric']
    net_name = net_obj['params']['net_name']
    diff = ['foo']
    if diff:
        payload = merged_payload(net_obj)
        # TODO: CONSIDER MOVING JSONIFY'S INTO PAYLOAD MAKER
        # jsonify the TemplateConfig by itself first, then do entire payload
        payload['networkTemplateConfig'] = json.dumps(payload['networkTemplateConfig'])
        payload = json.dumps(payload)

        # TODO: Use 'PUT' for updates, 'POST' for creates  *****
        path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, net_name)
        resp = send(net_obj, 'POST', path, payload)
        logit('create:response: %s' %resp)

    # import epdb;epdb.serve()

    # TODO: ADD LOGIC TO DETERMINE WHEN ATTACH/DEPLOY ACTIONS SHOULD BE SKIPPED (idempotence)
    # CASE: net is idempotent but attach list is not, or not all deployed
    # attach()
    # deploy()
    #
    return resp

def merged_payload(net_obj):
    """Create payload dict."""
    params = net_obj['params']
    net_name = params['net_name']

    # Create the payload top-level arguments
    top_level = {
        'fabric': 'fabric',
        'template': 'networkTemplate',
        'template_ext': 'networkExtensionTemplate',
        'net_name': 'networkName',
        # displayName: same as networkName
        'net_id': 'networkId',   # VNI
        'vrf': 'vrf',
    }
    payload = dict((top_level[k], params[k]) for k in top_level.keys() if params.get(k) is not None)

    # Build templateConfig arguments.
    template_cfg = {
        # some reqd/cfg keys are duplicated with top-level args
        'net_name': 'networkName',
        'net_id': 'networkId',
        'vlan_id': 'vlanId',
        'vrf': 'vrf',
        'gw_ip': 'gatewayIpAddress'
    }
    template = dict((template_cfg[k], params[k]) for k in template_cfg.keys() if params.get(k) is not None)
    payload['networkTemplateConfig'] = template

    logit('buildPayload: %s' %payload)
    return payload

def main():
    """ main entry point for module execution
    """
    element_spec = dict(
        fabric=dict(required=True, type='str'),
        net_name=dict(required=True, type='str'),
        net_id=dict(type=int),
        vrf=dict(type='str'),
        #
        gw_ip=dict(type='str'),
        vlan_id=dict(type=int),
        #
        attach=dict(type=list, default=[]),
        # deploy=dict(type='str', default=True),
        state=dict(type='str', default='merged'),
        #
        template=dict(default='Default_Network_Universal'),
        template_ext=dict(default='Default_Network_Extension_Universal'),
    )

    module = AnsibleModule(argument_spec=element_spec,
                           # required_one_of=required_one_of,
                           # mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)
    net_obj = {
        'params': module.params,
        'conn': Connection(module._socket_path),
    }
    get_facts(net_obj)
    have = net_obj['have']

    result = dict(changed=False, response=dict())
    state = module.params['state']
    normalize_inputs(net_obj)
    if state == 'query':
        resp = have
    elif state == 'deleted':
        resp = deleted(net_obj)
    elif state == 'merged':
        if have:  ## TEST CODE ONLY - REMOVES NET FOR MERGED TESTING
            deleted(net_obj)  ## REMOVEME
        resp = merged(net_obj)

    # import epdb;epdb.serve()
    result['response'] = resp
    module.exit_json(**result)


if __name__ == '__main__':
    main()

# TBD:
# NET_ATTRS = {
#     "networkTemplate": "network_template",
#     "networkExtensionTemplate": "network_extension_template",
#     # "networkTemplateConfig": "network_template_config",
#     "networkId": "network_id",
# }
