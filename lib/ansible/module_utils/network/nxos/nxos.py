#
# This code is part of Ansible, but is an independent component.
#
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# Copyright: (c) 2017, Red Hat Inc.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import collections
import json
import re
import yaml

from ansible.module_utils._text import to_text
from ansible.module_utils.basic import env_fallback
from ansible.module_utils.network.common.utils import to_list, ComplexList
from ansible.module_utils.connection import Connection, ConnectionError
from ansible.module_utils.common._collections_compat import Mapping
from ansible.module_utils.network.common.config import NetworkConfig, dumps
from ansible.module_utils.six import iteritems, string_types
from ansible.module_utils.urls import fetch_url

_DEVICE_CONNECTION = None

nxos_provider_spec = {
    'host': dict(type='str'),
    'port': dict(type='int'),

    'username': dict(type='str', fallback=(env_fallback, ['ANSIBLE_NET_USERNAME'])),
    'password': dict(type='str', no_log=True, fallback=(env_fallback, ['ANSIBLE_NET_PASSWORD'])),
    'ssh_keyfile': dict(type='str', fallback=(env_fallback, ['ANSIBLE_NET_SSH_KEYFILE'])),

    'authorize': dict(type='bool', fallback=(env_fallback, ['ANSIBLE_NET_AUTHORIZE'])),
    'auth_pass': dict(type='str', no_log=True, fallback=(env_fallback, ['ANSIBLE_NET_AUTH_PASS'])),

    'use_ssl': dict(type='bool'),
    'use_proxy': dict(type='bool', default=True),
    'validate_certs': dict(type='bool'),

    'timeout': dict(type='int'),

    'transport': dict(type='str', default='cli', choices=['cli', 'nxapi'])
}
nxos_argument_spec = {
    'provider': dict(type='dict', options=nxos_provider_spec),
}
nxos_top_spec = {
    'host': dict(type='str', removed_in_version=2.9),
    'port': dict(type='int', removed_in_version=2.9),

    'username': dict(type='str', removed_in_version=2.9),
    'password': dict(type='str', no_log=True, removed_in_version=2.9),
    'ssh_keyfile': dict(type='str', removed_in_version=2.9),

    'authorize': dict(type='bool', fallback=(env_fallback, ['ANSIBLE_NET_AUTHORIZE'])),
    'auth_pass': dict(type='str', no_log=True, removed_in_version=2.9),

    'use_ssl': dict(type='bool', removed_in_version=2.9),
    'validate_certs': dict(type='bool', removed_in_version=2.9),
    'timeout': dict(type='int', removed_in_version=2.9),

    'transport': dict(type='str', choices=['cli', 'nxapi'], removed_in_version=2.9)
}
nxos_argument_spec.update(nxos_top_spec)


def get_provider_argspec():
    return nxos_provider_spec


def check_args(module, warnings):
    pass


def load_params(module):
    provider = module.params.get('provider') or dict()
    for key, value in iteritems(provider):
        if key in nxos_provider_spec:
            if module.params.get(key) is None and value is not None:
                module.params[key] = value


def get_connection(module):
    global _DEVICE_CONNECTION
    if not _DEVICE_CONNECTION:
        load_params(module)
        if is_local_nxapi(module):
            conn = LocalNxapi(module)
        else:
            connection_proxy = Connection(module._socket_path)
            cap = json.loads(connection_proxy.get_capabilities())
            if cap['network_api'] == 'cliconf':
                conn = Cli(module)
            elif cap['network_api'] == 'nxapi':
                conn = HttpApi(module)
        _DEVICE_CONNECTION = conn
    return _DEVICE_CONNECTION


