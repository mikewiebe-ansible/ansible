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
        of.write("\n---- _network: %s\n" % (msg))

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
        logit('#### send: exception: %s' %resp)
        import epdb;epdb.serve()
        raise Exception('foo')

def get_facts(net_obj):
    """Check for existing network, attached state, and deployed state.
    fabrics/{}/networks/{} is a per-net lookup.
    fabrics/{}/networks/{}/attachments is a per-net lookup that gets a list of all attached switches.
    """
    conn = net_obj['conn']
    params = net_obj['params']
    net_name = params['net_name']

    # Get network dict
    path = '/rest/top-down/fabrics/{}/networks/{}'.format(params['fabric'], net_name)
    have_net = send(net_obj, 'GET', path)

    have_attach = []
    if have_net:
        # Get attach list for this net
        path += '/attachments'
        have_attach = send(net_obj, 'GET', path)

    net_obj['have_net'] = have_net
    net_obj['have_attach'] = have_attach

    logit('get_facts:net: %s' %have_net)
    logit('get_facts:att: %s' %have_attach)

def _diff_net(net_obj):
    """Normalize the 'have' and 'want' network data, then create a diff.
    Results will be in 'have_net', 'want_net', 'diff_net'.
    """
    raw = net_obj.get('have_net', {})
    logit('raw: %s' %raw)
    cfg = json.loads(raw.get('networkTemplateConfig', {}))
    have = {
       'fabric': raw['fabric'],
       'template': raw['networkTemplate'],
       'template_ext': raw['networkExtensionTemplate'],
       'net_name': cfg.get('networkName'),
       'net_id': cfg.get('networkId'),
       'vlan_id': cfg.get('vlanId'),
       'vrf': cfg.get('vrf'),
       'gw_ip': cfg.get('gatewayIpAddress'),
    }
    # DCNM sets empty integer fields to ''; set them to None to match 'want' params.
    # TODO: Need better "None" compare; should I just call remove_empties?
    for k in ['net_id', 'vlan_id']:
        have[k] = int(have[k]) if have[k] else None

    # 'want' data
    want = dict((k, net_obj['params'].get(k)) for k in have.keys())

    net_obj['diff_net'] = diff = dict_diff(want, have)
    net_obj['want_net'] = want
    net_obj['have_net'] = have
    logit('have_net: %s' %have)
    logit('want_net: %s' %want)
    logit('diff_net: %s' %diff)
    # import epdb; epdb.serve()

def _diff_attach(net_obj):
    """Normalize the 'have' and 'want' network attach lists, then create a diff.
    Results will be in 'have_attach', 'want_attach', 'diff_attach'.
    """
    raw = net_obj.get('have_attach', [])
    logit('raw: %s' %raw)
    have = []
    for sw in raw:
        sample_raw = [
            {'networkName': 'c1', 'switchName': 'dt-n9k5-1', 'switchRole': 'leaf',
             'fabricName': 'cvh4', 'lanAttachState': 'DEPLOYED', 'isLanAttached': True,
             'portNames': 'Ethernet1/13,Ethernet1/12', 'switchSerialNo': 'SAL1821T9EF',
             'switchDbId': 389920, 'ipAddress': '10.122.197.192', 'networkId': 30001,
             'vlanId': 2301}]
        ports = sw.get('portNames', '')
        ports = ports.split(',') if ports else []

        deploy = True if (sw.get('lanAttachState') in ['DEPLOYED', 'PENDING']) else False
        have.append({
            'name': sw.get('switchName'),   ### HOW BEST TO INDEX THESE? name? ip? both?
            'ip': sw.get('ipAddress'),
            'ports': ports,
            'deploy': deploy
        })

    want_attach = []
    diff_attach = []
    for sw in net_obj['params'].get('attach', []):
        ip = sw.get('ip')
        want = {
            'name': sw.get('name'),
            'ip': ip,
            'ports': sw.get('ports', []),
            'deploy': sw.get('deploy')
        }
        hv = [i for i in have if i['ip'] == ip]
        if hv:
            hv = hv[0]
            # {'name': 'dt-n9k5-1', 'ip': '10.122.197.192', 'ports': ['Ethernet1/13', 'Ethernet1/12'], 'deploy': 'DEPLOYED'}
            diff = dict_diff(want, hv)
            diff['ports'] = list(set(want['ports']) - set(hv['ports']))
            diff_attach.append(diff)

            logit('diff: %s' %diff)


    net_obj['have_attach'] = have
    net_obj['want_attach'] = want_attach
    net_obj['diff_attach'] = diff_attach

    logit('have_attach: %s' %have)
    logit('want_attach: %s' %want_attach)
    logit('diff_attach: %s' %diff_attach)
    import epdb; epdb.serve()


