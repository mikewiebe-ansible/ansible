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
import socket
from textwrap import dedent

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common import validation
from ansible.module_utils.connection import Connection
from ansible.module_utils.network.common.utils import dict_diff, remove_empties

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
    # for code: 200 we don't get a response body. Can we get the code at least?
    # logit('### send:resp: %s ' %resp)
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

class DcnmNetwork:

    def __init__(self, module, conn):
        self.conn = conn
        self.state = module.params['state']
        self.fabric = module.params['fabric']
        self.config = module.params['config']
        self.sn = {},  # serialNumber lookup data
        self.have = {}, # Normalized data from device, e.g...
            # { network1: {
            #     net:{ vrf: x, vlan: fred },
            #     att:{ 192.2.2.2: { ports: [Eth1, Eth2], deploy: True}
            #           192.3.3.3: { ports: [Eth1], deploy: False}
            #         } },
            # { network2: ...
        self.want = {}
        self.diff = {}

        self.normalize_inputs()

    def normalize_inputs(self):
        net_spec = dict(
            net_name=dict(required=True, type='str'),
            net_id=dict(required=True, type='int'),
            vrf=dict(required=True, type='str'),
            #
            attach=dict(type='list'),
            deploy_net=dict(type='bool'),
            gw_ip=dict(type='ipv4'),
            vlan_id=dict(type='int'),
            template=dict(type='str', default='Default_Network_Universal'),
            template_ext=dict(type='str', default='Default_Network_Extension_Universal')
        )
        att_spec = dict(
            ip=dict(required=True, type='ipv4'),
            switch_name=dict(type='str'),
            ports=dict(required=True, type='list'),
            deploy=dict(type='bool', default=True)
        )
        want = self.want
        valid_net_list = self.validate_list_of_dicts(self.config, net_spec)
        # Create a dict of net data
        for i in valid_net_list:
            net_name = i['net_name']
            want[net_name] = {}
            want[net_name]['net'] = {
                'fabric': self.fabric,
                'net_id': i['net_id'],
                'gw_ip': i['gw_ip'],
                'vlan_id': i['vlan_id'],
                'vrf': i['vrf'],
                'template': i['template'],
                'template_ext': i['template_ext']
            }
            # Create a dict of att data
            if i['attach']:
                want[net_name]['att'] = {}
                valid_att_list = self.validate_list_of_dicts(i['attach'], att_spec)
                for sw in valid_att_list:
                    ip = sw['ip']
                    want[net_name]['att'][ip] = {
                        'switch_name': sw['switch_name'],
                        'ports': sw['ports'],
                        'deploy': sw['deploy'],
                    }

        logit('normalize_inputs: want: %s' %self.want)

    def validate_list_of_dicts(self, param_list, spec): # Move this into common ****
        """ Validate playbook entries and normalize the playbook values. """
        v = validation
        normalized = []
        invalid_params = []
        for list_entry in param_list:
            # TBD: can net_id be blank? i.e. allow dcnm to generate net_id; or if playbook
            # doesn't list it can I assume it exists and get it from the 'have' data?
            valid_params_dict = {}
            for param in spec:
                item = list_entry.get(param)
                if item is None:
                    if spec[param].get('required'):
                        invalid_params.append('{} : Required parameter not found'.format(item))
                    else:
                        item = spec[param].get('default')
                else:
                    type = spec[param].get('type')
                    if type == 'str':
                        item = v.check_type_str(item)
                    elif type == 'int':
                        item = v.check_type_int(item)
                    elif type == 'bool':
                        item = v.check_type_bool(item)
                    elif type == 'list':
                        item = v.check_type_list(item)
                    elif type == 'dict':
                        item = v.check_type_dict(item)
                    elif type == 'ipv4':
                        address = item.split('/')[0]
                        try:
                            socket.inet_aton(address)
                        except socket.error:
                            invalid_params.append('{} : Invalid IPv4 address syntax'.format(item))
                        if address.count('.') != 3:
                            invalid_params.append('{} : Invalid IPv4 address syntax'.format(item))
                valid_params_dict[param] = item
            normalized.append(valid_params_dict)

        if invalid_params:
            msg = 'Invalid parameters in playbook: {}'.format('\n'.join(invalid_params))
            raise Exception(msg)

        return(normalized)

    def populate_have(self):
        """Check for existing networks and attached states.
        ** facts db structure: facts[have|want][netwrk1,netwrk2,...][net|att]
        """
        # GET all networks
        path = '/rest/top-down/fabrics/{}/networks'.format(self.fabric)


        #### START HERE ####
        #### START HERE ####
        #### START HERE ####
        #### START HERE ####
        #### convert send to use common code Mike added
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

        populate_sn(facts)

