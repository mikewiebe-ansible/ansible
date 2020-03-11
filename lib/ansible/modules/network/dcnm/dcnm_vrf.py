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

import json, socket, time #,yaml
from ansible.module_utils.network.dcnm.dcnm import get_fabric_inventory_details, dcnm_send, validate_list_of_dicts
from ansible.module_utils.connection import Connection
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
    - "Send REST API requests to DCNM controller for VRF operations - Create, Attach, Deploy and Delete"
author: Shrishail Kariyappanavar(@nkshrishail)
options:
  fabric:
    description:
    - 'Name of the target fabric for VRF operations'
    type: str
    required: yes
  state:
    description:
      - The state of the configuration after module completion.
    type: str
    choices:
      - merged
      - replaced
      - overridden
      - deleted
      - query
    default: merged
  config:
    description: 'List of details of VRFs being managed'
    type: list
    elements: dict
    required: true (except for state: deleted)
    suboptions:
      vrf_name:
        description: 'Name of the VRF being managed'
        type: str
        required: true 
      vrf_id:
        description: 'ID of the VRF being managed'
        type: int
        required: true
      vrf_template:
        description: 'Name of the config template to be used'
        type: str
        default: 'Default_VRF_Universal'
      vrf_extension_template: 
        description: 'Name of the extension config template to be used'
        type: str
        default: 'Default_VRF_Extension_Universal'
      source:
        description: '??'
        type: str
        default: null
      service_vrf_template:
        description: 'Service vrf template'
        type: str
        default: null
      suboptions:
        attach:
          description: 'List of VRF attachment details'
          type: list
          elements: dict
        deploy:
          description: 'Global knob to control whether to deploy the attachment'
          type: bool
          default: true
          suboptions:
            ip_address:
              description: 'IP address of the switch where VRF will be attached or detached'
              type: ipv4
              required: true
            vlan_id:
              description: 'vlan ID for the VRF attachment'
              type: int
              required: true
            deploy:
              description: 'Per switch knob to control whether to deploy the attachment'
              type: bool
              default: true
'''

EXAMPLES = '''
- name: Create VRFs
    dcnm_vrf:
      fabric: vxlan-fabric
      state: merged 
      config:
        - vrf_name: ansible-vrf-r1
          vrf_id: 9008011
          vrf_template: Default_VRF_Universal
          vrf_extension_template: Default_VRF_Extension_Universal
          source: null
          service_vrf_template: null
          attach:
            - ip_address: 10.122.197.224
              vlan_id: 202
              deploy: true
            - ip_address: 10.122.197.225
              vlan_id: 203
            deploy: false
        - vrf_name: ansible-vrf-r2
          vrf_id: 9008012
          vrf_template: Default_VRF_Universal
          vrf_extension_template: Default_VRF_Extension_Universal
          source: null
          service_vrf_template: null
          attach:
            - ip_address: 10.122.197.224
              vlan_id: 402
            - ip_address: 10.122.197.225
              vlan_id: 403

- name: Replace VRFs
    dcnm_vrf:
      fabric: vxlan-fabric
      state: replaced 
      config:
        - vrf_name: ansible-vrf-r1
          vrf_id: 9008011
          vrf_template: Default_VRF_Universal
          vrf_extension_template: Default_VRF_Extension_Universal
          source: null
          service_vrf_template: null
          attach:
            - ip_address: 10.122.197.224
              vlan_id: 202
              deploy: true
            # Delete this attachment
            # - ip_address: 10.122.197.225
            #   vlan_id: 203
            # deploy: true
            # Create the following attachment
            - ip_address: 10.122.197.226
              vlan_id: 204
              deploy: true
        # Dont touch this if its present on DCNM
        # - vrf_name: ansible-vrf-r2
        #   vrf_id: 9008012
        #   vrf_template: Default_VRF_Universal
        #   vrf_extension_template: Default_VRF_Extension_Universal
        #   source: null
        #   service_vrf_template: null
        #   attach:
        #     - ip_address: 10.122.197.224
        #       vlan_id: 402
        #     - ip_address: 10.122.197.225
        #       vlan_id: 403
              
