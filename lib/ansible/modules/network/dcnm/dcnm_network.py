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
#                                         *** WIP ***
    - name: foo
      dcnm_network:
        fabric: cvh4
        state: merged
        config:
          - net_name: c1
            net_id: 31120                 # VNI, optional: can autogenerate
            vrf: MyVRF_50000
            # template: Default_Network_Universal                 # optional
            # template_ext: Default_Network_Extension_Universal   # optional
            # gw_ip: '201.1.1.1/24'
            vlan_id: 2305               # optional: can be empty
            attach:
              - ip: 10.122.197.192
                name: dt-n9k5-1
                ports: [Ethernet1/1, Ethernet1/2]
                # deploy: false
          - net_name: c2
            net_id: 31122                 # VNI, optional: can autogenerate
            vrf: MyVRF_50000
'''

import datetime
def logit(msg):
    with open('/tmp/logit.txt', 'a') as of:
        of.write("\n---- _network: %s\n" % (msg))

def send(facts, method, path, payload=None):
    logit('send: path: %s' %path)
    if payload:
        resp = facts['conn'].send_request(method, path, payload)
    else:
        resp = facts['conn'].send_request(method, path)
    if isinstance(resp, dict):
        return resp
    elif isinstance(resp, list):
        if resp[0].get('ERROR') == 'Bad Request':
            # object does not exist
            return {}
        else:
            return resp
    else:
        logit('#### send: exception: %s' %resp)
        import epdb;epdb.serve()
        raise Exception('foo')

def validate_playbook(facts):
    """ Validate playbook entries, set defaults, normalize the 'want' data. """

    for param in facts['config']:
        # config:
        # - net_name: c1
        #   net_id: 31120
        #   vrf: MyVRF_50000
        #   attach: <list>
        name = param.get('net_name')
        net = {
            #### TBD: ADD SOME VALIDATION HERE :-)
            'fabric': facts['fabric'],
            'gw_ip': param.get('gw_ip'),
            'net_id': param.get('net_id'),  ## NEED?
            'vlan_id': param.get('vlan_id'), ## to_int
            'vrf': param.get('vrf'),
            'template': param.get('template', 'Default_Network_Universal'),
            'template_ext': param.get('template_ext', 'Default_Network_Extension_Universal'),
        }
        facts['want'][name] = {}
        facts['want'][name]['net'] = net

        att = {}
        for sw in param.get('attach', []):
            # TBD: switches are indexed in facts db by IP
            #   attach:
            #     - name: dt-n9k5-1
            #       ip: 10.122.197.192
            #       ports: [Ethernet1/1, Ethernet1/2]
            ip = sw.get('ip')
            # TBD: if not valid(ip) raise
            att[ip] = {
                #### TBD: ADD SOME VALIDATION HERE :-)
                'name': sw.get('name'),
                'ports': sw.get('ports', []),
                'deploy': sw.get('deploy', True),
            }
        facts['want'][name]['att'] = att
        logit('validate_playbook:want: %s' %facts['want'][name])
    # import epdb;epdb.serve()

def populate_facts(facts):
    """Check for existing networks and attached states.
    ** facts db structure: facts[have|want][netwrk1,netwrk2,...][net|att]
    """
    # GET all networks
    path = '/rest/top-down/fabrics/{}/networks'.format(facts['fabric'])
    all_net_raw = send(facts, 'GET', path)

    all_att_raw = []
    if all_net_raw:
        # GET all attach states for networks found above (there may be none)
        all_net_names = ','.join([ k['networkName'] for k in all_net_raw ])
        path += '/attachments?network-names={}'.format(all_net_names)
        all_att_raw = send(facts, 'GET', path)
        logit('all_att_raw: %s' %all_att_raw)

    have = facts['have']
    # Update 'have' facts dict with current net/attach/deploy states
    for net_raw in all_net_raw:
        name = net_raw['networkName']
        have[name] = {}
        have[name]['net'] = render_net(net_raw)
        # Get a list of switches that this specific net is attached to.
        for k in all_att_raw:
            if k.get('networkName') == name:
                att_raw = k.get('lanAttachList', [])
                break
        else:
            att_raw = []
        have[name]['att'] = render_att(att_raw)

    # TBD: NEED THIS? it's the net deploy state, not the attach deploy state
    # have[name]['dep'] = net_raw.get('networkStatus')
    # import epdb;epdb.serve()

def render_net(net_raw):
    # Select & normalize 'have' network data.
    # net_raw is a json-syntax dict
    logit('net raw: %s' %net_raw)
    cfg = json.loads(net_raw.get('networkTemplateConfig', {}))
    net = {
       'fabric': net_raw['fabric'],
       'template': net_raw['networkTemplate'],
       'template_ext': net_raw['networkExtensionTemplate'],
       'net_name': cfg.get('networkName'),
       'net_id': cfg.get('networkId'),
       'vlan_id': cfg.get('vlanId'),
       'vrf': cfg.get('vrf'),
       'gw_ip': cfg.get('gatewayIpAddress'),
    }
    for k in ['net_id', 'vlan_id']:
        net[k] = int(net[k]) if net[k] else None # Q: Is None safe here?

    logit('render_net:%s: %s' %(net['net_name'], net))
    return(net)

def render_att(att_raw):
    # Select & normalize 'have' attach data.
    # att_raw is a list of switch dicts.
    # Return an 'att' dict which contains switch dicts
    logit('att raw: %s' %att_raw)
    att = {}
    for sw in att_raw:
        ports = sw.get('portNames', '')
        ports = ports.split(',') if ports else []
        deploy = True if (sw.get('lanAttachState') in ['DEPLOYED', 'PENDING']) else False
        ip = sw.get('ipAddress')   # TBD: guaranteed to always have ip??
        att[ip] = {
            'name': sw.get('switchName'),
            'ports': ports,
            'deploy': deploy,
        }
        logit('render_att:%s: %s' %(ip, att))
    return att
    # sample_att_raw = [    #### REMOVEME
    #     {'networkName': 'c1', 'switchName': 'dt-n9k5-1', 'switchRole': 'leaf',
    #      'fabricName': 'cvh4', 'lanAttachState': 'DEPLOYED', 'isLanAttached': True,
    #      'portNames': 'Ethernet1/13,Ethernet1/12', 'switchSerialNo': 'SAL1821T9EF',
    #      'switchDbId': 389920, 'ipAddress': '10.122.197.192', 'networkId': 30001,
    #      'vlanId': 2301}]

def get_diffs(facts):
    """ Create diffs for each network in 'want'
    """
    ##### WIP: ...

    for param in facts['config']:
        for data_type in ['net', 'att']:
            name = param['net_name']
            have = facts['have'].get(name, {}).get(data_type, {})
            want = facts['want'].get(name, {}).get(data_type, {})
            diff = dict_diff(have, want)

            # ...clean up diff here...?
            facts['diff'][name] = { data_type: diff }
            # logit('get_diffs: %s:%s: %s' %(name, data_type, diff))
            logit('get_diffs: %s: %s\nhave: %s\nwant: %s\ndiff: %s' %(name, data_type, have, want, diff))

    # import epdb;epdb.serve()


def deleted(facts):
    # TODO: check attach state; also need to deploy change to devices
    fabric = facts['params']['fabric']
    net_name = facts['params']['net_name']
    path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, net_name)
    resp = send(facts, 'DELETE', path)
    logit('delete:response: %s' %resp)
    return resp

# def merged(facts):
#     # TODO: if vlan_id is empty then DCNM will automatically pick the next vlan from the fabric;
#     #       however,net_id/VNI can also be automatically populated, in which case use
#     #       POST /rest/managed-pool/fabrics/{{fabric}}/segments/ids
#     #       to get the next avail VNI e.g. get_vni()
#
#     fabric = facts['params']['fabric']
#     net_name = facts['params']['net_name']
#
#     # CREATE/UPDATE the network object
#     if facts['diff_net']:
#         method = 'PUT' if facts['have_net'] else 'POST'
#         path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, net_name)
#         payload = net_payload_merged(facts)
#
#         resp = send(facts, method, path, payload)
#         logit('create:response: %s' %resp)
#     else:
#         logit('merged: no diff')
#
#     import epdb;epdb.serve()
#
#     # ATTACH the network
#     if facts['diff_attach']:
#         pass
#
#     # DEPLOY the network on devices
#     if facts['diff_deploy']:
#         pass
#
#     # CASE: net is idempotent but attach list is not, or not all deployed
#     #
#     return resp
#
# def net_payload_merged(facts):
#     """Create payload for network PUT/POST"""
#     params = facts['params']
#     net_name = params['net_name']
#
#     # Create the payload top-level arguments
#     top_level = {
#         'fabric': 'fabric',
#         'template': 'networkTemplate',
#         'template_ext': 'networkExtensionTemplate',
#         'net_name': 'networkName',
#         # displayName: same as networkName
#         'net_id': 'networkId',   # VNI
#         'vrf': 'vrf',
#     }
#     payload = dict((top_level[k], params[k]) for k in top_level.keys() if params.get(k) is not None)
#
#     # Build templateConfig arguments.
#     template_cfg = {
#         # some reqd/cfg keys are duplicated with top-level args
#         'net_name': 'networkName',
#         'net_id': 'networkId',
#         'vlan_id': 'vlanId',
#         'vrf': 'vrf',
#         'gw_ip': 'gatewayIpAddress'
#     }
#     template = dict((template_cfg[k], params[k]) for k in template_cfg.keys() if params.get(k) is not None)
#     # templateConfig needs to be in json syntax before overall payload
#     payload['networkTemplateConfig'] = json.dumps(template)
#     payload = json.dumps(payload)
#
#     logit('buildPayload: %s' %payload)
#     return payload


def main():
    """ main entry point for module execution
    """
    element_spec = dict(
        fabric=dict(required=True, type='str'),
        config=dict(required=True, type=list),
        state=dict(type='str', default='merged'),
    )
    module = AnsibleModule(argument_spec=element_spec,
                           # required_one_of=required_one_of,
                           # mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)
    facts = {
        'conn': Connection(module._socket_path),
        'fabric': module.params['fabric'],
        'config': module.params['config'],
        'have': {}, # Normalized data below...
            # { network1: {
            #     net:{ vrf: x, vlan: fred },
            #     att:{ 192.2.2.2: { ports: [Eth1, Eth2], deploy: True}
            #           192.3.3.3: { ports: [Eth1], deploy: False}
            #         } },
            # { network2: ...
        'want': {},
        'diff': {},
    }
    validate_playbook(facts)
    populate_facts(facts)
    get_diffs(facts)

    import epdb;epdb.serve()
    # TODO: Add checkmode support

    # WIP BELOW THIS POINT
    result = dict(changed=False, response=dict())
    state = module.params['state']
    if state == 'query':
        resp = have
    elif state == 'deleted':
        resp = deleted(facts)
    elif state == 'merged':
        if have:  ## TEST CODE ONLY - REMOVES NET FOR MERGED TESTING
            deleted(facts)  ## REMOVEME

        resp = merged(facts) ### REFACTOR TO USE BULK CREATE/ATTACH

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

    # NET FACTS
    # { "fabric": "cvh3", "networkName": "c1", "displayName": "c1", "networkId": 31120,
    # "networkTemplate": "Default_Network_Universal", "networkExtensionTemplate": "Default_Network_Extension_Universal",
    # "networkTemplateConfig": "{\"suppressArp\":\"false\",\"secondaryGW2\":\"\",\"secondaryGW1\":\"\",\"loopbackId\":\"\",\"vlanId\":\"2308\",\"gatewayIpAddress\":\"\",\"enableL3OnBorder\":\"false\",\"networkName\":\"c1\",\"vlanName\":\"\",\"enableIR\":\"false\",\"mtu\":\"\",\"rtBothAuto\":\"false\",\"isLayer2Only\":\"false\",\"intfDescription\":\"\",\"segmentId\":\"31120\",\"mcastGroup\":\"239.1.1.3\",\"gatewayIpV6Address\":\"\",\"trmEnabled\":\"false\",\"dhcpServerAddr2\":\"\",\"dhcpServerAddr1\":\"\",\"tag\":\"12345\",\"nveId\":\"1\",\"vrfDhcp\":\"\",\"vrfName\":\"MyVRF_50000\"}",
    # "vrf": "MyVRF_50000", "serviceNetworkTemplate": null, "source": null }

    # ATTACH FACTS
    # [{"networkName":"c1","lanAttachList":[{"networkName":"c1","switchName":"dt-n9k5-1","switchRole":"leaf","fabricName":"cvh3","lanAttachState":"PENDING","isLanAttached":true,"portNames":"Ethernet1/5","switchSerialNo":"SAL1821T9EF","switchDbId":336700,"ipAddress":"10.122.197.192","networkId":31120,"vlanId":2308}]}]
