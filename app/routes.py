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
from flask import jsonify, abort, request, send_from_directory, url_for
import os
import json

from app.policy_evaluation.availability_evaluation import evaluate_availability_aws, \
    evaluate_availability_qiskit
from app.utils import add_devices_for_evaluation, authenticate, compute_aws_devices
from app.policy_evaluation.privacy_evaluation import evaluate_privacy_qiskit, evaluate_privacy_aws
from app.policy_evaluation.money_evaluation import calculate_costs, calculate_costs_aws, calculate_costs_qiskit
import string
import random


@app.route('/policy-handler/api/v1.0/design-time-evaluation-hybrid-runtime', methods=['POST'])
def design_time_evaluation_hybrid_runtime():
    app.logger.info('Received request for hybrid runtime evaluation...')
    # extract required input data
    if not request.form.get('moneyPolicy') and not request.form.get('availabilityPolicy') \
            and not request.form.get('privacyPolicy') and not request.form.get('customEnvironmentPolicy') \
            and not request.form.get('awsKeys') and not request.form.get('ibmqToken') \
            and not request.files['requiredPrograms']:
        app.logger.info('Not all required parameters available in request: ')
        abort(400)
    ibmq_token = request.form.get('ibmqToken')
    ibmq_token = json.loads(ibmq_token)['ibmqToken']
    data = json.loads(request.form.get('awsKeys'))
    aws_access_key = data['awsKeys']["awsAccessKey"]
    aws_secret_access_key = data['awsKeys']["awsSecretAccessKey"]

    # set to any region which supports Amazon Braket
    aws_region = 'us-east-1'
    authenticate(ibmq_token, aws_access_key, aws_secret_access_key, aws_region)
    custom_environment_policy_set = False
    money_policy_set = False
    money_policy = json.loads(request.form.get('moneyPolicy'))
    privacy_policy = json.loads(request.form.get('privacyPolicy'))
    availability_policy = json.loads(request.form.get('availabilityPolicy'))
    custom_environment_policy = json.loads(request.form.get('customEnvironmentPolicy'))
    required_programs = request.files['requiredPrograms']
    # store file with required programs in local file and forward path to the workers
    directory = app.config["UPLOAD_FOLDER"]
    app.logger.info('Storing file comprising required programs at folder: ' + str(directory))
    if not os.path.exists(directory):
        os.makedirs(directory)
    randomString = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    fileName = 'required-programs' + randomString + '.zip'
    required_programs.save(os.path.join(directory, fileName))
    url = url_for('download_uploaded_file', name=os.path.basename(fileName))
    app.logger.info('File available via URL: ' + str(url))

    # if this policy is specified the execution of the programs require a customized docker environment
    # since Qiskit Runtime does not allow this, only devices from AWS are included in the selection
    custom_environment_policy_set = False
    simulators_allowed = True
    if len(custom_environment_policy) > 1 or len(money_policy) > 1:
        custom_environment_policy_set = True
        simulators_allowed = False

    # compute all devices from each provider
    devices, backends = add_devices_for_evaluation(ibmq_token, simulators_allowed, custom_environment_policy_set)


    if len(money_policy) == 1:
        money_policy_set = True
        money_policy_result = calculate_costs(devices, money_policy, url)
        money_policy_weight = money_policy['moneyPolicy']['weight']
    else:
        money_policy_result = [0] * len(devices)
        money_policy_weight = 0

    # get queue size for ibm devices
    # get execution window for aws devices
    if len(availability_policy) == 1:
        availability_policy_result_aws = evaluate_availability_aws(devices)
        availability_policy_result_qiskit = evaluate_availability_qiskit(backends)
        availability_policy_weight = availability_policy['availabilityPolicy']['weight']
    else:
        availability_policy_result_aws = [0] * len(devices)
        availability_policy_result_qiskit = [0] * len(backends)
        availability_policy_weight = 0

    if len(privacy_policy) == 1:
        data_retention_result_aws, third_party_qpu_result_aws = evaluate_privacy_aws(devices, privacy_policy)
        data_retention_result_qiskit, third_party_qpu_result_qiskit = evaluate_privacy_aws(backends, privacy_policy)
        privacy_policy_weight = privacy_policy['privacyPolicy']['weight']
    else:
        data_retention_result_aws = [0] * len(devices)
        third_party_qpu_result_aws = [0] * len(devices)
        data_retention_result_qiskit = [0] * len(backends)
        third_party_qpu_result_qiskit = [0] * len(backends)
        privacy_policy_weight = 0

    # Ranking
    combined_aws = []
    for cost, time, data, third_party in zip(money_policy_result, availability_policy_result_aws,
                                             data_retention_result_aws,
                                             third_party_qpu_result_aws):
        combined_aws.append([cost, time, data, third_party])
    scores = [0] * len(devices)

    multipliers = [money_policy_weight, availability_policy_weight, privacy_policy_weight, privacy_policy_weight]
    counter = 0
    for i in range(len(combined_aws)):
        counter = 0
        score = 0
        for j in combined_aws[i]:
            score += int(j) * int(multipliers[counter])
            counter = counter + 1
        scores[i] = score

    result = []

    for device, cost, time, data, third_party, score in zip(devices, money_policy_result, availability_policy_result_aws,
                                                            data_retention_result_aws, third_party_qpu_result_aws, scores):
        result.append(["AWS Runtime", device, cost, time, data, third_party, score])

    if min(scores) < 0:
        sorted_list = sorted(result, key=lambda x: x[5], reverse=True)
    else:
        sorted_list = sorted(result, key=lambda x: x[5])
    if not custom_environment_policy_set and not money_policy_set:
        combined_qiskit = []
        for time, data, third_party in zip(availability_policy_result_qiskit,
                                                 data_retention_result_qiskit,
                                                 third_party_qpu_result_qiskit):
            combined_qiskit.append([time, data, third_party])
        scores_qiskit = [0] * len(backends)

        multipliers = [availability_policy_weight, privacy_policy_weight, privacy_policy_weight]
        counter = 0
        for i in range(len(combined_qiskit)):
            counter = 0
            score = 0
            for j in combined_qiskit[i]:
                score += int(j) * int(multipliers[counter])
                counter = counter + 1
            scores_qiskit[i] = score
        result = []

        for device, time, data, third_party, score in zip(backends, availability_policy_result_qiskit,
                                                                data_retention_result_qiskit,
                                                                third_party_qpu_result_qiskit, scores_qiskit):
            result.append(["Qiskit Runtime", device, time, data, third_party, score])

        if min(scores_qiskit) < 0:
            sorted_list_qiskit = sorted(result, key=lambda x: x[5], reverse=True)
        else:
            sorted_list_qiskit = sorted(result, key=lambda x: x[5])
        if min(scores_qiskit) > min(scores):
            return "Qiskit Runtime"
        if min(scores_qiskit) < min(scores):
            return "AWS Runtime"
        if min(scores_qiskit) == min(scores):
            return "Tie"

    return json.dumps(sorted_list[0])


