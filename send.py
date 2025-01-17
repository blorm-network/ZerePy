#!/usr/bin/env python
import pika, os
from dotenv import load_dotenv

load_dotenv()

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=os.getenv("RABBITMQ_HOST"),port=5672))
channel = connection.channel()

channel.queue_declare(queue='hello')

channel.basic_publish(exchange='', routing_key='stuff', body='Hello World!')
print(" [x] Sent 'Hello World!'")
connection.close()