def populate_sn(facts):
    # Lookup serialNumbers for each device in each attachList that needs
    # to be updated. The api requires the S/N but we don't want to
    # require S/N in the playbook. Of course this assumes the device is
    # already present in DCNM.
    # TBD: is there a better way to handle this?
    sn = facts['sn']
    path = '/rest/control/fabrics/{}/inventory'.format(facts['fabric'])
    resp = send(facts, 'GET', path)
    # Todo: need to check for safe/usable values in resp
    # Valid resp data should contain a list of dicts
    for i in resp:
        sn[i['ipAddress']] = i['serialNumber']
    logit('sn: %s' %sn)

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
            'switch_name': sw.get('switchName'),
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
    # Due to the way the api's work, we can't really make incremental changes
    # to the objects since the payload requires a number of mandatory items.
    # That makes this diff data somewhat unnecessary since we really just
    # need to know whether anything has changed and then send the entire
    # 'want' payload regardless. May need to revisit this...
    for network in facts['config']:
        for data_type in ['net', 'att']:
            name = network['net_name']
            deploy = network['deploy']

            have = facts['have'].get(name, {}).get(data_type, {})
            want = facts['want'].get(name, {}).get(data_type, {})

            diff = dict_diff(have, want)

            # ...clean up diff here...?
            facts['diff'][name] = { data_type: diff }
            # logit('get_diffs: %s:%s: %s' %(name, data_type, diff))
            logit('get_diffs: %s: %s\nhave: %s\nwant: %s\ndiff: %s' %(name, data_type, have, want, diff))

    # import epdb;epdb.serve()

def query(facts):
    """Create a yaml-formatted string of current 'have' data.
    """
    # ** TBD: This report includes all networks in the fabric. **
    # **      Should this only look at the networks found in the playbook?? **
    # have[name][net]
    # have[name][att][ip]
    have = facts['have']
    net_keys = ['net_id', 'vrf', 'vlan_id', 'gw_ip']
    att_keys = ['name', 'ports', 'deploy']

    # Consider: do not display when arg set to default?
    rpt = dedent('''\
    tasks:
      dcnm_network:
        fabric: {}
        config:''').format(facts['fabric'])
    for name in have.keys():
        net = have[name].get('net')
        rpt += '\n    - net_name: {}'.format(name)
        for k in net_keys:
            if net.get(k) is not None:  ## TBD: assumes always exists. safe?
                rpt += '\n      {}: {}'.format(k, net[k])
        att = have[name].get('att')
        if att:
            rpt += '\n      attach:'
            for ip in att.keys():
                rpt += '\n        - ip: {}'.format(ip)
                for k in att_keys:
                    if att[ip].get(k) is not None:
                        rpt += '\n          {}: {}'.format(k, att[ip][k])
    logit('rpt: %s' %rpt)
    # import epdb;epdb.serve()
    return rpt

def deleted(facts):
    # Todo: global purge when config null.
    # TODO: check attach state; also need to deploy change to devices
    fabric = facts['fabric']
    ### FIXME: needs to handle multiple nets
    for i in facts['config']:
        path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, i[net_name])
        resp = send(facts, 'DELETE', path)
        logit('delete:response: %s' %resp)
    return resp ## list of resp's?

def merged(facts):
    """ Check for non-idempotent networks, create payloads, update DCNM.
    """
    # Use bulk-create for all new networks, use PUT networks for updates.
    # TBD: if vlan_id is empty then DCNM will automatically pick the next vlan
    #      from the fabric; however,net_id/VNI can also be automatically
    #      populated, in which case use POST /rest/managed-pool/fabrics/{{fabric}}/segments/ids
    #       to get the next avail VNI e.g. get_vni()
    # TBD: check_mode
    # TBD: log separate results for each network, each attach, ...?
    # TBD: create a collective 'resp', carry in facts?
    fabric = facts['fabric']
    have = facts['have']
    want = facts['want']
    diff = facts['diff']

    # List of new net objects to bulk-create in DCNM
    new_nets = [ i for i in diff.keys() if not have.get(i) ]
    if new_nets:
        method = 'POST'
        payload = []
        for name in new_nets:
            payload.append(net_payload(facts, name))
        payload = json.dumps(payload)
        logit('bulk payload: %s' %payload)
        path = '/rest/top-down/bulk-create/networks'
        resp = send(facts, method, path, payload)
        # TBD: log results for each network in the bulk create
        logit ('resp:bulk: %s' %resp)

    # List of existing net objects to update in DCNM
    upd_nets = [ i for i in diff.keys() if have.get(i) ]
    for name in upd_nets:
        # There is no bulk-update; use a separate payload for each net
        payload = net_payload(facts, name)
        payload = json.dumps(payload)
        path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, name)
        resp = send(facts, 'PUT', path, payload)

    # List of networks to create or update attachments
    upd_atts = [ i for i in diff.keys() if diff[i].get('att') ]
    for name in upd_atts:
        # NOTES on deploy states:
        #  PENDING: attached, not deployed
        #  OUT_OF_SYNC: deploy failed
        #  PROGRESS: transient state before DEPLOYED
        #  DEPLOYED: success
        # TBD: For now we'll update attachments one at a time but revisit this
        # and see if updating all diff attachments in one api call is feasible.
        # TBD: For merge we don't care if there are extra ports or attachments
        # on the device, but if so the diff might cause a false non-idempotence.
        # TBD: handle detachPorts logic in diff method. If detachPorts populated
        # and port not in 'switchports' then idempotent; also need a per-port
        # check when diff the 'port' arg, since the order can be different and
        # incomplete; e.g. have:1,2 want:attach 1,3 detach 2,
        #  diff:att 3 det 2. post-have: 1,3 now idempotent.
        payload = {
            "networkName": name,
            "lanAttachList": att_payload(facts, name)
        }
        payload = json.dumps([payload]) ## TBD: Send all updates at once?
        # logit('upd_atts:json: %s' %payload)
        path = '/rest/top-down/fabrics/{}/networks/attachments'.format(fabric)
        resp = send(facts, 'POST', path, payload)
        ## TBD: Response should be as below; need to parse EACH S/N for success.
        #  {'c1-[SAL1821T9EF/dt-n9k5-1]': 'SUCCESS'}
        logit('upd_atts:resp: %s' %resp)
        # import epdb;epdb.serve()

    if diff:
        # TBD: all: '/rest/top-down/fabrics/networks/deployments', payload='n1,n2'
        # per: '/rest/top-down/fabrics/{}/networks/{}/deploy'
        for name in diff.keys():
            if not diff[name].get('deploy'):
                continue
            path = '/rest/top-down/fabrics/{}/networks/{}/deploy'.format(fabric, name)
            resp = send(facts, 'POST', path)
            ## TBD: Response should be as below; need to parse EACH S/N for success.
            #  {'c1-[SAL1821T9EF/dt-n9k5-1]': 'SUCCESS'}
            logit('upd_atts:resp: %s' %resp)

    # List of networks with changes to deploy

    import epdb;epdb.serve()
    return resp

