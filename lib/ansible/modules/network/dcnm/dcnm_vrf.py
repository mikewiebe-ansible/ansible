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

import json, socket
from ansible.module_utils.common.validation import check_type_int, check_type_str
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
import datetime
def logit(msg):
    with open('/tmp/alog.txt', 'a') as of:
        d = datetime.datetime.now().replace(microsecond=0).isoformat()
        of.write("---- %s ----\n%s\n" % (d,msg))


def get_fabric_inventory_details(module, fabric):
    method = 'GET'
    path = '/rest/control/fabrics/{}/inventory'.format(fabric)

    all_ip_serial = dict()
    response = dcnm_connection(module, method, path)

    if response and isinstance(response, list):
        if response[0].get('ERROR') == 'Not Found' and \
                response[0].get('RETURN_CODE') == 404:
                return {}

    for device in response:
        ip_addr = device.get('ipAddress')
        serial_number = device.get('serialNumber')
        all_ip_serial.update({ip_addr: serial_number})

    return all_ip_serial


def diff_for_attach_deploy(want_a, have_a):

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

    #logit(json.dumps(attach_list, indent=4, sort_keys=True))
    return attach_list, dep_vrf


def update_attach_params(attach, vrf_name, ip_serial, fabric, deploy):

    serial = ""
    for ip, ser in ip_serial.items():
        if ip == attach['ip_address']:
            serial = ser

    if attach:
        attach.update({'fabric': fabric})
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


def diff_for_create(want, have):
    create = dict()
    if not have:
        create = want
    else:
        if have['vrfId'] != want['vrfId']: # Was thinking of moving it out, try to remember why...
            logit("diff_for_create - VRF ID cant be updated to a different value")
            pass
            #module.exit_json("Can not update the VRF ID") # need to find a proper way to err
        elif have['serviceVrfTemplate'] != want['serviceVrfTemplate'] or \
             have['source'] != want['source'] or \
             have['vrfTemplate'] != want['vrfTemplate'] or \
             have['vrfExtensionTemplate'] != want['vrfExtensionTemplate']:
            create = want
        else:
            pass

    return create

def update_create_params(create, fabric):

    if not create:
        return create

    v_template = 'Default_VRF_Universal' if not create.get('vrf_template') else create['vrf_template']
    ve_template = 'Default_VRF_Extension_Universal' if not create.get('vrf_extension_template') \
        else create['vrf_extension_template']
    src = None if not create.get('source') else create['source']
    s_v_template = None if not create.get('service_vrf_template') else create['service_vrf_template']


    create_upd = dict()
    create_upd.update({'fabric': fabric})
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


def dcnm_connection(module, method, path, json_data=None):

    conn = Connection(module._socket_path)
    return conn.send_request(method, path, json_data)


def get_have(facts, module):
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


    fabric = facts.get('params')['fabric']
    method = 'GET'
    path = '/rest/top-down/fabrics/{}/vrfs'.format(fabric)

    resp = dcnm_connection(module, method, path)

    if resp and isinstance(resp, list):
        if resp[0].get('ERROR') == 'Not Found' and resp[0].get('RETURN_CODE') == 404:
                logit("Fabric not found")
                return have_create, have_attach, have_deploy

    if not resp:
        return have_create, have_attach, have_deploy

    for vrf in resp:
        all_vrfs += vrf['vrfName'] + ','

    path = '/rest/top-down/fabrics/{}/vrfs/attachments?vrf-names={}'.format(fabric, all_vrfs[:-1])

    all_vrf_attach = dcnm_connection(module, method, path)

    for vrf in resp:
        t_conf = dict()
        t_conf.update({'vrfSegmentId': vrf['vrfId']})
        t_conf.update({'vrfName': vrf['vrfName']})

        vrf.update({'vrfTemplateConfig': json.dumps(t_conf)})
        del vrf['vrfStatus']
        have_create.append(vrf)

    all_vrfs = ''

    for vrf_attach in all_vrf_attach:
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

            attach.update({'fabric': fabric})
            attach.update({'vlan': vlan})
            attach.update({'serialNumber': sn})
            attach.update({'deployment': deploy})
            attach.update({'extensionValues': ""})
            attach.update({'instanceValues': ""})
            attach.update({'freeformConfig': ""})
            attach.update({'isAttached': attach_state})

        if dep_vrf:
            all_vrfs += dep_vrf + ","

    have_attach = all_vrf_attach

    if all_vrfs:
        have_deploy.update({'vrfNames': all_vrfs[:-1]})

    # logit(json.dumps(have_create, indent=4, sort_keys=True))
    # logit(json.dumps(have_attach, indent=4, sort_keys=True))
    # logit(json.dumps(have_deploy, indent=4, sort_keys=True))

    return have_create, have_attach, have_deploy


