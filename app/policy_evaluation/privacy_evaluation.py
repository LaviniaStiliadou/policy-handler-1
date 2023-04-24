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
from app import app


def evaluate_privacy_aws(devices, privacy_policy):
    app.logger.info("Start to evaluate privacy")
    data_retention = privacy_policy['privacyPolicy']['dataRetention']
    third_party_qpu = privacy_policy['privacyPolicy']['thirdPartyQPU']

    data_retention_result = [0] * len(devices)
    third_party_qpu_result = [0] * len(devices)

    for i in range(len(devices)):
        if data_retention == 'true':
            data_retention_result[i] = 1
        if third_party_qpu == 'true':
            third_party_qpu_result[i] = 1

    return data_retention_result, third_party_qpu_result


def evaluate_privacy_qiskit(devices, privacy_policy):
    app.logger.info("Start to evaluate privacy")
    data_retention = privacy_policy['privacyPolicy']['dataRetention']
    third_party_qpu = privacy_policy['privacyPolicy']['thirdPartyQPU']

    data_retention_result = [0] * len(devices)
    third_party_qpu_result = [0] * len(devices)

    for i in range(len(devices)):
        device = devices[i]
        if data_retention == 'false':
            # only AWS devices allow the data Retention of tasks after 90 days
            data_retention_result[i] = 1
        if third_party_qpu == 'false':
            third_party_qpu_result[i] = 1

    return data_retention_result, third_party_qpu_result