class Cli:

    def __init__(self, module):
        self._module = module
        self._device_configs = {}
        self._connection = None

    def _get_connection(self):
        if self._connection:
            return self._connection
        self._connection = Connection(self._module._socket_path)

        return self._connection

    def get_config(self, flags=None):
        """Retrieves the current config from the device or cache
        """
        flags = [] if flags is None else flags

        cmd = 'show running-config '
        cmd += ' '.join(flags)
        cmd = cmd.strip()

        try:
            return self._device_configs[cmd]
        except KeyError:
            connection = self._get_connection()
            try:
                out = connection.get_config(flags=flags)
            except ConnectionError as exc:
                self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))

            cfg = to_text(out, errors='surrogate_then_replace').strip() + '\n'
            self._device_configs[cmd] = cfg
            return cfg

    def run_commands(self, commands, check_rc=True):
        """Run list of commands on remote device and return results
        """
        connection = self._get_connection()

        try:
            out = connection.run_commands(commands, check_rc)
            if check_rc == 'retry_json':
                capabilities = self.get_capabilities()
                network_api = capabilities.get('network_api')

                if network_api == 'cliconf' and out:
                    for index, resp in enumerate(out):
                        if ('Invalid command at' in resp or 'Ambiguous command at' in resp) and 'json' in resp:
                            if commands[index]['output'] == 'json':
                                commands[index]['output'] = 'text'
                                out = connection.run_commands(commands, check_rc)
            return out
        except ConnectionError as exc:
            self._module.fail_json(msg=to_text(exc))

    def load_config(self, config, return_error=False, opts=None, replace=None):
        """Sends configuration commands to the remote device
        """
        if opts is None:
            opts = {}

        connection = self._get_connection()
        responses = []
        try:
            resp = connection.edit_config(config, replace=replace)
            if isinstance(resp, Mapping):
                resp = resp['response']
        except ConnectionError as e:
            code = getattr(e, 'code', 1)
            message = getattr(e, 'err', e)
            err = to_text(message, errors='surrogate_then_replace')
            if opts.get('ignore_timeout') and code:
                responses.append(err)
                return responses
            elif code and 'no graceful-restart' in err:
                if 'ISSU/HA will be affected if Graceful Restart is disabled' in err:
                    msg = ['']
                    responses.extend(msg)
                    return responses
                else:
                    self._module.fail_json(msg=err)
            elif code:
                self._module.fail_json(msg=err)

        responses.extend(resp)
        return responses

    def get_diff(self, candidate=None, running=None, diff_match='line', diff_ignore_lines=None, path=None, diff_replace='line'):
        conn = self._get_connection()
        try:
            response = conn.get_diff(candidate=candidate, running=running, diff_match=diff_match, diff_ignore_lines=diff_ignore_lines, path=path,
                                     diff_replace=diff_replace)
        except ConnectionError as exc:
            self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))
        return response

    def get_capabilities(self):
        """Returns platform info of the remove device
        """
        if hasattr(self._module, '_capabilities'):
            return self._module._capabilities

        connection = self._get_connection()
        try:
            capabilities = connection.get_capabilities()
        except ConnectionError as exc:
            self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))
        self._module._capabilities = json.loads(capabilities)
        return self._module._capabilities

    def read_module_context(self, module_key):
        connection = self._get_connection()
        try:
            module_context = connection.read_module_context(module_key)
        except ConnectionError as exc:
            self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))

        return module_context

    def save_module_context(self, module_key, module_context):
        connection = self._get_connection()
        try:
            connection.save_module_context(module_key, module_context)
        except ConnectionError as exc:
            self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))

        return None