def net_payload(facts, name):
    """Create payload for network PUT/POST"""
    net = facts['want'][name]['net']
    payload = { 'fabric': facts['fabric'] }
    xtable = {
        'template': 'networkTemplate',
        'template_ext': 'networkExtensionTemplate',
        'net_name': 'networkName',
        # displayName: same as networkName
        'net_id': 'networkId',   # VNI
        'vrf': 'vrf',
    }
    payload.update(dict((xtable[k], net[k]) for k in xtable.keys() if net.get(k) is not None))
    # logit('net_payload:top: %s' %payload)

    # Build templateConfig arguments.
    t_cfg = {
        # some reqd/cfg keys are duplicated with top-level args
        'net_name': 'networkName',
        'net_id': 'networkId',
        'vlan_id': 'vlanId',
        'vrf': 'vrf',
        'gw_ip': 'gatewayIpAddress'
    }
    template = dict((t_cfg[k], net[k]) for k in t_cfg.keys() if net.get(k) is not None)
    # templateConfig needs to be in json syntax before overall payload
    payload['networkTemplateConfig'] = json.dumps(template)

    # payload = json.dumps(payload)

    # logit('net_payload:tmeplate %s' %template)
    logit('net_payload:payload(all) %s' %payload)
    # import epdb;epdb.serve()
    return payload

def att_payload(facts, name):
    """Create attachList for one network"""
    # TBD: We already have the 'have' data so I should be able to
    # create a payload from copying that, then update it with diff vals.

    # { "fabric": "cvh4",
    # "networkName": "c1",
    # "serialNumber": "SAL1821T9EF",
    # "switchPorts": "Ethernet1/5,Ethernet1/6",
    # "deployment": true }
    attach_list = []
    # diff['c1']['att'] =
    #   {'10.122.197.192': {'ports': ['Ethernet1/1']}, '1.1.1.1': ...}
    att = facts['diff'][name]['att']
    for ip in att.keys():
        # device = facts['want'][name]['att'][device_id]

        attach_list.append({
            "fabric": facts['fabric'],
            "networkName": name,
            "serialNumber": facts['sn'][ip],
            "switchPorts": (',').join(att[ip]['ports']),
            "detachSwitchPorts": "", # fix these hard-codes
            "vlan": 2301,
            "dot1QVlan": 1,
            "untagged": False,
            "freeformConfig": "",
            "deployment": True,
            "extensionValues": "",
            "instanceValues": ""
        })


    # import epdb;epdb.serve()
    return attach_list

def main():
    """ main entry point for module execution
    """
    element_spec = dict(
        state=dict(type='str', default='merged'),
        fabric=dict(required=True, type='str'),
        config=dict(required=True, type=list),
    )
    module = AnsibleModule(argument_spec=element_spec,
                           # required_one_of=required_one_of,
                           # mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)

    facts = DcnmNetwork(module, Connection(module._socket_path))
    facts.populate_have()
    facts.get_diffs()


    import epdb;epdb.serve()
    # populate_facts(facts)
    get_diffs(facts)

    # TODO: Add checkmode support

    # WIP BELOW THIS POINT
    result = dict(changed=False, response=dict())
    state = module.params['state']
    if state == 'query':
        # Return a playbook yaml report of 'have' data.
        resp = query(facts)
        # Q: what is the proper way to return this output to user?
    elif state == 'deleted':
        resp = deleted(facts)
    elif state == 'merged':
        # import epdb;epdb.serve()
        # for f in facts['have']:  ## TEST CODE ONLY - REMOVES NET FOR MERGED TESTING
        #     deleted(facts)  ## REMOVEME

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
