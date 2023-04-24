# ******************************************************************************
#  Copyright (c) 2023 University of Stuttgart
#
#  See the NOTICE file(s) distributed with this work for additional
#  information regarding copyright ownership.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ******************************************************************************

import os

from braket.aws import AwsDevice, AwsDeviceType
from qiskit import IBMQ
import datetime
import pytz
from app import app


def compute_ibm_devices(token, simulators_allowed):
    IBMQ.save_account(token=token)
    provider = IBMQ.load_account()
    backends = provider.backends()
    if not simulators_allowed:
        backends = [device for device in backends if not device.configuration().simulator]

    return backends


def compute_aws_devices(simulators_allowed):
    # get all online AwsDevices
    device_list = AwsDevice.get_devices(statuses=['ONLINE'], types=['QPU', 'SIMULATOR'])

    # only use gate-based QPUs and simulators
    device_list = [device for device in device_list if
                   (device.properties.service.deviceDocumentation.summary.__contains__('gate-model') or
                    device.properties.service.deviceDocumentation.summary.__contains__('simulator'))]

    # if simulators are not allowed do not include them in the result list
    if not simulators_allowed:
        device_list = [device for device in device_list if not device.type == AwsDeviceType.SIMULATOR]

    # check if execution window (given in UTC) corresponds to the current time
    current_time = datetime.datetime.now(tz=pytz.UTC)
    current_day = current_time.day
    current_hour = current_time.hour
    print(current_time.date())

    result = []
    for device in device_list:
        print(device.name)
        for executionWindow in device.properties.service.executionWindows:
            execution_day = executionWindow.executionDay.value
            execution_window_start = executionWindow.windowStartHour.hour
            execution_window_end = executionWindow.windowEndHour.hour
            print(execution_window_start)
            print(execution_window_end)
            if current_time.today().weekday() < 5 and execution_day == 'Weekday':
                # check if the execution_window corresponds to the actual time
                available = compare_execution_window_with_actual_time(current_hour, execution_window_start,
                                                                      execution_window_end)

                if available:
                    if device not in result:
                        result.append(device)

            elif current_time.today().weekday() >= 5 and execution_day == 'Weekend':
                # check if the execution_window corresponds to the actual time
                available = compare_execution_window_with_actual_time(current_hour, execution_window_start,
                                                                      execution_window_end)

                # check if the execution_window corresponds to the actual time
                if available:
                    if device not in result:
                        result.append(device)

            elif execution_day == current_day or execution_day == 'Everyday':
                # check if the execution_window corresponds to the actual time
                available = compare_execution_window_with_actual_time(current_hour, execution_window_start,
                                                                      execution_window_end)

                # check if the execution_window corresponds to the actual time
                if available:
                    if device not in result:
                        result.append(device)
            else:
                print("The execution window of the QPU")
                print(device.name)

    app.logger.info(result)
    return result,


def compare_execution_window_with_actual_time(current_hour, execution_window_start, execution_window_end):
    # check if the execution_window corresponds to the actual time
    if execution_window_start <= current_hour < execution_window_end:
        return True
    return False


def add_devices_for_evaluation(token, simulators_allowed, custom_environment_policy_set):
    devices = []
    backends = []
    app.logger.info("SIMULATORS ALLOWED")
    app.logger.info(simulators_allowed)
    app.logger.info(custom_environment_policy_set)
    # custom environment policy specifies that custom dependencies have to be installed
    # Qiskit Runtime cannot be used
    if not custom_environment_policy_set:
        backends = compute_ibm_devices(token, simulators_allowed)

        # print the list of ibm backends
        for backend in backends:
            app.logger.info("IN BACKENDS")
            app.logger.info(backend.name())
            devices.append(backend.name())

    device_list = compute_aws_devices(simulators_allowed)

    # print the list of aws devices
    for device in device_list:
        app.logger.info(device)
        # print(device.properties)
        # print(device.status)
        devices.append(device)

    return device_list, backends


def authenticate(ibm_token, aws_access_key_id, aws_secret_access_key, aws_region):
    # this will allow you to authenticate to aws
    os.environ["AWS_ACCESS_KEY_ID"] = aws_access_key_id
    os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret_access_key
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    app.logger.info("YOU ARE AUTHENTICATED")
    # authentication to ibm
    #IBMProvider.save_account(token=ibm_token)
    if IBMQ.active_account():
        IBMQ.disable_account()
    IBMQ.enable_account(ibm_token, url='https://auth.quantum-computing.ibm.com/api', hub='ibm-q', group='open', project='main')