class LocalNxapi:

    OUTPUT_TO_COMMAND_TYPE = {
        'text': 'cli_show_ascii',
        'json': 'cli_show',
        'bash': 'bash',
        'config': 'cli_conf'
    }

    def __init__(self, module):
        self._module = module
        self._nxapi_auth = None
        self._device_configs = {}
        self._module_context = {}

        self._module.params['url_username'] = self._module.params['username']
        self._module.params['url_password'] = self._module.params['password']

        host = self._module.params['host']
        port = self._module.params['port']

        if self._module.params['use_ssl']:
            proto = 'https'
            port = port or 443
        else:
            proto = 'http'
            port = port or 80

        self._url = '%s://%s:%s/ins' % (proto, host, port)

    def _error(self, msg, **kwargs):
        self._nxapi_auth = None
        if 'url' not in kwargs:
            kwargs['url'] = self._url
        self._module.fail_json(msg=msg, **kwargs)

    def _request_builder(self, commands, output, version='1.0', chunk='0', sid=None):
        """Encodes a NXAPI JSON request message
        """
        try:
            command_type = self.OUTPUT_TO_COMMAND_TYPE[output]
        except KeyError:
            msg = 'invalid format, received %s, expected one of %s' % \
                (output, ','.join(self.OUTPUT_TO_COMMAND_TYPE.keys()))
            self._error(msg=msg)

        if isinstance(commands, (list, set, tuple)):
            commands = ' ;'.join(commands)

        # Order should not matter but some versions of NX-OS software fail
        # to process the payload properly if 'input' gets serialized before
        # 'type' and the payload of 'input' contains the word 'type'.
        msg = collections.OrderedDict()
        msg['version'] = version
        msg['type'] = command_type
        msg['chunk'] = chunk
        msg['sid'] = sid
        msg['input'] = commands
        msg['output_format'] = 'json'

        return dict(ins_api=msg)

    def send_request(self, commands, output='text', check_status=True,
                     return_error=False, opts=None):
        # only 10 show commands can be encoded in each request
        # messages sent to the remote device
        if opts is None:
            opts = {}
        if output != 'config':
            commands = collections.deque(to_list(commands))
            stack = list()
            requests = list()

            while commands:
                stack.append(commands.popleft())
                if len(stack) == 10:
                    body = self._request_builder(stack, output)
                    data = self._module.jsonify(body)
                    requests.append(data)
                    stack = list()

            if stack:
                body = self._request_builder(stack, output)
                data = self._module.jsonify(body)
                requests.append(data)

        else:
            body = self._request_builder(commands, 'config')
            requests = [self._module.jsonify(body)]

        headers = {'Content-Type': 'application/json'}
        result = list()
        timeout = self._module.params['timeout']
        use_proxy = self._module.params['provider']['use_proxy']

        for req in requests:
            if self._nxapi_auth:
                headers['Cookie'] = self._nxapi_auth

            response, headers = fetch_url(
                self._module, self._url, data=req, headers=headers,
                timeout=timeout, method='POST', use_proxy=use_proxy
            )
            self._nxapi_auth = headers.get('set-cookie')

            if opts.get('ignore_timeout') and re.search(r'(-1|5\d\d)', str(headers['status'])):
                result.append(headers['status'])
                return result
            elif headers['status'] != 200:
                self._error(**headers)

            try:
                response = self._module.from_json(response.read())
            except ValueError:
                self._module.fail_json(msg='unable to parse response')

            if response['ins_api'].get('outputs'):
                output = response['ins_api']['outputs']['output']
                for item in to_list(output):
                    if check_status is True and item['code'] != '200':
                        if return_error:
                            result.append(item)
                        else:
                            self._error(output=output, **item)
                    elif 'body' in item:
                        result.append(item['body'])
                    # else:
                        # error in command but since check_status is disabled
                        # silently drop it.
                        # result.append(item['msg'])

            return result

    def get_config(self, flags=None):
        """Retrieves the current config from the device or cache
        """
        flags = [] if flags is None else flags

        cmd = 'show running-config '
        cmd += ' '.join(flags)
        cmd = cmd.strip()

        try:
            return self._device_configs[cmd]
        except KeyError:
            out = self.send_request(cmd)
            cfg = str(out[0]).strip()
            self._device_configs[cmd] = cfg
            return cfg

    def run_commands(self, commands, check_rc=True):
        """Run list of commands on remote device and return results
        """
        output = None
        queue = list()
        responses = list()

        def _send(commands, output):
            return self.send_request(commands, output, check_status=check_rc)

        for item in to_list(commands):
            if is_json(item['command']):
                item['command'] = str(item['command']).rsplit('|', 1)[0]
                item['output'] = 'json'

            if all((output == 'json', item['output'] == 'text')) or all((output == 'text', item['output'] == 'json')):
                responses.extend(_send(queue, output))
                queue = list()

            output = item['output'] or 'json'
            queue.append(item['command'])

        if queue:
            responses.extend(_send(queue, output))

        return responses

    def load_config(self, commands, return_error=False, opts=None, replace=None):
        """Sends the ordered set of commands to the device
        """
        if replace:
            device_info = self.get_device_info()
            if '9K' not in device_info.get('network_os_platform', ''):
                self._module.fail_json(msg='replace is supported only on Nexus 9K devices')
            commands = 'config replace {0}'.format(replace)

        commands = to_list(commands)
        msg = self.send_request(commands, output='config', check_status=True,
                                return_error=return_error, opts=opts)
        if return_error:
            return msg
        else:
            return []

    def get_diff(self, candidate=None, running=None, diff_match='line', diff_ignore_lines=None, path=None, diff_replace='line'):
        diff = {}

        # prepare candidate configuration
        candidate_obj = NetworkConfig(indent=2)
        candidate_obj.load(candidate)

        if running and diff_match != 'none' and diff_replace != 'config':
            # running configuration
            running_obj = NetworkConfig(indent=2, contents=running, ignore_lines=diff_ignore_lines)
            configdiffobjs = candidate_obj.difference(running_obj, path=path, match=diff_match, replace=diff_replace)

        else:
            configdiffobjs = candidate_obj.items

        diff['config_diff'] = dumps(configdiffobjs, 'commands') if configdiffobjs else ''
        return diff

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'nxos'
        reply = self.run_commands({'command': 'show version', 'output': 'json'})
        data = reply[0]

        platform_reply = self.run_commands({'command': 'show inventory', 'output': 'json'})
        platform_info = platform_reply[0]

        device_info['network_os_version'] = data.get('sys_ver_str') or data.get('kickstart_ver_str')
        device_info['network_os_model'] = data['chassis_id']
        device_info['network_os_hostname'] = data['host_name']
        device_info['network_os_image'] = data.get('isan_file_name') or data.get('kick_file_name')

        if platform_info:
            inventory_table = platform_info['TABLE_inv']['ROW_inv']
            for info in inventory_table:
                if 'Chassis' in info['name']:
                    device_info['network_os_platform'] = info['productid']

        return device_info

    def get_capabilities(self):
        result = {}
        result['device_info'] = self.get_device_info()
        result['network_api'] = 'nxapi'
        return result

    def read_module_context(self, module_key):
        if self._module_context.get(module_key):
            return self._module_context[module_key]

        return None

    def save_module_context(self, module_key, module_context):
        self._module_context[module_key] = module_context

        return None


