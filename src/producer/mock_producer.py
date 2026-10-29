import json
import random
from datetime import datetime, timezone
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configuration
KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]

# Mock pool of random services, apps, and varying log messages to ensure generic discovery
SERVICES_POOL = [
    {"service": "auth-service", "app": "iam-oauth-v2"},
    {"service": "payment-api", "app": "stripe-wrapper-svc"},
    {"service": "order-service", "app": "checkout-core"},
    {"service": "inventory-service", "app": "warehouse-sync"}
]

SEVERITIES = ["INFO", "WARNING", "ERROR", "CRITICAL"]

MESSAGES_POOL = [
    "Database connection pool exhausted temporarily.",
    "SQL Injection attempt detected on /api/login endpoint.",
    "Unauthorized token signature presented in header.",
    "Payment gateway timed out during transaction settlement.",
    "Successfully processed checkout payload for user session.",
    "Rate limit threshold crossed for IP address range.",
    "Inventory lock failed due to concurrent race condition."
]

def generate_random_events(count=100):
    """Generates a list of diverse mock events across different apps and services."""
    events = []
    for _ in range(count):
        service_info = random.choice(SERVICES_POOL)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_name": service_info["service"],
            "app_name": service_info["app"],
            "severity": random.choice(SEVERITIES),
            "message": random.choice(MESSAGES_POOL),
            "metadata": {
                "datacenter": random.choice(["us-east-1", "eu-west-1", "ap-south-1"]),
                "request_id": f"req-{random.randint(10000, 99999)}"
            }
        }
        events.append(event)
    return events

def push_batch_to_kafka():
    print(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Generate 100 random events
        batch_events = generate_random_events(100)
        print(f"🚀 Generated {len(batch_events)} random events across mixed services/apps.")

        # Push them dynamically distributed across different Kafka topics
        for event in batch_events:
            # Dynamically route topic based on the service name
            topic_name = f"ecommerce.{event['service_name']}"
            
            # Send event asynchronously to Kafka
            producer.send(topic_name, value=event)

        # Ensure all messages are flushed and sent over the network
        producer.flush()
        producer.close()
        
        print(f"✅ Successfully pushed 100 events to Kafka topics (e.g., ecommerce.auth-service, ecommerce.payment-api, etc.)!")

    except KafkaError as e:
        print(f"❌ Failed to connect or publish to Kafka: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    push_batch_to_kafka()