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

from ansible.module_utils.connection import Connection


def get_fabric_inventory_details(module, fabric):
    method = 'GET'
    path = '/rest/control/fabrics/{}/inventory'.format(fabric)

    ip_sn = dict()
    response = dcnm_send(module, method, path)

    if response.get('RETURN_CODE') == 404:
        # RC 404 - Object not found
        return ip_sn
    if response.get('RETURN_CODE') >= 400:
        # Handle additional return codes as needed but for now raise
        # for any error other then 404.
        raise Exception(response)

    for device in response.get('DATA'):
        ip = device.get('ipAddress')
        sn = device.get('serialNumber')
        ip_sn.update({ip: sn})

    return ip_sn


def dcnm_send(module, method, path, json_data=None):

    conn = Connection(module._socket_path)
    return conn.send_request(method, path, json_data)
