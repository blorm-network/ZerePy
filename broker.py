import pika, sys, os, json,time
from dotenv import load_dotenv
from src.agent import ZerePyAgent

def validate_message_data(data):
    required_fields = ["connection", "action", "args"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")

def main():
    load_dotenv()
    agent = ZerePyAgent("example")

    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv("RABBITMQ_HOST"), port=5672))
            break
        except pika.exceptions.AMQPConnectionError as e:
            print(f" [!] Connection to RabbitMQ failed. Retrying in 5 seconds... {e}")
            time.sleep(5)
    channel = connection.channel()

    channel.queue_declare(queue='stuff')

    def callback(ch, method, properties, body):
        print(f" [x] Received {body}")
        try:
            data = json.loads(body)
            validate_message_data(data)
            res = agent.perform_action(data['connection'], data['action'], data['args'])
            print(f" [x] Received {body}")
            print(f" [x] Sent {res}")
        except Exception as e:
            print(f" [x] Error: {e}")




    channel.basic_consume(queue='stuff', on_message_callback=callback, auto_ack=True)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
