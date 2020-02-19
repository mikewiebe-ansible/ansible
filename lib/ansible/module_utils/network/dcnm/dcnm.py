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


def dcnm_connection(module, method, path, json_data=None):

    conn = Connection(module._socket_path)
    return conn.send_request(method, path, json_data)