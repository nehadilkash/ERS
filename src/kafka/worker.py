import json
import logging
import requests
from datetime import datetime, timezone
from kafka import KafkaConsumer
from kafka.errors import KafkaError

# Configure logging for the worker
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("KafkaLogWorker")

# Configuration
KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]
KAFKA_TOPIC_PATTERN = "ecommerce.*"  # Subscribes to any topic starting with ecommerce. (or use a specific topic name)
FASTAPI_INGEST_URL = "http://127.0.0.1:8000/ingest"

def extract_generic_log_fields(event: dict, topic: str) -> dict:
    """
    Generic extractor: dynamically discovers service name, severity, timestamp, 
    and message from any incoming event schema without hardcoding.
    """
    # 1. Dynamically find service name (checks common keys, falls back to Kafka topic name)
    service_name = (
        event.get("service_name") 
        or event.get("service") 
        or event.get("app") 
        or event.get("source")
    )
    if not service_name and topic:
        # e.g., topic "ecommerce.payment" -> "payment"
        parts = topic.split(".")
        service_name = parts[-1] if len(parts) > 1 else topic
    service_name = str(service_name or "dynamic-service").lower()

    # 2. Dynamically find severity/log level
    severity = (
        event.get("severity") 
        or event.get("level") 
        or event.get("log_level") 
        or "INFO"
    ).upper()

    # Normalize standard log levels if mapped differently
    severity_map = {"WARN": "WARNING", "ERR": "ERROR", "FATAL": "CRITICAL"}
    severity = severity_map.get(severity, severity)
    if severity not in ["CRITICAL", "ERROR", "WARNING", "INFO"]:
        severity = "INFO"

    # 3. Dynamically find message or payload description
    message = (
        event.get("message") 
        or event.get("msg") 
        or event.get("error") 
        or event.get("description")
        or json.dumps(event)  # Fallback: serialize entire event if no message field exists
    )

    # 4. Dynamically find timestamp
    timestamp = (
        event.get("timestamp") 
        or event.get("time") 
        or event.get("created_at") 
        or datetime.now(timezone.utc).isoformat()
    )

    return {
        "timestamp": timestamp,
        "severity": severity,
        "service_name": service_name,
        "message": message
    }

def start_kafka_consumer():
    logger.info(f"Connecting to Kafka brokers at {KAFKA_BOOTSTRAP_SERVERS}...")
    
    try:
        # Using regex to subscribe to dynamic topics (e.g., ecommerce.orders, ecommerce.auth, etc.)
        consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='ers-log-ingest-group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        consumer.subscribe(pattern=KAFKA_TOPIC_PATTERN)
        logger.info(f"Successfully subscribed to Kafka topics matching pattern: '{KAFKA_TOPIC_PATTERN}'")

        for message in consumer:
            topic = message.topic
            raw_event = message.value
            
            logger.debug(f"Received event from topic '{topic}': {raw_event}")

            # Handle both single event dicts or batched lists from Kafka
            events_list = raw_event if isinstance(raw_event, list) else [raw_event]
            
            formatted_logs = []
            for ev in events_list:
                if isinstance(ev, dict):
                    normalized_log = extract_generic_log_fields(ev, topic)
                    formatted_logs.append(normalized_log)

            if formatted_logs:
                payload = {"logs": formatted_logs}
                try:
                    response = requests.post(FASTAPI_INGEST_URL, json=payload, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"📥 Forwarded {len(formatted_logs)} event(s) from [{topic}] to ERS RAG.")
                    else:
                        logger.error(f"⚠️ FastAPI ingestion failed [{response.status_code}]: {response.text}")
                except requests.exceptions.ConnectionError:
                    logger.error("❌ ERS FastAPI backend is offline. Retrying on next message...")

    except KafkaError as e:
        logger.error(f"Kafka connection error: {e}")
    except Exception as e:
        logger.error(f"Unexpected worker error: {e}")

if __name__ == "__main__":
    start_kafka_consumer()