import atexit
import math
import os
import sys
from time import sleep
import pika
import uuid
import json
import logging
import threading
from web3 import Web3
from flask import Flask, abort, request, jsonify
from werkzeug.exceptions import BadRequest
from io import StringIO
from src.cli import ZerePyCLI
from dstack_sdk import AsyncTappdClient, DeriveKeyResponse, TdxQuoteResponse
import asyncio
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("cli")

# Flask app
app = Flask(__name__)

load_dotenv()
# RabbitMQ connection parameters
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT")
JOBS_QUEUE = os.getenv("JOBS_QUEUE")
RESPONSES_QUEUE = os.getenv("RESPONSES_QUEUE")
SERVER_HOST = os.getenv("SERVER_HOST")
SERVER_PORT = os.getenv("SERVER_PORT")
DSTACK_SIMULATOR_ENDPOINT = os.getenv("DSTACK_SIMULATOR_ENDPOINT")
os.environ["GOAT_WALLET_PRIVATE_KEY"] = ""
os.environ["GOAT_WALLET_PUBKEY"] = ""


def pubkey_exists() -> bool:
    return len(os.getenv("GOAT_WALLET_PUBKEY")) > 0


def get_pubkey_from_private_key(private_key_string: str) -> str:
    if private_key_string.startswith("0x"):
        private_key_string = private_key_string[2:]
    private_key_bytes = bytes.fromhex(private_key_string)
    account = Web3().eth.account.from_key(private_key_bytes)
    return account.address


def set_private_key(private_key: str) -> None:
    if pubkey_exists():
        return
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    os.environ["GOAT_WALLET_PRIVATE_KEY"] = private_key
    pubkey = get_pubkey_from_private_key(private_key)
    os.environ["GOAT_WALLET_PUBKEY"] = pubkey
    print(f"Private key set. Public key: {pubkey}")


# initialize goat


# Initialize the ZerePyCLI
cli = ZerePyCLI()
cli._load_default_agent()
cli._list_loaded_agent()
cli.list_connections()


# Graceful shutdown handler
def cleanup():
    logger.info("Shutting down gracefully...")


atexit.register(cleanup)

#######################################################################################
######################################### GET #########################################
#######################################################################################


# Health check endpoint
@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200


# get config
@app.route("/info", methods=["GET"])
def info():
    general = json.load(open("agents/general.json", "r"))
    default_agent_name = general["default_agent"]
    config = json.load(open(f"agents/{default_agent_name}.json", "r"))
    return jsonify({"config": config}), 200


@app.get("/derivekey")
async def derivekey():
    if pubkey_exists():
        return jsonify({"pubkey": os.getenv("GOAT_WALLET_PUBKEY")}), 200
    try:
        print(f"dstack endpoint: {DSTACK_SIMULATOR_ENDPOINT}")
        client = AsyncTappdClient(DSTACK_SIMULATOR_ENDPOINT)
        # generate random string
        random_path = f"/{str(uuid.uuid4())}"
        subject = "zerepy_v0.1.0"
        deriveKey = await client.derive_key(random_path, subject)

        assert isinstance(deriveKey, DeriveKeyResponse)
        asBytes = deriveKey.toBytes()

        # hash the derived key
        keccak_private_key_bytes = Web3().keccak(asBytes)
        keccak_private_key_string = keccak_private_key_bytes.hex().replace("0x", "")

        set_private_key(keccak_private_key_string)
        return jsonify({"pubkey": os.getenv("GOAT_WALLET_PUBKEY")}), 200
    except Exception as e:
        print(f"Error in init_goat: {e}")
        return jsonify({"error": str(e)}), 500


@app.get("/tdxquote")
async def tdxquote():
    required_fields = ["report_data"]
    data = request.get_json()
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    client = AsyncTappdClient(DSTACK_SIMULATOR_ENDPOINT)
    tdxQuote = await client.tdx_quote(data["report_data"])
    assert isinstance(tdxQuote, TdxQuoteResponse)

    return {"tdxQuote": tdxQuote.quote}


#######################################################################################
######################################## POST #########################################
#######################################################################################
@app.route("/execute_command", methods=["POST"])
def execute_command():
    log_output = StringIO()
    log_handler = logging.StreamHandler(log_output)
    logger.addHandler(log_handler)

    try:
        # Extract data from the request
        data = request.get_json()
        if "args" not in data:
            raise BadRequest('Missing "command" or "args" field')

        args = data["args"]

        # Validate if the command is valid in ZerePyCLI
        input_string = " ".join(args)
        try:
            cli._handle_command(input_string)

        except Exception as e:
            logger.error(f"Error executing command {input_string}: {e}")
            return jsonify({"error": str(e)}), 500

        result = {"status": "success"}

        # Capture the logs
        log_output.seek(0)  # Go to the start of the StringIO buffer
        logs = log_output.read()
        result["logs"] = logs

        # Return the result with logs in the response
        return jsonify(result), 202

    except BadRequest as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error in execute_command endpoint: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