class HttpApi:
    def __init__(self, module):
        self._module = module
        self._device_configs = {}
        self._module_context = {}
        self._connection_obj = None

    @property
    def _connection(self):
        if not self._connection_obj:
            self._connection_obj = Connection(self._module._socket_path)

        return self._connection_obj

    def run_commands(self, commands, check_rc=True):
        """Runs list of commands on remote device and returns results
        """
        try:
            out = self._connection.send_request(commands)
        except ConnectionError as exc:
            if check_rc is True:
                raise
            out = to_text(exc)

        out = to_list(out)
        if not out[0]:
            return out

        for index, response in enumerate(out):
            if response[0] == '{':
                out[index] = json.loads(response)

        return out

    def get_config(self, flags=None):
        """Retrieves the current config from the device or cache
        """
        flags = [] if flags is None else flags

        cmd = 'show running-config '
        cmd += ' '.join(flags)
        cmd = cmd.strip()

        try:
            return self._device_configs[cmd]
        except KeyError:
            try:
                out = self._connection.send_request(cmd)
            except ConnectionError as exc:
                self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))

            cfg = to_text(out).strip()
            self._device_configs[cmd] = cfg
            return cfg

    def get_diff(self, candidate=None, running=None, diff_match='line', diff_ignore_lines=None, path=None, diff_replace='line'):
        diff = {}

        # prepare candidate configuration
        candidate_obj = NetworkConfig(indent=2)
        candidate_obj.load(candidate)

        if running and diff_match != 'none' and diff_replace != 'config':
            # running configuration
            running_obj = NetworkConfig(indent=2, contents=running, ignore_lines=diff_ignore_lines)
            configdiffobjs = candidate_obj.difference(running_obj, path=path, match=diff_match, replace=diff_replace)

        else:
            configdiffobjs = candidate_obj.items

        diff['config_diff'] = dumps(configdiffobjs, 'commands') if configdiffobjs else ''
        return diff

    def load_config(self, commands, return_error=False, opts=None, replace=None):
        """Sends the ordered set of commands to the device
        """
        if opts is None:
            opts = {}

        responses = []
        try:
            resp = self.edit_config(commands, replace=replace)
        except ConnectionError as exc:
            code = getattr(exc, 'code', 1)
            message = getattr(exc, 'err', exc)
            err = to_text(message, errors='surrogate_then_replace')
            if opts.get('ignore_timeout') and code:
                responses.append(code)
                return responses
            elif code and 'no graceful-restart' in err:
                if 'ISSU/HA will be affected if Graceful Restart is disabled' in err:
                    msg = ['']
                    responses.extend(msg)
                    return responses
                else:
                    self._module.fail_json(msg=err)
            elif code:
                self._module.fail_json(msg=err)

        responses.extend(resp)
        return responses

    def edit_config(self, candidate=None, commit=True, replace=None, comment=None):
        resp = list()

        self.check_edit_config_capability(candidate, commit, replace, comment)

        if replace:
            candidate = 'config replace {0}'.format(replace)

        responses = self._connection.send_request(candidate, output='config')
        for response in to_list(responses):
            if response != '{}':
                resp.append(response)
        if not resp:
            resp = ['']

        return resp

    def get_capabilities(self):
        """Returns platform info of the remove device
        """
        try:
            capabilities = self._connection.get_capabilities()
        except ConnectionError as exc:
            self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))

        return json.loads(capabilities)

    def check_edit_config_capability(self, candidate=None, commit=True, replace=None, comment=None):
        operations = self._connection.get_device_operations()

        if not candidate and not replace:
            raise ValueError("must provide a candidate or replace to load configuration")

        if commit not in (True, False):
            raise ValueError("'commit' must be a bool, got %s" % commit)

        if replace and not operations.get('supports_replace'):
            raise ValueError("configuration replace is not supported")

        if comment and not operations.get('supports_commit_comment', False):
            raise ValueError("commit comment is not supported")

    def read_module_context(self, module_key):
        try:
            module_context = self._connection.read_module_context(module_key)
        except ConnectionError as exc:
            self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))

        return module_context

    def save_module_context(self, module_key, module_context):
        try:
            self._connection.save_module_context(module_key, module_context)
        except ConnectionError as exc:
            self._module.fail_json(msg=to_text(exc, errors='surrogate_then_replace'))

        return None