def deleted(net_obj):
    # TODO: check attach state; also need to deploy change to devices
    fabric = net_obj['params']['fabric']
    net_name = net_obj['params']['net_name']
    path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, net_name)
    resp = send(net_obj, 'DELETE', path)
    logit('delete:response: %s' %resp)
    return resp

def merged(net_obj):
    # TODO: if vlan_id is empty then DCNM will automatically pick the next vlan from the fabric;
    #       however,net_id/VNI can also be automatically populated, in which case use
    #       POST /rest/managed-pool/fabrics/{{fabric}}/segments/ids
    #       to get the next avail VNI e.g. get_vni()

    fabric = net_obj['params']['fabric']
    net_name = net_obj['params']['net_name']

    # CREATE/UPDATE the network object
    if net_obj['diff_net']:
        method = 'PUT' if net_obj['have_net'] else 'POST'
        path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, net_name)
        payload = net_payload_merged(net_obj)

        resp = send(net_obj, method, path, payload)
        logit('create:response: %s' %resp)
    else:
        logit('merged: no diff')

    import epdb;epdb.serve()

    # ATTACH the network
    if net_obj['diff_attach']:
        pass

    # DEPLOY the network on devices
    if net_obj['diff_deploy']:
        pass

    # CASE: net is idempotent but attach list is not, or not all deployed
    #
    return resp

def net_payload_merged(net_obj):
    """Create payload for network PUT/POST"""
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
    # templateConfig needs to be in json syntax before overall payload
    payload['networkTemplateConfig'] = json.dumps(template)
    payload = json.dumps(payload)

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
    _diff_net(net_obj)
    _diff_attach(net_obj)
    # TODO: Add checkmode support
    result = dict(changed=False, response=dict())
    state = module.params['state']
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

    # NET FACTS
    # { "fabric": "cvh3", "networkName": "c1", "displayName": "c1", "networkId": 31120,
    # "networkTemplate": "Default_Network_Universal", "networkExtensionTemplate": "Default_Network_Extension_Universal",
    # "networkTemplateConfig": "{\"suppressArp\":\"false\",\"secondaryGW2\":\"\",\"secondaryGW1\":\"\",\"loopbackId\":\"\",\"vlanId\":\"2308\",\"gatewayIpAddress\":\"\",\"enableL3OnBorder\":\"false\",\"networkName\":\"c1\",\"vlanName\":\"\",\"enableIR\":\"false\",\"mtu\":\"\",\"rtBothAuto\":\"false\",\"isLayer2Only\":\"false\",\"intfDescription\":\"\",\"segmentId\":\"31120\",\"mcastGroup\":\"239.1.1.3\",\"gatewayIpV6Address\":\"\",\"trmEnabled\":\"false\",\"dhcpServerAddr2\":\"\",\"dhcpServerAddr1\":\"\",\"tag\":\"12345\",\"nveId\":\"1\",\"vrfDhcp\":\"\",\"vrfName\":\"MyVRF_50000\"}",
    # "vrf": "MyVRF_50000", "serviceNetworkTemplate": null, "source": null }

    # ATTACH FACTS
    # [{"networkName":"c1","lanAttachList":[{"networkName":"c1","switchName":"dt-n9k5-1","switchRole":"leaf","fabricName":"cvh3","lanAttachState":"PENDING","isLanAttached":true,"portNames":"Ethernet1/5","switchSerialNo":"SAL1821T9EF","switchDbId":336700,"ipAddress":"10.122.197.192","networkId":31120,"vlanId":2308}]}]