@app.before_request
def before_request():
    if request.environ.get("HTTP_TRANSFER_ENCODING", "").lower() == "chunked":
        server = request.environ.get("SERVER_SOFTWARE", "")
        if server.lower().startswith("gunicorn/"):
            if "wsgi.input_terminated" in request.environ:
                app.logger.debug(
                    "environ wsgi.input_terminated already set, keeping: %s"
                    % request.environ["wsgi.input_terminated"]
                )
            else:
                request.environ["wsgi.input_terminated"] = 1
        else:
            abort(501, "Chunked requests are not supported for server %s" % server)


@app.after_request
def set_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Credentials"] = "true"

    if request.method == "OPTIONS":
        # Both of these headers are only used for the "preflight request"
        # http://www.w3.org/TR/cors/#access-control-allow-methods-response-header
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, PATCH, OPTIONS"
        )
        response.headers["Access-Control-Max-Age"] = "3600"  # 1 hour cache
        if request.headers.get("Access-Control-Request-Headers") is not None:
            response.headers["Access-Control-Allow-Headers"] = request.headers[
                "Access-Control-Request-Headers"
            ]
    return response


# Run consumers in the background and ensure a WSGI server handles the Flask app
if __name__ == "__main__":
    # Start the job and response consumers in separate threads
    # job_consumer_thread = threading.Thread(target=consume_job_event)
    # response_consumer_thread = threading.Thread(target=consume_response_event)
    #
    # job_consumer_thread.daemon = True  # Make threads exit when the main program exits
    # response_consumer_thread.daemon = True
    # job_consumer_thread.start()
    # response_consumer_thread.start()

    # Import and run Gunicorn in production mode
    from gunicorn.app.base import BaseApplication

    class GunicornApp(BaseApplication):
        def __init__(self, app):
            self.application = app
            super().__init__()

        def load(self):
            return self.application

    # Run Gunicorn with the Flask app
    app_config = {
        "bind": f"{SERVER_HOST}:{SERVER_PORT}",  # Bind the server to the correct host and port
        "workers": 4,  # Adjust the number of workers based on your machine's capabilities
    }

    gunicorn_app = GunicornApp(app)
    gunicorn_app.run()


# Helper function to connect to RabbitMQ
def get_rabbitmq_channel():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
    )
    channel = connection.channel()
    return channel


# Producer function to send job data to RabbitMQ
def produce_job_event(job_id, command_name, args):
    try:
        channel = get_rabbitmq_channel()
        channel.queue_declare(queue=JOBS_QUEUE)

        message = {"job_id": job_id, "command": command_name, "args": args}
        channel.basic_publish(
            exchange="",
            routing_key=JOBS_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            ),
        )
        logger.info(f"Job {job_id} published to jobs_queue")
    except Exception as e:
        logger.error(f"Failed to produce job event: {e}")
    finally:
        channel.close()


# Consumer function to process jobs from the queue
def consume_job_event():
    def callback(ch, method, properties, body):
        try:
            job_data = json.loads(body)
            job_id = job_data["job_id"]
            command_name = job_data["command"]
            args = job_data["args"]

            # Find the command in ZerePyCLI and run the handler
            command = cli.commands.get(command_name)
            if command:
                logger.info(f"Processing job {job_id} with command {command}")
                command.handler(args)  # This will execute the command handler
                result = {"job_id": job_id, "status": "success"}
            else:
                result = {
                    "job_id": job_id,
                    "status": "failed",
                    "error": "Invalid command",
                }

            # Publish the result to the responses_queue
            publish_response(job_id, result)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing job: {e}")

    channel = get_rabbitmq_channel()
    channel.queue_declare(queue=JOBS_QUEUE)
    channel.basic_consume(queue=JOBS_QUEUE, on_message_callback=callback)
    logger.info("Waiting for job events. To exit press Ctrl+C")
    channel.start_consuming()


# Producer function to send response back to responses_queue
def publish_response(job_id, result):
    try:
        channel = get_rabbitmq_channel()
        channel.queue_declare(queue=RESPONSES_QUEUE)

        channel.basic_publish(
            exchange="",
            routing_key=RESPONSES_QUEUE,
            body=json.dumps(result),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            ),
        )
        logger.info(f"Published response for job {job_id} to responses_queue")
    except Exception as e:
        logger.error(f"Failed to publish response: {e}")
    finally:
        channel.close()


# Consumer function to process job responses from the queue
def consume_response_event():
    def callback(ch, method, properties, body):
        try:
            response_data = json.loads(body)
            job_id = response_data["job_id"]
            status = response_data.get("status", "unknown")
            error = response_data.get("error", "")

            # Print the response to the terminal
            if status == "success":
                logger.info(
                    f"\n\nJob {job_id} processed successfully.\ndata: {response_data}"
                )
            else:
                logger.error(f"Job {job_id} failed with error: {error}")

            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            logger.error(f"Error processing response: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag)

    # Set up the RabbitMQ channel to listen to the responses queue
    channel = get_rabbitmq_channel()
    channel.queue_declare(queue=RESPONSES_QUEUE)
    channel.basic_consume(queue=RESPONSES_QUEUE, on_message_callback=callback)

    logger.info("Waiting for responses. To exit press Ctrl+C")
    channel.start_consuming()