- name: Override VRFs
    dcnm_vrf:
      fabric: vxlan-fabric
      state: overridden 
      config:
        - vrf_name: ansible-vrf-r1
          vrf_id: 9008011
          vrf_template: Default_VRF_Universal
          vrf_extension_template: Default_VRF_Extension_Universal
          source: null
          service_vrf_template: null
          attach:
            - ip_address: 10.122.197.224
              vlan_id: 202
              deploy: true
            # Delete this attachment
            # - ip_address: 10.122.197.225
            #   vlan_id: 203
            # deploy: true
            # Create the following attachment
            - ip_address: 10.122.197.226
              vlan_id: 204
              deploy: true
        # Delete this VRF
        # - vrf_name: ansible-vrf-r2
        #   vrf_id: 9008012
        #   vrf_template: Default_VRF_Universal
        #   vrf_extension_template: Default_VRF_Extension_Universal
        #   source: null
        #   service_vrf_template: null
        #   attach:
        #     - ip_address: 10.122.197.224
        #       vlan_id: 402
        #     - ip_address: 10.122.197.225
        #       vlan_id: 403
              
- name: Delete selected VRFs
    dcnm_vrf:
      fabric: vxlan-fabric
      state: deleted 
      config:
        - vrf_name: ansible-vrf-r1
          vrf_id: 9008011
          vrf_template: Default_VRF_Universal
          vrf_extension_template: Default_VRF_Extension_Universal
          source: null
          service_vrf_template: null 
        - vrf_name: ansible-vrf-r2
          vrf_id: 9008012
          vrf_template: Default_VRF_Universal
          vrf_extension_template: Default_VRF_Extension_Universal
          source: null
          service_vrf_template: null
          
- name: Delete all the VRFs
    dcnm_vrf:
      fabric: vxlan-fabric
      state: deleted
      
- name: Create VRFs
    dcnm_vrf:
      fabric: vxlan-fabric
      state: query
      config:
        - vrf_name: ansible-vrf-r1
          vrf_id: 9008011
          vrf_template: Default_VRF_Universal
          vrf_extension_template: Default_VRF_Extension_Universal
          source: null
          service_vrf_template: null
        - vrf_name: ansible-vrf-r2
          vrf_id: 9008012
          vrf_template: Default_VRF_Universal
          vrf_extension_template: Default_VRF_Extension_Universal
          source: null
          service_vrf_template: null