@app.route('/policy-handler/api/v1.0/runtime-evaluation-hybrid-runtime', methods=['POST'])
def runtime_evaluation_hybrid_runtime():
    app.logger.info('Received request for hybrid runtime evaluation...')
    app.logger.info(request.data)
    json_data = json.loads(request.data)
    policy_set = False
    custom_environment_policy_set = False
    availability_policy = False
    simulators_allowed = False
    money_policy_weight = 0
    availability_policy_weight = 0
    privacy_policy_weight = 0
    availability_policy_set = False
    if 'devices' in json_data:
        devices = json_data['devices']
        devices = devices.split(',')
    if 'money' in json_data:
        # 'moneyPolicy' key exists in the JSON object
        money_policy = json_data['money']
        json_money = json.loads(money_policy)
        money_policy = json_money
        if money_policy is not None:
            policy_set = True
            money_policy_weight = money_policy['moneyWeight']
    if 'availability' in json_data:
        availability_policy = json_data['availability']
        if availability_policy is not None:
            availability_policy = json.loads(availability_policy)
            policy_set = True
            availability_policy_weight = availability_policy['availabilityWeight']
            availability_policy_set = True
    if 'privacy' in json_data:
        privacy_policy = json_data['privacy']
        if privacy_policy is not None:
            privacy_policy = json.loads(privacy_policy)
            policy_set = True
            privacy_policy_weight = privacy_policy['privacyWeight']
    if 'customEnvironment' in json_data:
        custom_environment_policy = json_data['customEnvironment']
        if custom_environment_policy is not None:
            policy_set = True
            custom_environment_policy_set = True
    if 'awsAccessKey' in json_data and 'awsSecretAccessKey' in json_data:
        aws_secret_access_key = json_data["awsSecretAccessKey"]
        aws_access_key = json_data["awsAccessKey"]
        aws_region = "us-east-1"
    if 'ibmqToken' in json_data:
        ibmq_token = json_data['ibmqToken']
    if 'simulatorsAllowed' in json_data:
        simulators_allowed = json_data['simulatorsAllowed']
    if not policy_set:
        app.logger.info('No policy provided for evaluation')
        abort(400)
    if 'ibmqToken' not in json_data and 'awsAccessKey' not in json_data and 'awsSecretAccessKey' not in json_data:
        app.logger.info("Some credentials are missing")
        abort(400)

    app.logger.info('Received request for hybrid runtime evaluation...')
    authenticate(ibmq_token, aws_access_key, aws_secret_access_key, aws_region)
    aws_devices = compute_aws_devices(simulators_allowed)
    # no QPU is detected from NISQ, we only deal with AWS devices then
    if len(devices) == 0:
        app.logger.info('NISQ did not detect any devices')
        custom_environment_policy_set = True
        devices = aws_devices

    # if this policy is specified the execution of the programs require a customized docker environment
    # since Qiskit Runtime does not allow this, AWS Runtime is returned
    if custom_environment_policy is not 'null':
        devices = aws_devices

    if money_policy is not None:
        sumExecutionTimeClassical = money_policy['sumExecutionTimeClassical']
        sumExecutionTimeQuantum = money_policy['sumExecutionTimeQuantum']
        sumNumberOfQuantumShots = money_policy['sumNumberOfQuantumShots']
        sumNumberOfQuantumTasks = money_policy['sumNumberOfQuantumTaks']
        money_policy_result_qiskit = calculate_costs_qiskit(sumExecutionTimeClassical, sumExecutionTimeQuantum, devices)
        money_policy_result_aws = calculate_costs_aws(sumExecutionTimeClassical, sumExecutionTimeQuantum,
                                                      sumNumberOfQuantumShots, sumNumberOfQuantumTasks, aws_devices)

    if availability_policy is not None:
        availability_policy_result_aws = evaluate_availability_aws(aws_devices)
        if not custom_environment_policy_set:
            availability_policy_result_qiskit = evaluate_availability_qiskit(devices)
    if privacy_policy is not None:
        if not custom_environment_policy_set:
            data_retention_result_qiskit, third_party_qpu_result_qiskit = evaluate_privacy_qiskit(devices,
                                                                                                  privacy_policy)
        data_retention_result_aws, third_party_qpu_result_aws = evaluate_privacy_aws(aws_devices, privacy_policy)
    else:
        data_retention_result_aws = [0] * len(aws_devices)
        third_party_qpu_result_aws = [0] * len(aws_devices)
        data_retention_result_aws = [0] * len(devices)
        third_party_qpu_result_aws = [0] * len(devices)

    aws_scores = [0] * len(aws_devices)
    # Ranking
    combined_aws = []
    for cost, time, data, third_party in zip(money_policy_result_aws, availability_policy_result_aws,
                                             data_retention_result_aws,
                                             third_party_qpu_result_aws):
        combined_aws.append([cost, time, data, third_party])
    aws_scores = [0] * len(aws_devices)
    if custom_environment_policy_set:
        combined_qiskit = []
        for cost, time, data, third_party in zip(money_policy_result_qiskit, availability_policy_result_qiskit,
                                                 data_retention_result_qiskit,
                                                 third_party_qpu_result_qiskit):
            combined_qiskit.append([cost, time, data, third_party])
        qiskit_scores = [0] * len(devices)

    multipliers = [money_policy_weight, availability_policy_weight, privacy_policy_weight, privacy_policy_weight]

    for i in range(len(combined_aws)):
        counter = 0
        score = 0
        for j in combined_aws[i]:
            score += int(j) * int(multipliers[counter])
            counter = counter + 1
        aws_scores[i] = score

    aws_result = []
    combined_qiskit = []
    for i in range(len(combined_qiskit)):
        counter = 0
        score = 0
        for j in combined_qiskit[i]:
            score += int(j) * int(multipliers[counter])
            counter = counter + 1
        qiskit_scores[i] = score

    qiskit_result = []

    for device, cost, time, data, third_party, score in zip(aws_devices, money_policy_result_aws,
                                                            availability_policy_result_aws,
                                                            data_retention_result_aws, third_party_qpu_result_aws,
                                                            aws_scores):
        aws_result.append([device, cost, time, data, third_party, score])

    for device, cost, time, data, third_party, score in zip(aws_devices, money_policy_result_qiskit,
                                                            availability_policy_result_qiskit,
                                                            data_retention_result_qiskit, third_party_qpu_result_qiskit,
                                                            qiskit_scores):
        qiskit_result.append([device, cost, time, data, third_party, score])

    if min(aws_scores) < 0:
        sorted_list_aws = sorted(aws_result, key=lambda x: x[4], reverse=True)
    else:
        sorted_list_aws = sorted(aws_result, key=lambda x: x[4])

    if min(qiskit_scores) < 0:
        sorted_list_qiskit = sorted(qiskit_result, key=lambda x: x[4], reverse=True)
    else:
        sorted_list_qiskit = sorted(qiskit_result, key=lambda x: x[4])

    best_aws_result = aws_scores[0]
    best_results = []
    if custom_environment_policy_set:
        best_qiskit_result = qiskit_scores[0]
        if best_aws_result > best_qiskit_result:
            return json.dumps(sorted_list_aws[0])
        if best_aws_result < best_qiskit_result:
            return json.dumps(sorted_list_qiskit[0])
        if best_aws_result == best_qiskit_result:
            return json.dumps([sorted_list_qiskit[0], sorted_list_aws[0]])
    if availability_policy_set:
        best_qiskit_result = qiskit_scores[0]
        best_results.append(best_qiskit_result)
        best_results.append(best_aws_result)
        return json.dumps(best_results)

    return json.dumps(sorted_list_aws[0])


@app.route('/policy-handler/api/v1.0/uploads/<name>')
def download_uploaded_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)


@app.route('/policy-handler/api/v1.0/hybrid-programs/<name>')
def download_generated_file(name):
    return send_from_directory(app.config["RESULT_FOLDER"], name)


@app.route('/policy-handler/api/v1.0/version', methods=['GET'])
def version():
    return jsonify({'version': '1.0'})
