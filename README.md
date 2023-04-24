[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# policy-handler


The policy-handler can be used in conjunction with the [QuantME Transformation Framework](https://github.com/UST-QuAntiL/QuantME-TransformationFramework).
It allows an evaluation of a hybrid runtime (Qiskit Runtime, Amazon Braket Hybrid Jobs) based on non-functional requirements and circuits during design time or runtime.

## Docker Setup

* Clone the repository:
```
git clone https://github.com/UST-QuAntiL/policy-handler.git
```

* Start the containers using the [docker-compose file](docker-compose.yml):
```
docker-compose pull
docker-compose up
```

Now the policy-handler is available on http://localhost:8892/.

## Local Setup

### Start Redis

Start Redis, e.g., using Docker:

```
docker run -p 5050:5050 redis --port 5050
```

### Configure the Policy Handler

Before starting the Qiskit Runtime handler, define the following environment variables:

```
FLASK_RUN_PORT=8892
REDIS_URL=redis://$DOCKER_ENGINE_IP:5050
```

Thereby, please replace $DOCKER_ENGINE_IP with the actual IP of the Docker engine you started the Redis container.

### Configure the Database

* Install SQLite DB, e.g., as described [here](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-iv-database)
* Create a `data` folder in the `app` folder
* Setup the results table with the following commands:

```
flask db migrate -m "results table"
flask db upgrade
```

### Start the Application

Start a worker for the request queue:

```
rq worker --url redis://$DOCKER_ENGINE_IP:5050 policy-handler
```

Finally, start the Flask application, e.g., using PyCharm or the command line.


### Disclaimer of Warranty
Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE. You are solely responsible for determining the appropriateness of using or redistributing the Work and assume any risks associated with Your exercise of permissions under this License.

### Haftungsausschluss
Dies ist ein Forschungsprototyp. Die Haftung für entgangenen Gewinn, Produktionsausfall, Betriebsunterbrechung, entgangene Nutzungen, Verlust von Daten und Informationen, Finanzierungsaufwendungen sowie sonstige Vermögens- und Folgeschäden ist, außer in Fällen von grober Fahrlässigkeit, Vorsatz und Personenschäden, ausgeschlossen.