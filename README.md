1. Authentication
OAuth 2.0
JWT Authentication: Secures microservices with JSON Web Tokens.

2. API Gateway
Sentinel Token Bucket Mode: Controls traffic with token-based rate limiting.
Rate Limiting: Protects services from overload.
Load Balancing: Distributes requests across multiple service instances.

3. Service-to-Service Communication (Feign)
Resilience4j Integration:
Retry
Circuit Breaker
Rate Limiting

4. Service Discovery
Eureka: Automatically detects and registers service instances for dynamic discovery.

5. RocketMQ
Asynchronous Message-Driven Persistence: Handles high-throughput data writes asynchronously.
Batch Replay: Supports replaying messages in batches.
Order Dispatch: Manages the delivery of order messages reliably.

6. Kafka
Asynchronous Message-Driven Persistence: Similar to RocketMQ, supports asynchronous persistence.
Batch Replay: Enables replaying messages in batches for data consistency or recovery.
