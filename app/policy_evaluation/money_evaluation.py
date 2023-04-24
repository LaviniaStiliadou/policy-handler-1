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
import urllib
import zipfile
from tempfile import mkdtemp
from flask import abort
from redbaron import RedBaron

from app import app
from app.policy_evaluation.zip_handler import search_python_file
from qiskit import IBMQ

def count_and_extract_shots(filename):
    # Load the file with RedBaron
    with open(filename, 'r') as f:
        red = RedBaron(f.read())

    # run, run_batch, create_quantum_task in aws programs
    # run and create_quantum_task create exactly one task that's why we count both of them in one variable
    count_quantum_tasks_statements = 0
    count_quantum_tasks_shots = 0
    count_batch_statements = 0
    count_batch_shots = 0

    # execute statements are in qiskit programs
    count_execute_statements = 0
    count_execute_shots = 0

    for function in red.find_all("def"):
        for node in function.find_all("atomtrailers"):
            if node[0].value == "device" and node[1].value == "run":
                count_quantum_tasks_statements += 1
                # source_code = "x = 1"
                # red2 = RedBaron(source_code)
                # node.append(source_code)
                # new_node_list = RedBaron("print('x is 1')")
                # node.parent.insert_after(new_node_list)
                # find the node representing the second argument
                second_arg = red.find('name', value="shots").parent.value
                try:
                    # get the value of the second argument
                    print(second_arg)
                    count_quantum_tasks_shots += int(node[2].value[1].value.value)
                except TypeError:
                    app.logger.info("Runtime evaluation is required")
                    abort(400)
            if node[0].value == "qiskit" and node[1].value == "execute":
                count_execute_statements += 1
                # get the value of the second argument
                print(int(node[2].value[2].value.value))
                try:
                    count_execute_shots += int(node[2].value[2].value.value)
                except TypeError:
                    app.logger.info("Runtime evaluation is required")
                    abort(400)

                print(count_execute_shots)
                app.logger.info("THE SHOTS IN EXECUTE")
                app.logger.info(count_execute_shots)
            if node[0].value == "device" and node[1].value == "run_batch":
                count_batch_statements += 1
                shots = node[2].value[1].value
                try:
                    count_batch_shots += shots
                except TypeError:
                    app.logger.info("Runtime evaluation is required")
                    abort(400)
            if node[0].value == "braket_client" and node[1].value == "create_quantum_task":
                count_quantum_tasks_statements += 1
                shots = node[2].value.find("name", value="shots").parent.value
                try:
                    count_quantum_tasks_shots += shots
                except TypeError:
                    app.logger.info("Runtime evaluation is required")
                    abort(400)

    app.logger.info("number of quantum tasks")
    app.logger.info(count_quantum_tasks_statements)

    app.logger.info("number of quantum task shots")
    app.logger.info(count_quantum_tasks_shots)

    app.logger.info("number of batch tasks")
    app.logger.info(count_batch_statements)

    app.logger.info("number of batch task shots")
    app.logger.info(count_batch_shots)

    app.logger.info("number of execute statements")
    app.logger.info(count_execute_statements)

    app.logger.info("number of execute shots")
    app.logger.info(count_execute_shots)

    return count_quantum_tasks_statements, count_quantum_tasks_shots, count_batch_statements, count_batch_shots, \
           count_execute_statements, count_execute_shots


def calculate_costs(devices, money_policy, required_programs_url):
    app.logger.info("Start to estimate costs")
    # get URL to the ZIP file with the required programs
    url = 'http://' + os.environ.get('FLASK_RUN_HOST') + ':' + os.environ.get('FLASK_RUN_PORT') + required_programs_url

    # download the ZIP file
    app.logger.info('Downloading required programs from: ' + str(url))
    download_path, response = urllib.request.urlretrieve(url, "requiredPrograms.zip")

    # dict to store task IDs and the paths to the related programs
    task_id_program_map = {}

    # extract the zip file
    with zipfile.ZipFile(download_path, "r") as zip_ref:
        directory = mkdtemp()
        app.logger.info('Extracting to directory: ' + str(directory))
        zip_ref.extractall(directory)

        # zip contains one folder per task within the candidate
        zip_contents = [f for f in os.listdir(directory)]
        for zipContent in zip_contents:
            app.logger.info('Searching for program related to task with ID: ' + str(zipContent))

            # search for Python file and store with ID if found
            python_file = search_python_file(os.path.join(directory, zipContent))
            if python_file is not None:
                task_id_program_map[zipContent] = python_file

    sum_count_quantum_tasks_statements = 0
    sum_count_quantum_tasks_shots = 0
    sum_count_batch_statements = 0
    sum_count_batch_shots = 0
    sum_count_execute_statements = 0
    sum_count_execute_shots = 0
    for task in task_id_program_map:
        count_quantum_tasks_statements, count_quantum_tasks_shots, count_batch_statements, count_batch_shots, \
        count_execute_statements, count_execute_shots = count_and_extract_shots(task_id_program_map[task])
        sum_count_quantum_tasks_statements += count_quantum_tasks_statements
        sum_count_quantum_tasks_shots += count_quantum_tasks_shots
        sum_count_batch_statements += count_batch_statements
        sum_count_batch_shots += count_batch_shots
        sum_count_execute_statements += count_execute_statements
        sum_count_execute_shots += count_execute_shots

    price_per_qpu = compute_price_per_qpu(sum_count_quantum_tasks_statements, sum_count_quantum_tasks_shots,
                                          sum_count_batch_statements, sum_count_batch_shots,
                                          sum_count_execute_statements, sum_count_execute_shots, devices)
    app.logger.info("The result of qpu costs")
    app.logger.info(price_per_qpu)
    return price_per_qpu


