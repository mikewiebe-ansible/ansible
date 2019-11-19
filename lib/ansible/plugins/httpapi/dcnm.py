from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
---
author: Mike Wiebe (mikewiebe)
httpapi: dcnm
short_description: Send REST api calls to Data Center Network Manager (DCNM) NX-OS Fabric Controller.
description:
  - This DCNM plugin provides the HTTPAPI transport methods needed to initiate
    a connection to the DCNM controller, send API requests and process the
    respsonse from the controller.
version_added: "2.10"
"""

import json
import re
import collections
import requests
import sys

from ansible.module_utils._text import to_text
from ansible.module_utils.connection import ConnectionError
from ansible.module_utils.network.common.utils import to_list
from ansible.plugins.httpapi import HttpApiBase


class HttpApi(HttpApiBase):

    def __init__(self, *args, **kwargs):
        super(HttpApi, self).__init__(*args, **kwargs)
        self.headers = {
            'Content-Type': "application/json",
            'Dcnm-Token': None
        }

    def login(self, username, password):
        ''' DCNM Login Method.  This method is automatically called by the
            Ansible plugin architecture if an active Dcnm-Token is not already
            available.
        '''
        method = 'POST'
        path = '/rest/logon'
        data = "{'expirationTime': 60000}"

        try:
            response, response_data = self.connection.send(path, data, method=method, headers=self.headers, force_basic_auth=True)
            response_value = self._get_response_value(response_data)
            self.headers['Dcnm-Token'] = self._response_to_json(response_value)['Dcnm-Token']
        except Exception as e:
            msg = 'Error on attempt to connect and authenticate with DCNM controller: {}'.format(e)
            raise Exception(self._return_error(None, method, path, msg))

    def send_request(self, method, path, json=None):
        ''' This method handles all DCNM REST API requests other then login '''
        if json is None:
            json = {}

        try:
            # Perform some very basic path input validation.
            path = str(path)
            if path[0] != '/':
                msg = 'Value of <path> does not appear to be formated properly'
                raise Exception(self._return_error(None, method, path, msg))
            response, response_data = self.connection.send(path, json, method=method, headers=self.headers, force_basic_auth=True)
            self._verify_response(response, method, path)
            response_value = self._get_response_value(response_data)

            return self._response_to_json(response_value)
        except Exception as e:
            if isinstance(e.message, dict):
                if e.message.get('METHOD') is not None:
                    return [e.message]
                raise
            else:
                raise

    def _verify_response(self, response, method, path):
        ''' Process the return code and response object from DCNM '''
        rc = response.getcode()
        if rc == 200:
            return
        elif rc >= 400:
            path = response.geturl()
            msg = response.msg
            raise Exception(self._return_error(rc, method, path, msg))
        else:
            msg = 'Unknown RETURN_CODE: {}'.format(rc)
            raise Exception(self._return_error(rc, method, path, msg))

    def _get_response_value(self, response_data):
        ''' Extract string data from response_data returned from DCNM '''
        return to_text(response_data.getvalue())

    def _response_to_json(self, response_text):
        ''' Convert response_text to json format '''
        try:
            return json.loads(response_text) if response_text else {}
        # JSONDecodeError only available on Python 3.5+
        except ValueError:
            msg = 'Invalid JSON response: {}'.format(response_text)
            raise ConnectionError(self._return_error(None, None, None, msg))

    def _return_error(self, rc, method, path, error):
        ''' Format error data returned in a raise with a consistent dict format '''
        error_info = {}
        error_info['RETURN_CODE'] = rc
        error_info['METHOD'] = method
        error_info['REQUEST_PATH'] = path
        error_info['ERROR'] = error

        return error_info
