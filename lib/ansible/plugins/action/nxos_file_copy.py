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
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import copy
import hashlib
import os
import re
import sys
import time
import traceback
import uuid

from ansible.errors import AnsibleError
from ansible.module_utils._text import to_text, to_bytes
from ansible.module_utils.connection import Connection
from ansible.plugins.action import ActionBase
from ansible.module_utils.six.moves.urllib.parse import urlsplit
from ansible.utils.display import Display

# From nxos module
from ansible.module_utils.compat.paramiko import paramiko
from ansible.module_utils.network.nxos.nxos import run_commands
from ansible.module_utils._text import to_native, to_text, to_bytes
from ansible.module_utils.basic import AnsibleModule


try:
    from scp import SCPClient
    HAS_SCP = True
except ImportError:
    HAS_SCP = False

try:
    import pexpect
    HAS_PEXPECT = True
except ImportError:
    HAS_PEXPECT = False

display = Display()


class ActionModule(ActionBase):

    def process_playbook_values(self):
        ''' Get playbook values and perform input validation '''
        argument_spec = dict(
            vrf=dict(type='str', default='management'),
            connect_ssh_port=dict(type='int', default=22),
            file_system=dict(type='str', default='bootflash:'),
            file_pull=dict(type='bool', default=False),
            file_pull_timeout=dict(type='int', default=300),
            local_file=dict(type='str'),
            local_file_directory=dict(type='str'),
            remote_file=dict(type='str'),
            remote_scp_server=dict(type='str'),
            remote_scp_server_user=dict(type='str'),
            remote_scp_server_password=dict(no_log=True),
        )

        playvals = {}
        # Process key value pairs from playbook task
        for key in argument_spec.keys():
            playvals[key] = self._task.args.get(key, argument_spec[key].get('default'))
            if playvals[key] is None:
                continue
            if argument_spec[key].get('type') is None:
                argument_spec[key]['type'] = 'str'
            type_ok = False
            type = argument_spec[key]['type']
            if type == 'str':
                if isinstance(playvals[key], str) or isinstance(playvals[key], unicode):
                    type_ok = True
            elif type == 'int':
                if isinstance(playvals[key], int):
                    type_ok = True
            elif type == 'bool':
                if isinstance(playvals[key], bool):
                    type_ok = True
            else:
                raise AnsibleError('Unrecognized type <{0}> for playbook parameter <{1}>'.format(type, key))

            if not type_ok:
                raise AnsibleError('Playbook parameter <{0}> value should be of type <{1}>'.format(key, type))

        # Validate playbook dependencies
        if playvals['file_pull']:
            if playvals.get('remote_file') is None:
                raise AnsibleError('Playbook parameter <remote_file> required when <file_pull> is True')
            if playvals.get('remote_scp_server') is None:
                raise AnsibleError('Playbook parameter <remote_scp_server> required when <file_pull> is True')

        if playvals['remote_scp_server'] or \
           playvals['remote_scp_server_user'] or \
           playvals['remote_scp_server_password']:

            if None in (playvals['remote_scp_server'],
                        playvals['remote_scp_server_user'],
                        playvals['remote_scp_server_password']):
                params = '<remote_scp_server>, <remote_scp_server_user>, ,remote_scp_server_password>'
                raise AnsibleError('Playbook parameters {0} must all be set together'.format(params))

        return playvals

    def check_library_dependencies(self, file_pull):
        if file_pull:
            if not HAS_PEXPECT:
                msg = 'library pexpect is required when file_pull is True but does not appear to be '
                msg += 'installed. It can be installed using `pip install pexpect`'
                raise AnsibleError(msg)
        else:
            if paramiko is None:
                msg = 'library paramiko is required when file_pull is False but does not appear to be '
                msg += 'installed. It can be installed using `pip install paramiko`'
                raise AnsibleError(msg)

            if not HAS_SCP:
                msg = 'library scp is required when file_pull is False but does not appear to be '
                msg += 'installed. It can be installed using `pip install scp`'
                raise AnsibleError(msg)

    def md5sum_check(self, dst, file_system):
        command = 'show file {0}{1} md5sum'.format(file_system, dst)
        remote_filehash = self.conn.exec_command(command)
        remote_filehash = to_bytes(remote_filehash, errors='surrogate_or_strict')

        local_file = self.playvals['local_file']
        try:
            with open(local_file, 'rb') as f:
                filecontent = f.read()
        except (OSError, IOError) as exc:
            raise AnsibleError('Error reading the file: {0}'.format(to_text(exc)))

        filecontent = to_bytes(filecontent, errors='surrogate_or_strict')
        local_filehash = hashlib.md5(filecontent).hexdigest()

        if local_filehash == remote_filehash:
            return True
        else:
            return False

    def remote_file_exists(self, remote_file, file_system):
        command = 'dir {0}/{1}'.format(file_system, remote_file)
        body = self.conn.exec_command(command)
        if 'No such file' in body:
            return False
        else:
            return self.md5sum_check(remote_file, file_system)

    def verify_remote_file_exists(self, dst, file_system):
        command = 'dir {0}/{1}'.format(file_system, dst)
        body = self.conn.exec_command(command)
        if 'No such file' in body:
            return 0
        return body.split()[0].strip()

    def local_file_exists(self, file):
        return os.path.isfile(file)

    def get_flash_size(self, file_system):
        command = 'dir {0}'.format(file_system)
        body = self.conn.exec_command(command)

        match = re.search(r'(\d+) bytes free', body)
        bytes_free = match.group(1)

        return int(bytes_free)

    def enough_space(self, file, file_system):
        flash_size = self.get_flash_size(file_system)
        file_size = os.path.getsize(file)
        if file_size > flash_size:
            return False

        return True

    def transfer_file_to_device(self, remote_file):
        timeout = self.socket_timeout
        local_file = self.playvals['local_file']
        file_system = self.playvals['file_system']
        file_size = os.path.getsize(local_file)

        if not self.enough_space(local_file, file_system):
            raise AnsibleError('Could not transfer file. Not enough space on device.')

        # frp = full_remote_path, flp = full_local_path
        frp = '{0}{1}'.format(file_system, remote_file)
        flp = os.path.join(os.path.abspath(local_file))
        try:
            self.conn.copy_file(source=flp, destination=frp, proto='scp', timeout=timeout)
        except Exception as exc:
            self.results['failed'] = True
            self.results['msg'] = ('Exception received : %s' % exc)

    def file_push(self):
        local_file = self.playvals['local_file']
        remote_file = self.playvals['remote_file'] or os.path.basename(local_file)
        file_system = self.playvals['file_system']

        if not self.local_file_exists(local_file):
            raise AnsibleError('Local file {0} not found'.format(local_file))

        remote_file = remote_file or os.path.basename(local_file)
        remote_exists = self.remote_file_exists(remote_file, file_system)

        if not remote_exists:
            self.results['changed'] = True
            file_exists = False
        else:
            self.results['transfer_status'] = 'No Transfer: File already copied to remote device.'
            file_exists = True

        if not self.play_context.check_mode and not file_exists:
            self.transfer_file_to_device(remote_file)
            self.results['transfer_status'] = 'Sent: File copied to remote device.'

        self.results['local_file'] = local_file
        if remote_file is None:
            remote_file = os.path.basename(local_file)
        self.results['remote_file'] = remote_file

    def copy_file_from_remote(self, local, local_file_directory, file_system):
        nxos_hostname = self.play_context.remote_addr
        nxos_username = self.play_context.remote_user
        nxos_password = self.play_context.password
        port = self.playvals['connect_ssh_port']

        # Build copy command components that will be used to initiate copy from the nxos device.
        cmdroot = 'copy scp://'
        ruser = self.playvals['remote_scp_server_user'] + '@'
        rserver = self.playvals['remote_scp_server']
        rfile = self.playvals['remote_file'] + ' '
        vrf = ' vrf ' + self.playvals['vrf']
        local_dir_root = '/'

        def process_outcomes(session, timeout=None):
            if timeout is None:
                timeout = 10
            outcome = {}
            outcome['user_response_required'] = False
            outcome['password_prompt_detected'] = False
            outcome['existing_file_with_same_name'] = False
            outcome['final_prompt_detected'] = False

            # Possible outcomes key:
            # 0) - Are you sure you want to continue connecting (yes/no)
            # 1) - Password: or @servers's password:
            # 2) - nxos_router_prompt#
            # 3) - Warning: There is already a file existing with this name. Do you want to overwrite (y/n)?[n]
            possible_outcomes = ['yes', '(?i)Password', '#\s', 'existing', 'timed out',
                                 '(?i)No space', '(?i)Permission denied', '(?i)No such file',
                                 pexpect.TIMEOUT]
            index = session.expect(possible_outcomes, timeout=timeout)
            # Each index maps to items in possible_outcomes
            if index == 0:
                outcome['user_response_required'] = True
                return outcome
            elif index == 1:
                outcome['password_prompt_detected'] = True
                return outcome
            elif index == 2:
                outcome['final_prompt_detected'] = True
                return outcome
            elif index == 3:
                outcome['existing_file_with_same_name'] = True
                return outcome
            elif index == 4:
                raise AnsibleError('Timeout occured. Remote scp server {0} not responding.'.format(rserver))
            elif index == 5:
                raise AnsibleError('File copy failed. No space left on the nxos file system {0}.'.format(file_system))
            elif index == 6:
                msg = 'Incorrect username/password for remote scp server {0} '
                msg += 'or Incorrect file permisions for remote file {1}'
                raise AnsibleError(msg.format(rserver, rfile))
            elif index == 7:
                raise AnsibleError('File copy failed. File {0} not found on remote scp server {1}'.format(rfile, file_system))
            elif index == 8:
                # The before property will contain all text up to the expected string pattern.
                # The after string will contain the text that was matched by the expected pattern.
                msg = 'Timeout error occured: BEFORE {0} AFTER {1}'.format(session.before, session.after)
                raise AnsibleError(msg)
            else:
                msg = 'Unrecognized error occured: BEFORE {0} AFTER {1}'.format(session.before, session.after)
                raise AnsibleError(msg)

            return outcome

        # Spawn pexpect connection to NX-OS device.
        nxos_session = pexpect.spawn('ssh ' + nxos_username + '@' + nxos_hostname + ' -p' + str(port))
        # There might be multiple user_response_required prompts so loop up to
        # 5 times during the connection process.
        for connect_attempt in range(30):
            outcome = process_outcomes(nxos_session)
            if outcome['user_response_required']:
                nxos_session.sendline('yes')
                continue
            if outcome['password_prompt_detected']:
                nxos_session.sendline(nxos_password)
                continue
            if outcome['final_prompt_detected']:
                break
        else:
            # The before property will contain all text up to the expected string pattern.
            # The after string will contain the text that was matched by the expected pattern.
            msg = 'After {0} attempts, failed to spawn pexpect session to {1}'
            msg += 'BEFORE: {2}, AFTER: {3}'
            raise AnsibleError(msg.format(connect_attempt, nxos_hostname, nxos_session.before, nxos_session.before))

        # Create local file directory under NX-OS filesystem if
        # local_file_directory playbook parameter is set.
        if local_file_directory:
            dir_array = local_file_directory.split('/')
            for each in dir_array:
                if each:
                    nxos_session.sendline('mkdir ' + local_dir_root + each)
                    process_outcomes(nxos_session)
                    local_dir_root += each + '/'

        # Initiate file copy
        copy_cmd = (cmdroot + ruser + rserver + rfile + file_system + local_dir_root + local + vrf)
        nxos_session.sendline(copy_cmd)
        for copy_attempt in range(6):
            outcome = process_outcomes(nxos_session, self.playvals['file_pull_timeout'])
            if outcome['user_response_required']:
                nxos_session.sendline('yes')
                continue
            if outcome['password_prompt_detected']:
                nxos_session.sendline(self.playvals['remote_scp_server_password'])
                continue
            if outcome['existing_file_with_same_name']:
                nxos_session.sendline('y')
                continue
            if outcome['final_prompt_detected']:
                break
        else:
            # The before property will contain all text up to the expected string pattern.
            # The after string will contain the text that was matched by the expected pattern.
            msg = 'After {0} attempts, failed to copy file to {1}'
            msg += 'BEFORE: {2}, AFTER: {3}'
            raise AnsibleError(msg.format(copy_attempt, nxos_hostname, nxos_session.before, nxos_session.before))
        nxos_session.close()

    def file_pull(self):
        local_file = self.playvals['local_file']
        remote_file = self.playvals['remote_file']
        file_system = self.playvals['file_system']
        # Note: This is the local file directory on the remote nxos device.
        local_file_dir = self.playvals['local_file_directory']

        local_file = local_file or self.playvals['remote_file'].split('/')[-1]

        if not self.play_context.check_mode:
            self.copy_file_from_remote(local_file, local_file_dir, file_system)
            self.results['transfer_status'] = 'Received: File copied/pulled to nxos device from remote scp server.'

        self.results['changed'] = True
        self.results['remote_file'] = remote_file
        if local_file_dir:
            dir = local_file_dir
        else:
            dir = ''
        self.results['local_file'] = file_system + dir + '/' + local_file
        self.results['remote_scp_server'] = self.playvals['remote_scp_server']

    # This is the main run method for the action plugin to copy files
    def run(self, tmp=None, task_vars=None):
        socket_path = None
        self.play_context = copy.deepcopy(self._play_context)
        self.results = super(ActionModule, self).run(task_vars=task_vars)

        if self.play_context.connection != 'network_cli':
            # Plugin is supported only with network_cli
            self.results['failed'] = True
            self.results['msg'] = ('Connection type must be <network_cli>')
            return self.results

        # Get playbook values
        self.playvals = self.process_playbook_values()

        file_pull = self.playvals['file_pull']
        self.check_library_dependencies(file_pull)

        if socket_path is None:
            socket_path = self._connection.socket_path
        self.conn = Connection(socket_path)
        self.socket_timeout = self.conn.get_option('persistent_command_timeout')

        # This action plugin support two modes of operation.
        # - file_pull is False - Push files from the ansible controller to nxos switch.
        # - file_pull is True - Initiate copy from the device to pull files to the nxos switch.
        self.results['transfer_status'] = 'No Transfer'
        self.results['file_system'] = self.playvals['file_system']
        if file_pull:
            self.file_pull()
        else:
            self.file_push()

        return self.results