def compute_price_per_qpu(count_quantum_tasks_statements, count_quantum_tasks_shots, count_batch_statements,
                          count_batch_shots, count_execute_statements, count_execute_shots, devices):
    result = []
    for device in devices:
        price_of_tasks_with_shots = 0

        # currently it is not possible to retrieve the task price of each QPU, but it is actually the same for all
        # devices 0.3 USD
        price_of_tasks = count_quantum_tasks_statements * 0.3
        if device.name == "Lucy":
            price_of_tasks_with_shots = device.properties.service.deviceCost.price * count_quantum_tasks_statements * \
                                        count_quantum_tasks_shots

        if device.name == "IonQ":
            price_of_tasks_with_shots = device.properties.service.deviceCost.price * count_quantum_tasks_statements * \
                                        count_quantum_tasks_shots

        if device.name == "Aspen-M-2":
            price_of_tasks_with_shots = device.properties.service.deviceCost.price * count_quantum_tasks_statements * \
                                        count_quantum_tasks_shots

        if device.name == "Aspen-M-3":
            price_of_tasks_with_shots = device.properties.service.deviceCost.price * count_quantum_tasks_statements * \
                                        count_quantum_tasks_shots
        result.append(price_of_tasks_with_shots + price_of_tasks)

    return result


def calculate_costs_qiskit(sumExecutionTimeClassical, sumExecutionTimeQuantum, devices):
    provider = IBMQ.load_account()
    backends = provider.backends()
    results = []
    for device in backends:
        results.append(0);

    for device in devices:
        if device not in backends:
            results(1.6 * (float(sumExecutionTimeClassical) + float(sumExecutionTimeQuantum)))

    return results


def calculate_costs_aws(sumExecutionTimeClassical, sumExecutionTimeQuantum,sumNumberOfQuantumShots,
                        sumNumberOfQuantumTasks, aws_devices):
    result = []
    classical_ressources = sumExecutionTimeClassical * 0.00443
    for device in aws_devices:
        price_of_tasks_with_shots = 0
        if device.name == "SV1":
            simulator_cost = device.properties.service.deviceCost.price * sumExecutionTimeQuantum
            result.append(simulator_cost + classical_ressources)
        if device.name == "TN1":
            simulator_cost = device.properties.service.deviceCost.price * sumExecutionTimeQuantum
            result.append(simulator_cost + classical_ressources)
        if device.name == "dm1":
            simulator_cost = device.properties.service.deviceCost.price * sumExecutionTimeQuantum
            result.append(simulator_cost + classical_ressources)
        # currently it is not possible to retrieve the task price of each QPU, but it is actually the same for all
        # devices 0.3 USD
        price_of_tasks = sumNumberOfQuantumTasks * 0.3
        if device.name == "Lucy":
            price_of_tasks_with_shots = device.properties.service.deviceCost.price * sumNumberOfQuantumTasks * \
                                        sumNumberOfQuantumShots
            result.append(price_of_tasks_with_shots + price_of_tasks + classical_ressources)
        if device.name == "IonQ":
            price_of_tasks_with_shots = device.properties.service.deviceCost.price * sumNumberOfQuantumTasks * \
                                        sumNumberOfQuantumShots
            result.append(price_of_tasks_with_shots + price_of_tasks + classical_ressources)
        if device.name == "Aspen-M-2":
            price_of_tasks_with_shots = device.properties.service.deviceCost.price * sumNumberOfQuantumTasks * \
                                        sumNumberOfQuantumShots
            result.append(price_of_tasks_with_shots + price_of_tasks + classical_ressources)
        if device.name == "Aspen-M-3":
            price_of_tasks_with_shots = device.properties.service.deviceCost.price * sumNumberOfQuantumTasks * \
                                        sumNumberOfQuantumShots
            result.append(price_of_tasks_with_shots + price_of_tasks + classical_ressources)

    return result