class NxosCmdRef:
    """NXOS Command Reference utilities.
    The NxosCmdRef class takes a yaml-formatted string of nxos module commands
    and converts it into dict-formatted database of getters/setters/defaults
    and associated common and platform-specific values. The utility methods
    add additional data such as existing states, playbook states, and proposed cli.
    The utilities also abstract away platform differences such as different
    defaults and different command syntax.

    Callers must provide a yaml formatted string that defines each command and
    its properties; e.g. BFD global:
    ---
    _template: # _template holds common settings for all commands
      # Enable feature bfd if disabled
      feature: bfd
      # Common getter syntax for BFD commands
      get_command: show run bfd all | incl '^(no )*bfd'

    echo_rx_interval:
      kind: int
      getval: bfd echo-rx-interval (\d+)$
      setval: bfd echo-rx-interval {0}
      default: 50
      N3K:
        default: 250
    """

    def __init__(self, module, cmd_ref_str):
        """Initialize cmd_ref from yaml data."""
        self._module = module
        ref = self._ref = yaml.load(cmd_ref_str)
        # Create a list of supported commands based on ref keys
        ref['commands'] = [k for k in ref if not k.startswith('_')]
        ref['_proposed'] = []
        self.feature_enable()
        self.get_platform_defaults()


    def feature_enable(self):
        """Enable the feature if specified in ref. """
        ref = self._ref
        feature = ref['_template'].get('feature')
        if feature:
            show_cmd = "show run | incl 'feature {0}'".format(feature)
            output = self.execute_show_command(show_cmd, 'text')
            if not output or 'CLI command error' in output:
                msg = "** 'feature {0}' is not enabled. Module will auto-enable ** ".format(feature)
                self._module.warn(msg)
                ref['_proposed'].append('feature {0}'.format(feature))


    def get_platform_defaults(self):
        """Query device for platform type; update ref with platform specific defaults. """
        info = get_capabilities(self._module).get('device_info')
        os_platform = info.get('network_os_platform')
        plat = None
        if 'N3K' in os_platform:
            plat = 'N3K'

        # Update platform-specific settings for each item in ref
        ref = self._ref
        if plat:
            plat_spec_cmds = [k for k in ref['commands'] if plat in ref[k]]
            for k in plat_spec_cmds:
                for plat_key in ref[k][plat]:
                    ref[k][plat_key] = ref[k][plat][plat_key]


    def execute_show_command(self, command, format):
        """Generic show command helper.
        'CLI command error' exceptions are caught and must be handled by caller.
        Return device output as a newline-separated string or None.
        """
        cmds = [{
            'command': command,
            'output': format,
        }]
        output = None
        try:
            output = run_commands(self._module, cmds)
            if output:
                output = output[0]
        except ConnectionError as exc:
            if 'CLI command error' in repr(exc):
                # CLI may be feature disabled
                output = repr(exc)
            else:
                raise
        return output


    def get_existing(self):
        """Update ref with existing command states from the device.
        Store these states in each command's 'existing' key.
        """
        ref = self._ref
        show_cmd = ref['_template']['get_command']
        output = self.execute_show_command(show_cmd, 'text') or []
        if not output:
            return

        # Walk each cmd in ref, use cmd pattern to discover existing cmds
        output = output.split('\n')
        for k in ref['commands']:
            pattern = ref[k]['getval']
            match = [m.groups() for m in (re.search(pattern, line) for line in output) if m]
            if not match:
                continue
            if len(match) > 1:
                # TBD: Add support for multiple instances
                raise "get_existing: multiple match instances are not currently supported"

            match = list(match[0]) # tuple to list
            # Example match results for patterns that nvgen with the 'no' prefix:
            # When pattern: '(no )*foo *(\S+)*$' And:
            #  When output: 'no foo'  -> match: ['no ', None]
            #  When output: 'foo 50'  -> match: [None, '50']
            if None is match[0]:
                match.pop(0)
            elif 'no' in match[0]:
                ref[k]['no_cmd'] = True
                match.pop(0)
                if not match:
                    continue
            kind = ref[k]['kind']
            if 'int' == kind:
                ref[k]['existing'] = int(match[0])
            elif 'list' == kind:
                ref[k]['existing'] = [str(i) for i in match]
            elif 'str' == kind:
                ref[k]['existing'] = match[0]
            else:
                raise "get_existing: unknown 'kind' value specified for key '{0}'".format(k)



    def get_playvals(self):
        """Update ref with values from the playbook.
        Store these values in each command's 'playval' key.
        """
        ref = self._ref
        module = self._module
        for k in ref.keys():
            if k in module.params and module.params[k] is not None:
                playval = module.params[k]
                if 'int' == ref[k]['kind']:
                    playval = int(playval)
                elif 'list' == ref[k]['kind']:
                    playval = [str(i) for i in playval]
                ref[k]['playval'] = playval


    def get_proposed(self):
        """Compare playbook values against existing states and create a list
        of proposed commands.
        Return a list of raw cli command strings.
        """
        ref = self._ref
        # '_proposed' may be empty list or contain initializations; e.g. ['feature foo']
        proposed = ref['_proposed']
        # Create a list of commands that have playbook values
        play_keys = [k for k in ref['commands'] if 'playval' in ref[k]]

        # Compare against current state
        for k in play_keys:
            playval = ref[k]['playval']
            existing = ref[k].get('existing', ref[k]['default'])
            if playval == existing:
                continue
            cmd = None
            kind = ref[k]['kind']
            if 'int' == kind:
                cmd = ref[k]['setval'].format(playval)
            elif 'list' == kind:
                cmd = ref[k]['setval'].format(*(playval))
            elif 'str' == kind:
                if playval:
                    cmd = ref[k]['setval'].format('', playval)
                elif existing:
                    cmd = ref[k]['setval'].format('no ', existing)
            else:
                raise "get_proposed: unknown 'kind' value specified for key '{0}'".format(k)
            if cmd:
                proposed.append(cmd)

        return proposed