'''

import datetime
def logit(msg):
    with open('/tmp/alog.txt', 'a') as of:
        d = datetime.datetime.now().replace(microsecond=0).isoformat()
        of.write("---- %s ----\n%s\n" % (d,msg))


class DcnmVrf:

    def __init__(self, module):
        self.module = module
        self.params = module.params
        self.fabric = module.params['fabric']
        self.config = module.params.get('config')
        self.check_mode = False
        self.conn = Connection(module._socket_path)
        self.have_create = []
        self.want_create = []
        self.diff_create = []
        self.have_attach = []
        self.want_attach = []
        self.diff_attach = []
        self.have_deploy = {}
        self.want_deploy = {}
        self.diff_deploy = {}
        self.diff_delete = {}
        self.query = []
        self.ip_sn = get_fabric_inventory_details(self.module, self.fabric)


    def diff_for_attach_deploy(self, want_a, have_a):

        attach_list = list()

        if not want_a:
            return attach_list

        dep_vrf = False
        for want in want_a:
            found = False
            if have_a:
                for have in have_a:
                    if want['serialNumber'] == have['serialNumber']:
                        found = True

                        ## Is this allowed use case? User wants to update vlan on an already attached and deployed VRF?
                        ## DCNM is accepting updates on an already deployed VRF attachment,
                        ## Ex: update vlan ID on an already deployed VLAN, just need to re-attach with new vlan and re-deploy
                        ## No need to detach and undeploy beforehand.
                        if bool(have['isAttached']) and bool(want['isAttached']):
                            if have['vlan'] != want['vlan']:
                                del want['isAttached']
                                attach_list.append(want)
                                continue

                        if bool(have['isAttached']) is not bool(want['isAttached']):
                            del want['isAttached']
                            attach_list.append(want)
                            continue

                        if bool(have['deployment']) is not bool(want['deployment']):
                            dep_vrf = True

            if not found:
                if bool(want['deployment']):
                    del want['isAttached']
                    attach_list.append(want)

        # logit(json.dumps(attach_list, indent=4, sort_keys=True))
        return attach_list, dep_vrf


    def update_attach_params(self, attach, vrf_name, deploy):
        serial = ""
        for ip, ser in self.ip_sn.items():
            if ip == attach['ip_address']:
                serial = ser

        if attach:
            attach.update({'fabric': self.fabric})
            attach.update({'vrfName': vrf_name})
            attach.update({'vlan': attach.get('vlan_id')})
            attach.update({'deployment': deploy})
            attach.update({'isAttached': deploy})
            attach.update({'serialNumber': serial})
            attach.update({'extensionValues': ""})
            attach.update({'instanceValues': ""})
            attach.update({'freeformConfig': ""})
            if 'deploy' in attach:
                del attach['deploy']
            del attach['vlan_id']
            del attach['ip_address']
        else:
            attach = dict()

        return attach


    def diff_for_create(self, want, have):
        create = dict()
        if not have:
            create = want
        else:
            if have['vrfId'] != want['vrfId']:
                logit("diff_for_create - VRF ID cant be updated to a different value")
                pass
                # module.exit_json("Can not update the VRF ID") # need to find a proper way to err
            elif have['serviceVrfTemplate'] != want['serviceVrfTemplate'] or \
                    have['source'] != want['source'] or \
                    have['vrfTemplate'] != want['vrfTemplate'] or \
                    have['vrfExtensionTemplate'] != want['vrfExtensionTemplate']:
                create = want
            else:
                pass

        return create


    def update_create_params(self, create):

        if not create:
            return create

        v_template = 'Default_VRF_Universal' if not create.get('vrf_template') else create['vrf_template']
        ve_template = 'Default_VRF_Extension_Universal' if not create.get('vrf_extension_template') \
            else create['vrf_extension_template']
        src = None if not create.get('source') else create['source']
        s_v_template = None if not create.get('service_vrf_template') else create['service_vrf_template']

        create_upd = dict()
        create_upd.update({'fabric': self.fabric})
        create_upd.update({'vrfName': create['vrf_name']})
        create_upd.update({'vrfTemplate': v_template})
        create_upd.update({'vrfExtensionTemplate': ve_template})
        create_upd.update({'vrfId': create['vrf_id']})
        create_upd.update({'serviceVrfTemplate': s_v_template})
        create_upd.update({'source': src})

        template_conf = dict()
        template_conf.update({'vrfSegmentId': create['vrf_id']})
        template_conf.update({'vrfName': create['vrf_name']})

        create_upd.update({'vrfTemplateConfig': json.dumps(template_conf)})

        return create_upd


    def get_have(self):
        """

        Sufficient error checking??
        Possiibe inputs from DCNM:
        1. API failures
        2. Blank responses - no vrfs
                           - no attachments
                           - no deployments
        3. typecast booleans before checks?
        """

        have_create = list()
        have_attach = list()
        have_deploy = dict()

        all_vrfs = ''

        method = 'GET'
        path = '/rest/top-down/fabrics/{}/vrfs'.format(self.fabric)

        resp = dcnm_send(self.module, method, path)

        if resp.get('ERROR') == 'Not Found' and resp.get('RETURN_CODE') == 404:
            logit("Fabric not found")
            return have_create, have_attach, have_deploy

        if not resp['DATA']:
            return have_create, have_attach, have_deploy

        for vrf in resp['DATA']:
            all_vrfs += vrf['vrfName'] + ','

        path = '/rest/top-down/fabrics/{}/vrfs/attachments?vrf-names={}'.format(self.fabric, all_vrfs[:-1])

        all_vrf_attach = dcnm_send(self.module, method, path)

        for vrf in resp['DATA']:
            t_conf = dict()
            t_conf.update({'vrfSegmentId': vrf['vrfId']})
            t_conf.update({'vrfName': vrf['vrfName']})

            vrf.update({'vrfTemplateConfig': json.dumps(t_conf)})
            del vrf['vrfStatus']
            have_create.append(vrf)

        all_vrfs = ''

        for vrf_attach in all_vrf_attach['DATA']:
            if not vrf_attach.get('lanAttachList'):
                continue
            attach_list = vrf_attach['lanAttachList']
            dep_vrf = ''
            for attach in attach_list:
                attach_state = False if attach['lanAttachState'] == "NA" else True
                deploy = attach['isLanAttached']
                if bool(deploy) and (attach['lanAttachState'] == "OUT-OF-SYNC" or
                                     attach['lanAttachState'] == "PENDING"):
                    deploy = False

                if bool(deploy):
                    dep_vrf = attach['vrfName']

                sn = attach['switchSerialNo']
                vlan = attach['vlanId']
                del attach['vlanId']
                del attach['switchSerialNo']
                del attach['switchName']
                del attach['switchRole']
                del attach['ipAddress']
                del attach['lanAttachState']
                del attach['isLanAttached']
                del attach['vrfId']
                del attach['fabricName']

                attach.update({'fabric': self.fabric})
                attach.update({'vlan': vlan})
                attach.update({'serialNumber': sn})
                attach.update({'deployment': deploy})
                attach.update({'extensionValues': ""})
                attach.update({'instanceValues': ""})
                attach.update({'freeformConfig': ""})
                attach.update({'isAttached': attach_state})

            if dep_vrf:
                all_vrfs += dep_vrf + ","

        have_attach = all_vrf_attach['DATA']

        if all_vrfs:
            have_deploy.update({'vrfNames': all_vrfs[:-1]})

        # logit(json.dumps(have_create, indent=4, sort_keys=True))
        # logit(json.dumps(have_attach, indent=4, sort_keys=True))
        # logit(json.dumps(have_deploy, indent=4, sort_keys=True))

        self.have_create = have_create
        self.have_attach = have_attach
        self.have_deploy = have_deploy


    def get_want(self):
        want_create = list()
        want_attach = list()
        want_deploy = dict()

        all_vrfs = ""

        if not self.config:
            return

        for vrf in self.config:
            vrf_attach = dict()
            vrfs = list()

            vrf_deploy = True
            if "deploy" in vrf:
                vrf_deploy = vrf['deploy']

            want_create.append(self.update_create_params(vrf))

            if not vrf.get('attach'):
                continue
            for attach in vrf['attach']:
                deploy = vrf_deploy if "deploy" not in attach else attach['deploy']
                vrfs.append(self.update_attach_params(attach,
                                                 vrf['vrf_name'],
                                                 deploy))
            if vrfs:
                vrf_attach.update({'vrfName': vrf['vrf_name']})
                vrf_attach.update({'lanAttachList': vrfs})
                want_attach.append(vrf_attach)

            all_vrfs += vrf['vrf_name'] + ","

        if all_vrfs:
            want_deploy.update({'vrfNames': all_vrfs[:-1]})

        # logit(json.dumps(want_create, indent=4, sort_keys=True))
        # logit(json.dumps(want_attach, indent=4, sort_keys=True))
        # logit(json.dumps(want_deploy, indent=4, sort_keys=True))

        self.want_create = want_create
        self.want_attach = want_attach
        self.want_deploy = want_deploy


    def get_diff_delete(self):
        #
        # Delete the vrfs mentioned in the play.
        # Delete all vrfs deployed on dcnm if none of them are in the play (config is absent)

        diff_attach = list()
        diff_deploy = dict()
        diff_delete = dict()

        all_vrfs = ''

        if self.config:

            for want_c in self.want_create:
                if not next((have_c for have_c in self.have_create if have_c['vrfName'] == want_c['vrfName']), None):
                    continue
                diff_delete.update({want_c['vrfName']: 'DEPLOYED'})

                have_a = next((attach for attach in self.have_attach if attach['vrfName'] == want_c['vrfName']), None)

                if not have_a:
                    continue

                to_del = list()
                atch_h = have_a['lanAttachList']
                for a_h in atch_h:
                    if a_h['isAttached']:
                        del a_h['isAttached']
                        a_h.update({'deployment': False})
                        to_del.append(a_h)
                if to_del:
                    have_a.update({'lanAttachList': to_del})
                    diff_attach.append(have_a)
                    all_vrfs += have_a['vrfName'] + ","
            if all_vrfs:
                diff_deploy.update({'vrfNames': all_vrfs[:-1]})

        else:
            for have_a in self.have_attach:
                to_del = list()
                atch_h = have_a['lanAttachList']
                for a_h in atch_h:
                    if a_h['isAttached']:
                        del a_h['isAttached']
                        a_h.update({'deployment': False})
                        to_del.append(a_h)
                if to_del:
                    have_a.update({'lanAttachList': to_del})
                    diff_attach.append(have_a)
                    all_vrfs += have_a['vrfName'] + ","

                diff_delete.update({have_a['vrfName']: 'DEPLOYED'})
            if all_vrfs:
                diff_deploy.update({'vrfNames': all_vrfs[:-1]})

        # logit(json.dumps(diff_attach, indent=4, sort_keys=True))
        # logit(json.dumps(diff_deploy, indent=4, sort_keys=True))
        # logit(json.dumps(diff_delete, indent=4, sort_keys=True))

        self.diff_attach = diff_attach
        self.diff_deploy = diff_deploy
        self.diff_delete = diff_delete


    def get_diff_override(self):
        # overridden:
        # DCNM should reflect exactly like the play.
        # The vrfs and their attachments not present in the play should be removed from DCNM if present there.
        # The vrfs and their attachments present in the play should replace whats there on DCNM if present there

        all_vrfs = ''
        diff_delete = list()

        self.get_diff_replace()

        diff_create = self.diff_create
        diff_attach = self.diff_attach
        diff_deploy = self.diff_deploy

        for have_a in self.have_attach:
            found = next((vrf for vrf in self.want_create if vrf['vrfName'] == have_a['vrfName']), None)

            to_del = list()
            if not found:
                atch_h = have_a['lanAttachList']
                for a_h in atch_h:
                    if a_h['isAttached']:
                        del a_h['isAttached']
                        a_h.update({'deployment': False})
                        to_del.append(a_h)

                if to_del:
                    have_a.update({'lanAttachList': to_del})
                    diff_attach.append(have_a)
                    all_vrfs += have_a['vrfName'] + ","

                diff_delete.append(have_a['vrfName'])

        if all_vrfs:
            vrfs = (diff_deploy['vrfNames'] + "," + all_vrfs[:-1]) if diff_deploy else all_vrfs[:-1]
            diff_deploy.update({'vrfNames': vrfs})

        # logit(json.dumps(diff_create, indent=4, sort_keys=True))
        # logit(json.dumps(diff_attach, indent=4, sort_keys=True))
        # logit(json.dumps(diff_deploy, indent=4, sort_keys=True))
        # logit(json.dumps(diff_delete, indent=4, sort_keys=True))

        self.diff_create = diff_create
        self.diff_attach = diff_attach
        self.diff_deploy = diff_deploy
        self.diff_delete = diff_delete


    def get_diff_replace(self):
        all_vrfs = ''

        self.get_diff_merge()
        diff_create = self.diff_create
        diff_attach = self.diff_attach
        diff_deploy = self.diff_deploy

        for have_a in self.have_attach:
            r_vrf_list = list()
            h_in_w = False
            for want_a in self.want_attach:
                if have_a['vrfName'] == want_a['vrfName']:
                    h_in_w = True
                    atch_h = have_a['lanAttachList']
                    atch_w = want_a.get('lanAttachList')

                    for a_h in atch_h:
                        if not a_h['isAttached']:
                            continue
                        a_match = False

                        if atch_w:
                            for a_w in atch_w:
                                if a_h['serialNumber'] == a_w['serialNumber']:
                                    # Have is already in diff, no need to continue looking for it.
                                    a_match = True
                                    break
                        if not a_match:
                            del a_h['isAttached']
                            a_h.update({'deployment': False})
                            r_vrf_list.append(a_h)
                    break

            if not h_in_w:
                found = next((vrf for vrf in self.want_create if vrf['vrfName'] == have_a['vrfName']), None)
                if found:
                    atch_h = have_a['lanAttachList']
                    for a_h in atch_h:
                        if not a_h['isAttached']:
                            continue
                        del a_h['isAttached']
                        a_h.update({'deployment': False})
                        r_vrf_list.append(a_h)

            if r_vrf_list:
                in_diff = False
                for d_attach in self.diff_attach:
                    if have_a['vrfName'] == d_attach['vrfName']:
                        in_diff = True
                        d_attach['lanAttachList'].extend(r_vrf_list)
                        break

                if not in_diff:
                    r_vrf_dict = dict()
                    r_vrf_dict.update({'vrfName': have_a['vrfName']})
                    r_vrf_dict.update({'lanAttachList': r_vrf_list})
                    diff_attach.append(r_vrf_dict)
                    all_vrfs += have_a['vrfName'] + ","

        if not all_vrfs:
            # logit(json.dumps(diff_create, indent=4, sort_keys=True))
            # logit(json.dumps(diff_attach, indent=4, sort_keys=True))
            # logit(json.dumps(diff_deploy, indent=4, sort_keys=True))
            self.diff_create = diff_create
            self.diff_attach = diff_attach
            self.diff_deploy = diff_deploy
            return

        if not self.diff_deploy:
            diff_deploy.update({'vrfNames': all_vrfs[:-1]})
        else:
            vrfs = self.diff_deploy['vrfNames'] + "," + all_vrfs[:-1]
            diff_deploy.update({'vrfNames': vrfs})

        # logit(json.dumps(diff_create, indent=4, sort_keys=True))
        # logit(json.dumps(diff_attach, indent=4, sort_keys=True))
        # logit(json.dumps(diff_deploy, indent=4, sort_keys=True))

        self.diff_create = diff_create
        self.diff_attach = diff_attach
        self.diff_deploy = diff_deploy


    def get_diff_merge(self):
        diff_create = list()
        diff_attach = list()
        diff_deploy = dict()

        all_vrfs = ""

        for want_c in self.want_create:
            found = False
            for have_c in self.have_create:
                if want_c['vrfName'] == have_c['vrfName']:
                    found = True
                    diff = self.diff_for_create(want_c, have_c)
                    if diff:
                        diff_create.append(diff)
                    break
            if not found:
                diff_create.append(want_c)

        for want_a in self.want_attach:
            dep_vrf = ''
            found = False
            for have_a in self.have_attach:
                if want_a['vrfName'] == have_a['vrfName']:

                    found = True
                    diff, vrf = self.diff_for_attach_deploy(want_a['lanAttachList'], have_a['lanAttachList'])

                    if diff:
                        base = want_a.copy()
                        del base['lanAttachList']
                        base.update({'lanAttachList': diff})
                        diff_attach.append(base)
                        dep_vrf = want_a['vrfName']
                    else:
                        if vrf:
                            dep_vrf = want_a['vrfName']

            if not found and want_a.get('lanAttachList'):
                atch_list = list()
                for attach in want_a['lanAttachList']:
                    del attach['isAttached']
                    if bool(attach['deployment']):
                        atch_list.append(attach)
                if atch_list:
                    base = want_a.copy()
                    del base['lanAttachList']
                    base.update({'lanAttachList': atch_list})
                    diff_attach.append(base)
                    dep_vrf = want_a['vrfName']

            if dep_vrf:
                all_vrfs += dep_vrf + ","

        if all_vrfs:
            diff_deploy.update({'vrfNames': all_vrfs[:-1]})

        # logit(json.dumps(diff_create, indent=4, sort_keys=True))
        # logit(json.dumps(diff_attach, indent=4, sort_keys=True))
        # logit(json.dumps(diff_deploy, indent=4, sort_keys=True))

        self.diff_create = diff_create
        self.diff_attach = diff_attach
        self.diff_deploy = diff_deploy


    def get_diff_query(self):

        query = list()

        for want_c in self.want_create:
            found_c = (next((vrf for vrf in self.have_create if vrf['vrfName'] == want_c['vrfName']), None)).copy()
            found_a = next((vrf for vrf in self.have_attach if vrf['vrfName'] == want_c['vrfName']), None)
            found_w = next((vrf for vrf in self.want_attach if vrf['vrfName'] == want_c['vrfName']), None)

            src = found_c['source']
            found_c.update({'vrf_name': found_c['vrfName']})
            found_c.update({'vrf_id': found_c['vrfId']})
            found_c.update({'vrf_template': found_c['vrfTemplate']})
            found_c.update({'vrf_extension_template': found_c['vrfExtensionTemplate']})
            del found_c['source']
            found_c.update({'source': src})
            found_c.update({'service_vrf_template': found_c['serviceVrfTemplate']})
            found_c.update({'attach': list()})

            del found_c['fabric']
            del found_c['vrfName']
            del found_c['vrfId']
            del found_c['vrfTemplate']
            del found_c['vrfExtensionTemplate']
            del found_c['serviceVrfTemplate']
            del found_c['vrfTemplateConfig']

            if  not found_w:
                query.append(found_c)
                continue

            attach_w = found_w['lanAttachList']
            attach_l = found_a['lanAttachList']

            for a_w in attach_w:
                attach_d = dict()
                serial = a_w['serialNumber']
                found = False
                for a_l in attach_l:
                    if a_l['serialNumber'] == serial:
                        found = True
                        break

                if found:
                    for k, v in self.ip_sn.items():
                        if v == a_l['serialNumber']:
                            attach_d.update({'ip_address': k})
                            break
                    attach_d.update({'vlan_id': a_l['vlan']})
                    attach_d.update({'deploy': a_l['isAttached']})
                    found_c['attach'].append(attach_d)

            if attach_d:
                query.append(found_c)

        self.query = query
        # logit(json.dumps(query, indent=4))


    def wait_for_vrf_del_ready(self):

        method = 'GET'
        if self.diff_delete:
            for vrf in self.diff_delete:
                state = False
                path = '/rest/top-down/fabrics/{}/vrfs/attachments?vrf-names={}'.format(self.fabric, vrf)
                while not state:
                    #all_vrf_attach = self.dcnm_connection(method, path)
                    resp = dcnm_send(self.module, method, path)
                    state = True
                    if resp['DATA']:
                        attach_list = resp['DATA'][0]['lanAttachList']
                        for atch in attach_list:
                            if atch['lanAttachState']  == 'OUT-OF-SYNC' or atch['lanAttachState']  == 'FAILED':
                                self.diff_delete.update({vrf: 'OUT-OF-SYNC'})
                                break
                            if atch['lanAttachState'] != 'NA':
                                self.diff_delete.update({vrf: 'DEPLOYED'})
                                state = False
                                time.sleep(5)
                                break
                            self.diff_delete.update({vrf: 'NA'})

            return True


    def validate_input(self):
        """Parse the playbook values, validate to param specs."""

        state = self.params['state']

        vrf_spec = dict(
            vrf_name=dict(required=True, type='str', length_max=32),
            vrf_id=dict(required=True, type='int', range_max=16777214),
            vrf_template=dict(required=True, type='str'),
            vrf_extension_template=dict(type='str', default='Default_Network_Universal'),
            source=dict(type='str', default='null'),
            service_vrf_template=dict(type='str', default='null'),
            attach=dict(type='list'),
            deploy=dict(type='bool')
        )
        att_spec = dict(
            ip_address=dict(required=True, type='ipv4'),
            vlan_id=dict(type='int', range_max=4094),
            deploy=dict(type='bool', default=True)
        )

        msg = ''
        if self.config:
            for vrf in self.config:
                if not 'vrf_name' in vrf or not 'vrf_id' in vrf:
                    msg = "vrf_name and vrf_id are mandatory under vrf parameters"

                if 'attach' in vrf and vrf['attach']:
                    for attach in vrf['attach']:
                        if not 'ip_address' in attach or not 'vlan_id' in attach:
                            msg =  "ip_address and vlan_id are mandatory under attach parameters"

        else:
            if state == 'merged' or state == 'overridden' or \
                    state == 'replaced' or state == 'query':
                msg =  "config: element is mandatory for this state"

        if msg:
            raise Exception(msg)

        if self.config:
            validated = []
            valid_vrf, invalid_params = validate_list_of_dicts(self.config, vrf_spec)
            for vrf in valid_vrf:
                if vrf.get('attach'):
                    valid_att, invalid_att = validate_list_of_dicts(vrf['attach'], att_spec)
                    vrf['attach'] = valid_att
                    invalid_params.extend(invalid_att)
                validated.append(vrf)

            if invalid_params:
                msg = 'Invalid parameters in playbook: {}'.format('\n'.join(invalid_params))
                raise Exception(msg)


    def handle_response(self, res, op):

        fail = False
        changed = True

        if res.get('ERROR'):
            fail = True
            changed = False
        if op == 'attach' and 'is in use already' in str(res.values()):
            fail = True
            changed = False
        if op == 'deploy' and 'No switches PENDING for deployment' in str(res.values()):
            changed = False

        return fail, changed


def main():
    """ main entry point for module execution
    """

    element_spec = dict(
        fabric=dict(required=True, type='str'),
        config=dict(required=False, type='list'),
        state=dict(default='merged',
                   choices=['merged', 'replaced', 'deleted', 'overridden', 'query'])
    )

    result = dict(
        changed=False,
        response=''
    )

    module = AnsibleModule(argument_spec=element_spec,
                           supports_check_mode=True)

    dcnm_vrf = DcnmVrf(module)

    dcnm_vrf.validate_input()

    dcnm_vrf.get_want()
    dcnm_vrf.get_have()

    if module.params['state'] == 'merged':
        dcnm_vrf.get_diff_merge()

    if module.params['state'] == 'replaced':
        dcnm_vrf.get_diff_replace()

    if module.params['state'] == 'overridden':
        dcnm_vrf.get_diff_override()

    if module.params['state'] == 'deleted':
        dcnm_vrf.get_diff_delete()

    if module.params['state'] == 'query':
        dcnm_vrf.get_diff_query()
        result['response'] = dcnm_vrf.query

    if module.check_mode:
        check_mode_results = []

        if dcnm_vrf.diff_create:
            check_mode_results.append(dcnm_vrf.diff_create)
        if dcnm_vrf.diff_attach:
            check_mode_results.append(dcnm_vrf.diff_attach)
        if dcnm_vrf.diff_deploy:
            check_mode_results.append(dcnm_vrf.diff_deploy)
        if dcnm_vrf.diff_delete:
            check_mode_results.append(dcnm_vrf.diff_delete)

        result['response'] = check_mode_results

        module.exit_json(**result)

    method = 'POST'
    path = '/rest/top-down/fabrics/{}/vrfs'.format(dcnm_vrf.fabric)
    bulk_create_path = '/rest/top-down/bulk-create/vrfs'

    if dcnm_vrf.diff_create or dcnm_vrf.diff_attach or dcnm_vrf.diff_deploy or dcnm_vrf.diff_delete:
        result['changed'] = True
    else:
        module.exit_json(**result)

    if dcnm_vrf.diff_create:
        result['response'] = dcnm_send(dcnm_vrf.module, method, bulk_create_path, json.dumps(dcnm_vrf.diff_create))
        fail, result['changed'] = dcnm_vrf.handle_response(result['response'], "create")
        if fail:
            module.fail_json(msg=result['response'])

    if dcnm_vrf.diff_attach:
        attach_path = path + '/attachments'
        result['response'] = dcnm_send(dcnm_vrf.module, method, attach_path, json.dumps(dcnm_vrf.diff_attach))
        fail, result['changed'] = dcnm_vrf.handle_response(result['response'], "attach")
        if fail:
            module.fail_json(msg=result['response'])

    if dcnm_vrf.diff_deploy:
        deploy_path = path + '/deployments'
        result['response'] = dcnm_send(dcnm_vrf.module, method, deploy_path, json.dumps(dcnm_vrf.diff_deploy))
        fail, result['changed'] = dcnm_vrf.handle_response(result['response'], "deploy")
        if fail:
            module.fail_json(msg=result['response'])

    del_failure = ''
    if dcnm_vrf.diff_delete and dcnm_vrf.wait_for_vrf_del_ready():
        method = 'DELETE'
        for vrf, state in dcnm_vrf.diff_delete.items():
            if state == 'OUT-OF-SYNC':
                del_failure += vrf + ","
                continue
            delete_path = path + "/" + vrf
            result['response'] = dcnm_send(dcnm_vrf.module, method, delete_path)
            fail, result['changed'] = dcnm_vrf.handle_response(result['response'], "delete")
            if fail:
                module.fail_json(msg=result['response'])

    if del_failure:
        result['response'] = 'Deletion of VRFs {} has failed'.format(del_failure[:-1])
        module.fail_json(msg=result['response'])

    module.exit_json(**result)


if __name__ == '__main__':
    main()