def get_want(facts, ip_sn):
    want_create = list()
    want_attach = list()
    want_deploy = dict()

    all_vrfs = ""

    if not facts['params'].get('config'):
        return want_create, want_attach, want_deploy

    fabric = facts.get('params')['fabric']
    config = facts.get('params')['config']

    for vrf in config:
        vrf_attach = dict()
        vrfs = list()

        vrf_deploy = True
        if "deploy" in vrf:
            vrf_deploy = vrf['deploy']

        want_create.append(update_create_params(vrf, fabric))

        if not vrf.get('attach'):
            continue
        for attach in vrf['attach']:
            deploy = vrf_deploy if "deploy" not in attach else attach['deploy']
            vrfs.append(update_attach_params(attach,
                                             vrf['vrf_name'],
                                             ip_sn,
                                             fabric,
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

    return want_create, want_attach, want_deploy


def get_diff_override(facts):
    # overridden:
    # DCNM should reflect exactly like the play.
    # The vrfs and their attachments not present in the play should be removed from DCNM if present there.
    # The vrfs and their attachments present in the play should replace whats there on DCNM if present there

    all_vrfs = ''
    want_create = facts['want_create']
    have_attach = facts['have_attach']
    diff_delete = list()

    diff_create, diff_attach, diff_deploy = get_diff_replace(facts)

    for have_a in have_attach:
        found = next((vrf for vrf in want_create if vrf['vrfName'] == have_a['vrfName']), None)

        to_del = list()
        if not found:
            atch_h = have_a['lanAttachList']
            for a_h in atch_h:
                if a_h['isAttached']:
                    del a_h['isAttached']
                    a_h.update({'deployment': False})
                    to_del.append(a_h)

            if to_del:
                have_a.update({'lanAttachList':to_del})
                diff_attach.append(have_a)
                all_vrfs += have_a['vrfName'] + ","

            diff_delete.append(have_a['vrfName'])

    if all_vrfs:
        vrfs = (diff_deploy['vrfNames'] + "," + all_vrfs[:-1]) if diff_deploy else all_vrfs[:-1]
        diff_deploy.update({'vrfNames': vrfs})

    logit(json.dumps(diff_create, indent=4, sort_keys=True))
    logit(json.dumps(diff_attach, indent=4, sort_keys=True))
    logit(json.dumps(diff_deploy, indent=4, sort_keys=True))
    logit(json.dumps(diff_delete, indent=4, sort_keys=True))

    return diff_create, diff_attach, diff_deploy, diff_delete


def get_diff_replace(facts):
    all_vrfs = ''
    diff_create, diff_attach, diff_deploy = get_diff_merge(facts)

    want_create = facts['want_create']
    want_attach = facts['want_attach']
    have_attach = facts['have_attach']

    for have_a in have_attach:
        r_vrf_list = list()
        h_in_w = False
        for want_a in want_attach:
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
            found = next((vrf for vrf in want_create if vrf['vrfName'] == have_a['vrfName']), None)
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
            for d_attach in diff_attach:
                if have_a['vrfName'] == d_attach['vrfName']:
                    in_diff = True
                    d_attach['lanAttachList'].extend(r_vrf_list)
                    break

            if not in_diff:
                r_vrf_dict = dict()
                r_vrf_dict.update({'vrfName':have_a['vrfName']})
                r_vrf_dict.update({'lanAttachList': r_vrf_list})
                diff_attach.append(r_vrf_dict)
                all_vrfs += have_a['vrfName'] + ","

    if not all_vrfs:
        # logit(json.dumps(diff_create, indent=4, sort_keys=True))
        # logit(json.dumps(diff_attach, indent=4, sort_keys=True))
        # logit(json.dumps(diff_deploy, indent=4, sort_keys=True))
        return diff_create, diff_attach, diff_deploy

    if not diff_deploy:
        diff_deploy.update({'vrfNames': all_vrfs[:-1]})
    else:
        vrfs = diff_deploy['vrfNames'] + "," + all_vrfs[:-1]
        diff_deploy.update({'vrfNames': vrfs})

    # logit(json.dumps(diff_create, indent=4, sort_keys=True))
    # logit(json.dumps(diff_attach, indent=4, sort_keys=True))
    # logit(json.dumps(diff_deploy, indent=4, sort_keys=True))

    return diff_create, diff_attach, diff_deploy


def get_diff_merge(facts):
    diff_create = list()
    diff_attach = list()
    diff_deploy = dict()

    all_vrfs = ""

    want_create = facts['want_create']
    have_create = facts['have_create']

    for want_c in want_create:
        found = False
        for have_c in have_create:
            if want_c['vrfName'] == have_c['vrfName']:
                found = True
                diff = diff_for_create(want_c, have_c)
                if diff:
                    diff_create.append(diff)
                break
        if not found:
            diff_create.append(want_c)

    want_attach = facts['want_attach']
    have_attach = facts['have_attach']

    for want_a in want_attach:
        dep_vrf = ''
        found = False
        for have_a in have_attach:
            if want_a['vrfName'] == have_a['vrfName']:

                found = True
                diff, vrf = diff_for_attach_deploy(want_a['lanAttachList'], have_a['lanAttachList'])

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

    return diff_create, diff_attach, diff_deploy


def get_diff_delete(facts):
    diff_create = list()
    diff_attach = list()
    diff_deploy = dict()
    pass


def get_diff_query(facts):
    diff_create = list()
    diff_attach = list()
    diff_deploy = dict()
    pass


def handle_response(res, op):

    fail = False
    changed = True

    if res and isinstance(res, list):
        if res[0].get('ERROR'):
            fail = True
            changed = False

    if res and isinstance(res, dict):
        if op == 'attach' and 'is in use already' in str(res.values()):
            fail = True
            changed = False
        if op == 'deploy' and 'No switches PENDING for deployment' in str(res.values()):
            changed = False

    return fail, changed

### Common utils

def validate_ipv4_addr(address):
    address = address.split('/')[0]
    try:
        socket.inet_aton(address)
    except socket.error:
        return False
    return address.count('.') == 3

def validate_vlan_id(value):
    if value and not 1 <= value <= 4094:
        return False
    return True

def validate_vrf_id(value):
    if value and check_type_int(value) and not 1 <= value <= 16777214:
        return False
    return True

def validate_vrf(name):
    if not check_type_str(name):
        return False
    if name:
        name = name.strip()
        if len(name) > 32:
            return False
    return True

###


def validate_input(params):

    state = params['state']

    err_m = ''
    ret_c = True

    if params.get('config'):
        for vrf in params['config']:
            if not 'vrf_name' in vrf or not 'vrf_id' in vrf:
                return "vrf_name and vrf_id are mandatory under vrf parameters", False

            if not validate_vrf_id(vrf['vrf_id']):
                return "vrf_id must be in the range of 1 and 16777214", False

            if not validate_vrf(vrf['vrf_name']):
                return "VRF name should not exceed length of 32", False

            if 'attach' in vrf:
                for attach in vrf['attach']:
                    if not 'ip_address' in attach or not 'vlan_id' in attach:
                        return "ip_address and vlan_id are mandatory under attach parameters", False
                    if not validate_ipv4_addr(attach['ip_address']):
                        return "ip_address is in incorrect format", False
                    if not validate_vlan_id(attach['vlan_id']):
                        return "vlan_id must be in the range of 1 and 4094", False

    else:
        if state == 'merged' or state == 'overridden' or \
            state == 'replaced' or state == 'query':
            return "config: element is mandatory for this state", False

    return err_m, ret_c


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
        response=dict()
    )

    module = AnsibleModule(argument_spec=element_spec,
                           supports_check_mode=True)

    err,ret = validate_input(module.params)

    if not ret:
        module.fail_json(msg=err)

    facts = {
        'params': module.params,
        'check_mode': False,
        'conn': Connection(module._socket_path),
        'have_create': [],
        'want_create': [],
        'diff_create': [],
        'have_attach': [],
        'want_attach': [],
        'diff_attach': [],
        'have_deploy': {},
        'want_deploy': {},
        'diff_deploy': {},
        'diff_delete': []
    }

    ip_sn = get_fabric_inventory_details(module, module.params['fabric'])
    if not ip_sn:
        module.fail_json(msg="Non-existent fabric or no devices in the fabric yet")

    want_create, want_attach, want_deploy = get_want(facts, ip_sn)
    have_create, have_attach, have_deploy = get_have(facts, module)

    facts.update({'want_create': want_create})
    facts.update({'want_attach': want_attach})
    facts.update({'want_deploy': want_deploy})
    facts.update({'have_create': have_create})
    facts.update({'have_attach': have_attach})
    facts.update({'have_deploy': have_deploy})

    if module.params['state'] == 'merged':
        diff_create, diff_attach, diff_deploy = get_diff_merge(facts)

    if module.params['state'] == 'replaced':
        diff_create, diff_attach, diff_deploy = get_diff_replace(facts)

    if module.params['state'] == 'overridden':
        diff_create, diff_attach, diff_deploy, diff_delete = get_diff_override(facts)

    facts.update({'diff_create': diff_create})
    facts.update({'diff_attach': diff_attach})
    facts.update({'diff_deploy': diff_deploy})
    facts.update({'diff_delete': diff_delete})

    fabric = module.params['fabric']

    method = 'POST'
    path = '/rest/top-down/fabrics/{}/vrfs'.format(fabric)
    bulk_create_path = '/rest/top-down/bulk-create/vrfs'

    if facts['diff_create'] or facts['diff_attach'] or facts['diff_deploy']:
        result['changed'] = True
    else:
        module.exit_json(**result)

    if facts['diff_create']:
        result['response'] = dcnm_connection(module, method, bulk_create_path, json.dumps(facts['diff_create']))
        fail, result['changed'] = handle_response(result['response'], "create")
        if fail:
            module.fail_json(msg=result['response'])
    if facts['diff_attach']:
        attach_path = path + '/attachments'
        result['response'] = dcnm_connection(module, method, attach_path, json.dumps(facts['diff_attach']))
        fail, result['changed'] = handle_response(result['response'], "attach")
        if fail:
            module.fail_json(msg=result['response'])
    if facts['diff_deploy']:
        deploy_path = path + '/deployments'
        result['response'] = dcnm_connection(module, method, deploy_path, json.dumps(facts['diff_deploy']))
        fail, result['changed'] = handle_response(result['response'], "deploy")
        if fail:
            module.fail_json(msg=result['response'])
    if facts['diff_delete']:
        method = 'DELETE'
        logit("HERE........")
        for vrf in facts['diff_delete']:
            logit("HERE........1")
            delete_path = path + "/" + vrf
            result['response'] = dcnm_connection(module, method, delete_path)
            fail, result['changed'] = handle_response(result['response'], "delete")
            if fail:
                module.fail_json(msg=result['response'])

    module.exit_json(**result)


if __name__ == '__main__':
    main()
