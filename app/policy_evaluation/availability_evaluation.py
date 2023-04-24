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
from datetime import datetime, timedelta
from app import app
from app.utils import compare_execution_window_with_actual_time
import pytz
from qiskit import IBMQ


# For the Qiskit Runtime, we order the devices according to the jobs in the queue.
def evaluate_availability_qiskit(backends):
    app.logger.info("Start to evaluate availability")
    # time zone used in Amazon Braket
    current_time = datetime.now(tz=pytz.UTC)
    current_hour = current_time.hour
    current_day = current_time.day
    result = []
    for b in backends:
        app.logger.info(b)
        provider = IBMQ.get_provider('ibm-q')
        backend = provider.get_backend(b.name())
        result.append(backend.status().pending_jobs)
        app.logger.info("AVAILABILITY b")
    return result


# For Amazon Braket Hybrid Jobs, we calculate the remaining execution window.
def evaluate_availability_aws(devices):
    # time zone used in Amazon Braket
    current_time = datetime.now(tz=pytz.UTC)
    current_hour = current_time.hour
    current_day = current_time.day
    result = []
    for device in devices:
        for d in device:
            app.logger.info("DEVICES")
            app.logger.info(device)
            name = d.name
            if name.__contains__('SV1') or name.__contains__('TN1') or name.__contains__('dm1'):
                result.append(168)
            else:

                for executionWindow in d.properties.service.executionWindows:
                    execution_day = executionWindow.executionDay.value
                    execution_window_start = executionWindow.windowStartHour.hour
                    execution_window_end = executionWindow.windowEndHour.hour
                    if current_time.today().weekday() < 5 and execution_day == 'Weekday':
                        # check if the execution_window corresponds to the actual time
                        available = compare_execution_window_with_actual_time(current_hour, execution_window_start,
                                                                              execution_window_end)

                        if available:
                            execution_time = compute_availability_window(executionWindow)
                            result.append(execution_time)


                    elif current_time.today().weekday() >= 5 and execution_day == 'Weekend':
                        # check if the execution_window corresponds to the actual time
                        available = compare_execution_window_with_actual_time(current_hour, execution_window_start,
                                                                              execution_window_end)

                        if available:
                            execution_time = compute_availability_window(executionWindow)
                            result.append(execution_time)

                    elif execution_day == current_day or execution_day == 'Everyday':
                        # check if the execution_window corresponds to the actual time
                        available = compare_execution_window_with_actual_time(current_hour, execution_window_start,
                                                                              execution_window_end)

                        if available:
                            execution_time = compute_availability_window(executionWindow)
                            result.append(execution_time)

    app.logger.info(result)
    return result


def compute_availability_window(execution_window):
    # Get the current date and time
    current_time = datetime.now(tz=pytz.UTC)
    start_hour = execution_window.windowStartHour.hour
    end_hour = execution_window.windowEndHour.hour

    # Set the start time
    start_time = current_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)

    # Set the end time
    if end_hour >= start_hour:
        end_time = current_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    else:
        # Add one day to the end time to consider it as the next day
        end_time = current_time.replace(hour=end_hour, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # Calculate the time available
    time_available = end_time - start_time
    app.logger.info(time_available.total_seconds() / 3600)
    return time_available.total_seconds() / 3600
