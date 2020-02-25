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
from textwrap import dedent

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.dcnm.dcnm import dcnm_send, get_fabric_inventory_details
from ansible.module_utils.network.dcnm.dcnm import validate_list_of_dicts
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

class DcnmNetwork:

    def __init__(self, module):
        self.module = module
        self.response = None
        self.state = module.params['state']
        self.fabric = module.params['fabric']
        self.config = module.params['config']
        self.have_net = dict()
        self.have_att = dict()
        self.have_dep = dict()
        self.want_net = dict()
        self.want_att = dict()
        self.want_dep = dict()
        self.diff_net = dict()
        self.diff_att = dict()
        self.diff_dep = dict()

        self.ip_sn = self.get_ip_sn()
        self.get_want()
        self.get_have()

    def get_ip_sn(self):
        # TBD: Requires that fabric exist in dcnm.
        inv = get_fabric_inventory_details(self.module, self.fabric)
        if inv:
            return inv
        else:
            self.module.fail_json(msg="fabric '{}' does not exist or no devices present in fabric".format(self.fabric))

    def validate_input(self):
        """Parse the playbook values, validate and normalize to param specs."""
        net_spec = dict(
            net_name=dict(required=True, type='str'),
            net_id=dict(required=True, type='int'),
            vrf=dict(required=True, type='str'),
            #
            attach=dict(type='list'),
            deploy=dict(type='bool'),
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
        validated = []
        # Validate net params
        valid_net, invalid_params = validate_list_of_dicts(self.config, net_spec)
        for net in valid_net:
            # TBD: add'l net validation may occur here; e.g. vrf name length, etc
            # Validate attach params
            if net.get('attach'):
                valid_att, invalid_att = validate_list_of_dicts(net['attach'], att_spec)
                # TBD: add'l att validation may occur here
                net['attach'] = valid_att
                invalid_params.extend(invalid_att)
            validated.append(net)

        if invalid_params:
            msg = 'Invalid parameters in playbook: {}'.format('\n'.join(invalid_params))
            raise Exception(msg)

        # logit('validated: %s' %validated)
        return validated

    def get_want(self):
        validated = self.validate_input()
        for net in validated:
            net_name = net['net_name']
            want = dict(
                fabric=self.fabric,
                networkName=net_name,
                networkId=net['net_id'],
                gatewayIpAddress=net['gw_ip'],
                vlanId=net['vlan_id'],
                vrf=net['vrf'],
                networkTemplate=net['template'],
                networkExtensionTemplate=net['template_ext'],
            )
            self.want_net.update({ net_name: want })
            # Create a dict of att data
            if net['attach']:
                attach = []
                for device in net['attach']:
                    att = dict(
                        fabric=self.fabric,
                        networkName=net_name,
                        # switchName=switch_name,
                        serialNumber=self.ip_sn[device['ip']],
                        switchPorts=(',').join(device['ports']),
                        detachSwitchPorts='',
                        deploy=device['deploy'],
                    )
                    attach.append(att)
                self.want_att.update({ net_name: attach })

            self.want_dep = net['deploy']

        logit('get_want: net: %s\natt: %s\ndep: %s' %(self.want_net, self.want_att, self.want_dep))

    def get_have(self):
        """Check for existing networks and attached states.
        """
        # GET all networks
        path = '/rest/top-down/fabrics/{}/networks'.format(self.fabric)
        resp = dcnm_send(self.module, 'GET', path)
        if resp['RETURN_CODE'] != 200:
            raise Exception('TBD')

        all_nets = resp['DATA']
        if all_nets:
            # Create a list of nets to GET all attach states for networks
            # found above (there may be none)
            all_net_names = ','.join([ k['networkName'] for k in all_nets ])
            path += '/attachments?network-names={}'.format(all_net_names)
            resp = dcnm_send(self.module, 'GET', path)
            if resp['RETURN_CODE'] != 200:
                raise Exception('TBD')
            all_attach = resp['DATA']
            logit('all_attach: %s' %all_attach)

        # Update 'have' facts dict with current net/attach/deploy states
        for net in all_nets:
            net_name = net['networkName']
            template = json.loads(net.get('networkTemplateConfig', {}))
            net['networkTemplateConfig'] = template
            self.have_net.update({ net_name: net })

            # Get a list of switches that this specific net is attached to.
            for attach in all_attach:
                if attach.get('networkName') == net_name:
                    attached_devices = attach.get('lanAttachList')
                    break
            else:
                attached_devices = []
            if attached_devices:
                normalized = []
                for device in attached_devices:
                    deploy = True if (device.get('lanAttachState') in ['DEPLOYED', 'PENDING']) else False
                    device['deploy'] = deploy
                    normalized.append(device)
                self.have_att.update({ net_name: normalized})

            logit('have_att:%s: %s' %(net_name, self.have_att))
            # import epdb;epdb.serve()

        # sample_att_raw = [    #### REMOVEME
        #     {'networkName': 'c1', 'switchName': 'dt-n9k5-1', 'switchRole': 'leaf',
        #      'fabricName': 'cvh4', 'lanAttachState': 'DEPLOYED', 'isLanAttached': True,
        #      'portNames': 'Ethernet1/13,Ethernet1/12', 'switchSerialNo': 'SAL1821T9EF',
        #      'switchDbId': 389920, 'ipAddress': '10.122.197.192', 'networkId': 30001,
        #      'vlanId': 2301}]

    def query(self):
        """Create a yaml-formatted string of current 'have' data.
        """
        # ** TBD: This report includes all networks in the fabric. **
        # **      Should this only look at the networks found in the playbook?? **
        x_net = dict(
            net_id='networkId',
            vlan_id='vlanId',
            vrf='vrf',
            gw_ip='gatewayIpAddress',
        )
        x_att = dict(
            # switch_name='switchName',
            ports='portNames',
            deploy='deploy',
        )
        rpt = dedent('''\
        tasks:
          dcnm_network:
            fabric: {}
            config:''').format(self.fabric)
        have_net = self.have_net
        have_att = self.have_att
        for net_name in have_net.keys():
            net = have_net[net_name]
            rpt += '\n    - net_name: {}'.format(net_name)
            for k in x_net.keys():
                if net.get(x_net[k]) is not None:  ## TBD: assumes always exists. safe?
                    rpt += '\n      {}: {}'.format(k, net[x_net[k]])
            attach_list = have_att.get(net_name)
            if attach_list:
                rpt += '\n      attach:'
                for device in attach_list:
                    rpt += '\n        - ip: {}'.format(device['ipaddress'])
                    for k in x_att.keys():
                        if device.get(x_att[k]) is not none:
                            rpt += '\n          {}: {}'.format(k, device[x_att[k]])
        logit('rpt: %s' %rpt)
        # import epdb;epdb.serve()
        self.response = rpt

    def deleted(self):
        # todo: global purge when config null.
        # todo: check attach state; also need to deploy change to devices
        responses = []
        for net_name in self.want_net.keys():
            path = '/rest/top-down/fabrics/{}/networks/{}'.format(self.fabric, net_name)
            resp = dcnm_send(self.module, 'DELETE', path)
            # error checking...
            responses.append(resp)
        self.response = responses
        # import epdb;epdb.serve()

    def merged(self):
        pass

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

    # facts = DcnmNetwork(module, Connection(module._socket_path))
    facts = DcnmNetwork(module)
    # TODO: Add checkmode support

    # WIP BELOW THIS POINT
    result = dict(changed=False, response=dict())
    state = module.params['state']
    if state == 'query':
        facts.query()
        # Q: what is the proper way to return this output to user?

    elif state == 'deleted':
        facts.deleted()

    elif state == 'merged':
        # for f in facts['have']:  ## TEST CODE ONLY - REMOVES NET FOR MERGED TESTING
        #     deleted(facts)  ## REMOVEME
        facts.merged() ### REFACTOR TO USE BULK CREATE/ATTACH

    # import epdb;epdb.serve()
    result['response'] = facts.response
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

    # def merged(self):
    #     ############ WIP ##############
    #     ############ WIP ##############
    #     ############ WIP ##############
    #     ############ WIP ##############
    #     """ Check for non-idempotent networks, create payloads, update DCNM.
    #     """
    #     # Use bulk-create for all new networks, use PUT networks for updates.
    #     # TBD: if vlan_id is empty then DCNM will automatically pick the next vlan
    #     #      from the fabric; however,net_id/VNI can also be automatically
    #     #      populated, in which case use POST /rest/managed-pool/fabrics/{{fabric}}/segments/ids
    #     #       to get the next avail VNI e.g. get_vni()
    #     # TBD: check_mode
    #     # TBD: log separate results for each network, each attach, ...?
    #     # TBD: create a collective 'resp', carry in facts?
    #     have = self.have
    #     want = self.want
    #     diff = self.diff
    #
    #     # List of new net objects to bulk-create in DCNM
    #     new_nets = [ i for i in diff.keys() if not have.get(i) ]
    #     if new_nets:
    #         method = 'POST'
    #         payload = []
    #         for name in new_nets:
    #             payload.append(net_payload(facts, name))
    #         payload = json.dumps(payload)
    #         logit('bulk payload: %s' %payload)
    #         path = '/rest/top-down/bulk-create/networks'
    #         resp = send(facts, method, path, payload)
    #         # TBD: log results for each network in the bulk create
    #         logit ('resp:bulk: %s' %resp)
    #
    #     # List of existing net objects to update in DCNM
    #     upd_nets = [ i for i in diff.keys() if have.get(i) ]
    #     for name in upd_nets:
    #         # There is no bulk-update; use a separate payload for each net
    #         payload = net_payload(facts, name)
    #         payload = json.dumps(payload)
    #         path = '/rest/top-down/fabrics/{}/networks/{}'.format(fabric, name)
    #         resp = send(facts, 'PUT', path, payload)
    #
    #     # List of networks to create or update attachments
    #     upd_atts = [ i for i in diff.keys() if diff[i].get('att') ]
    #     for name in upd_atts:
    #         # NOTES on deploy states:
    #         #  PENDING: attached, not deployed
    #         #  OUT_OF_SYNC: deploy failed
    #         #  PROGRESS: transient state before DEPLOYED
    #         #  DEPLOYED: success
    #         # TBD: For now we'll update attachments one at a time but revisit this
    #         # and see if updating all diff attachments in one api call is feasible.
    #         # TBD: For merge we don't care if there are extra ports or attachments
    #         # on the device, but if so the diff might cause a false non-idempotence.
    #         # TBD: handle detachPorts logic in diff method. If detachPorts populated
    #         # and port not in 'switchports' then idempotent; also need a per-port
    #         # check when diff the 'port' arg, since the order can be different and
    #         # incomplete; e.g. have:1,2 want:attach 1,3 detach 2,
    #         #  diff:att 3 det 2. post-have: 1,3 now idempotent.
    #         payload = {
    #             "networkName": name,
    #             "lanAttachList": att_payload(facts, name)
    #         }
    #         payload = json.dumps([payload]) ## TBD: Send all updates at once?
    #         # logit('upd_atts:json: %s' %payload)
    #         path = '/rest/top-down/fabrics/{}/networks/attachments'.format(fabric)
    #         resp = send(facts, 'POST', path, payload)
    #         ## TBD: Response should be as below; need to parse EACH S/N for success.
    #         #  {'c1-[SAL1821T9EF/dt-n9k5-1]': 'SUCCESS'}
    #         logit('upd_atts:resp: %s' %resp)
    #         # import epdb;epdb.serve()
    #
    #     if diff:
    #         # TBD: all: '/rest/top-down/fabrics/networks/deployments', payload='n1,n2'
    #         # per: '/rest/top-down/fabrics/{}/networks/{}/deploy'
    #         for name in diff.keys():
    #             if not diff[name].get('deploy'):
    #                 continue
    #             path = '/rest/top-down/fabrics/{}/networks/{}/deploy'.format(fabric, name)
    #             resp = send(facts, 'POST', path)
    #             ## TBD: Response should be as below; need to parse EACH S/N for success.
    #             #  {'c1-[SAL1821T9EF/dt-n9k5-1]': 'SUCCESS'}
    #             logit('upd_atts:resp: %s' %resp)
    #
    #     # List of networks with changes to deploy
    #
    #     self.response = resp  ## NEEDS list of per-network results
    #     import epdb;epdb.serve()
    #
    # def net_payload(self, name):
    #     """Create payload for network PUT/POST"""
    #     net = facts['want'][name]['net']
    #     payload = { 'fabric': facts['fabric'] }
    #     xtable = {
    #         'template': 'networkTemplate',
    #         'template_ext': 'networkExtensionTemplate',
    #         'net_name': 'networkName',
    #         # displayName: same as networkName
    #         'net_id': 'networkId',   # VNI
    #         'vrf': 'vrf',
    #     }
    #     payload.update(dict((xtable[k], net[k]) for k in xtable.keys() if net.get(k) is not None))
    #     # logit('net_payload:top: %s' %payload)
    #
    #     # Build templateConfig arguments.
    #     t_cfg = {
    #         # some reqd/cfg keys are duplicated with top-level args
    #         'net_name': 'networkName',
    #         'net_id': 'networkId',
    #         'vlan_id': 'vlanId',
    #         'vrf': 'vrf',
    #         'gw_ip': 'gatewayIpAddress'
    #     }
    #     template = dict((t_cfg[k], net[k]) for k in t_cfg.keys() if net.get(k) is not None)
    #     # templateConfig needs to be in json syntax before overall payload
    #     payload['networkTemplateConfig'] = json.dumps(template)
    #
    #     # payload = json.dumps(payload)
    #
    #     # logit('net_payload:tmeplate %s' %template)
    #     logit('net_payload:payload(all) %s' %payload)
    #     # import epdb;epdb.serve()
    #     return payload
    #
    # def att_payload(facts, name):
    #     """Create attachList for one network"""
    #     # TBD: We already have the 'have' data so I should be able to
    #     # create a payload from copying that, then update it with diff vals.
    #
    #     # { "fabric": "cvh4",
    #     # "networkName": "c1",
    #     # "serialNumber": "SAL1821T9EF",
    #     # "switchPorts": "Ethernet1/5,Ethernet1/6",
    #     # "deployment": true }
    #     attach_list = []
    #     # diff['c1']['att'] =
    #     #   {'10.122.197.192': {'ports': ['Ethernet1/1']}, '1.1.1.1': ...}
    #     att = facts['diff'][name]['att']
    #     for ip in att.keys():
    #         # device = facts['want'][name]['att'][device_id]
    #
    #         attach_list.append({
    #             "fabric": facts['fabric'],
    #             "networkName": name,
    #             "serialNumber": facts['sn'][ip],
    #             "switchPorts": (',').join(att[ip]['ports']),
    #             "detachSwitchPorts": "", # fix these hard-codes
    #             "vlan": 2301,
    #             "dot1QVlan": 1,
    #             "untagged": False,
    #             "freeformConfig": "",
    #             "deployment": True,
    #             "extensionValues": "",
    #             "instanceValues": ""
    #         })
    #
    #
    #     # import epdb;epdb.serve()
    #     return attach_list
    #
    # def get_diffs(self):
    #     """ Create diffs for each network in 'want'
    #     """
    #     ##### WIP: ...
    #     # Due to the way the api's work, we can't really make incremental changes
    #     # to the objects since the payload requires a number of mandatory items.
    #     # That makes this diff data somewhat unnecessary since we really just
    #     # need to know whether anything has changed and then send the entire
    #     # 'want' payload regardless. May need to revisit this...
    #     for net_name in self.want.keys():
    #         for data_type in ['net', 'att']:
    #             # deploy = want['deploy']
    #
    #             have = self.have.get(net_name, {}).get(data_type, {})
    #             want = self.want.get(net_name, {}).get(data_type, {})
    #
    #             diff = dict_diff(have, want)
    #             if diff:
    #                 self.diff.setdefault(net_name, {})
    #                 self.diff[net_name][data_type] = diff
    #             logit('get_diffs: %s: %s\nhave: %s\nwant: %s\nself.diff: %s' %(net_name, data_type, have, want, self.diff))
    #
    #     # import epdb;epdb.serve()
    #