def is_json(cmd):
    return to_text(cmd).endswith('| json')


def is_text(cmd):
    return not is_json(cmd)


def is_local_nxapi(module):
    transport = module.params['transport']
    provider_transport = (module.params['provider'] or {}).get('transport')
    return 'nxapi' in (transport, provider_transport)


def to_command(module, commands):
    if is_local_nxapi(module):
        default_output = 'json'
    else:
        default_output = 'text'

    transform = ComplexList(dict(
        command=dict(key=True),
        output=dict(default=default_output),
        prompt=dict(type='list'),
        answer=dict(type='list'),
        newline=dict(type='bool', default=True),
        sendonly=dict(type='bool', default=False),
        check_all=dict(type='bool', default=False),
    ), module)

    commands = transform(to_list(commands))

    for item in commands:
        if is_json(item['command']):
            item['output'] = 'json'

    return commands


def get_config(module, flags=None):
    flags = [] if flags is None else flags

    conn = get_connection(module)
    return conn.get_config(flags=flags)


def run_commands(module, commands, check_rc=True):
    conn = get_connection(module)
    return conn.run_commands(to_command(module, commands), check_rc)


def load_config(module, config, return_error=False, opts=None, replace=None):
    conn = get_connection(module)
    return conn.load_config(config, return_error, opts, replace=replace)


