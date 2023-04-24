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

from os import listdir
from tempfile import mkdtemp

from app import app
import zipfile
import os


def search_python_file(directory):
    # only .py are supported, also nested in zip files
    contained_python_files = [f for f in listdir(os.path.join(directory)) if f.endswith('.py')]
    if len(contained_python_files) >= 1:
        app.logger.info('Found Python file with name: ' + str(contained_python_files[0]))

        # we only support one file, in case there are multiple files, try the first one
        return os.path.join(directory, contained_python_files[0])

    # check if there are nested Python files
    contained_zip_files = [f for f in listdir(os.path.join(directory)) if f.endswith('.zip')]
    for zip in contained_zip_files:

        # extract the zip file
        with zipfile.ZipFile(os.path.join(directory, zip), "r") as zip_ref:
            folder = mkdtemp()
            app.logger.info('Extracting to directory: ' + str(folder))
            zip_ref.extractall(folder)

            # recursively search within zip
            result = search_python_file(folder)

            # return if we found the first Python file
            if result is not None:
                return os.path.join(folder, result)

    return None


def zip_runtime_program(hybrid_program_temp, meta_data_temp):
    if os.path.exists('../hybrid_program.zip'):
        os.remove('../hybrid_program.zip')
    zip_obj = zipfile.ZipFile('../hybrid_program.zip', 'w')
    zip_obj.write(hybrid_program_temp.name, 'hybrid_program.py')
    zip_obj.write(meta_data_temp.name, 'hybrid_program.json')
    zip_obj.close()
    zip_obj = open('../hybrid_program.zip', "rb")
    return zip_obj.read(), '../hybrid_program.zip'


def zip_polling_agent(templates_directory, polling_agent_temp, hybrid_program):
    # zip generated polling agent, afterwards zip resulting file with required Dockerfile
    if os.path.exists('../polling_agent.zip'):
        os.remove('../polling_agent.zip')
    if os.path.exists('../polling_agent_wrapper.zip'):
        os.remove('../polling_agent_wrapper.zip')
    zip_obj = zipfile.ZipFile('../polling_agent.zip', 'w')
    zip_obj.write(polling_agent_temp.name, 'polling_agent.py')
    zip_obj.write(hybrid_program, 'hybrid_program.zip')
    zip_obj.close()
    zip_obj = zipfile.ZipFile('../polling_agent_wrapper.zip', 'w')
    zip_obj.write('../polling_agent.zip', 'service.zip')
    zip_obj.write(os.path.join(templates_directory, 'Dockerfile'), 'Dockerfile')
    zip_obj = open('../polling_agent_wrapper.zip', "rb")
    return zip_obj.read()