def get_capabilities(module):
    conn = get_connection(module)
    return conn.get_capabilities()


def get_diff(self, candidate=None, running=None, diff_match='line', diff_ignore_lines=None, path=None, diff_replace='line'):
    conn = self.get_connection()
    return conn.get_diff(candidate=candidate, running=running, diff_match=diff_match, diff_ignore_lines=diff_ignore_lines, path=path, diff_replace=diff_replace)


def normalize_interface(name):
    """Return the normalized interface name
    """
    if not name:
        return

    def _get_number(name):
        digits = ''
        for char in name:
            if char.isdigit() or char in '/.':
                digits += char
        return digits

    if name.lower().startswith('et'):
        if_type = 'Ethernet'
    elif name.lower().startswith('vl'):
        if_type = 'Vlan'
    elif name.lower().startswith('lo'):
        if_type = 'loopback'
    elif name.lower().startswith('po'):
        if_type = 'port-channel'
    elif name.lower().startswith('nv'):
        if_type = 'nve'
    else:
        if_type = None

    number_list = name.split(' ')
    if len(number_list) == 2:
        number = number_list[-1].strip()
    else:
        number = _get_number(name)

    if if_type:
        proper_interface = if_type + number
    else:
        proper_interface = name

    return proper_interface


def get_interface_type(interface):
    """Gets the type of interface
    """
    if interface.upper().startswith('ET'):
        return 'ethernet'
    elif interface.upper().startswith('VL'):
        return 'svi'
    elif interface.upper().startswith('LO'):
        return 'loopback'
    elif interface.upper().startswith('MG'):
        return 'management'
    elif interface.upper().startswith('MA'):
        return 'management'
    elif interface.upper().startswith('PO'):
        return 'portchannel'
    elif interface.upper().startswith('NV'):
        return 'nve'
    else:
        return 'unknown'


def read_module_context(module):
    conn = get_connection(module)
    return conn.read_module_context(module._name)


def save_module_context(module, module_context):
    conn = get_connection(module)
    return conn.save_module_context(module._name, module_context)
