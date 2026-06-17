# Employee Service

`employee-service` owns the `employee` table and delegates all Elasticsearch operations to `es-query-service`.

## Database

The service imports datasource settings from Config Server:

```yaml
spring:
  config:
    import: optional:configserver:http://localhost:9888
  profiles:
    active: datasource
```

## Table APIs

```http
GET    /employees?page=1&size=20
GET    /employees/{idCardNo}
GET    /employees/count
POST   /employees
PUT    /employees/{idCardNo}
DELETE /employees/{idCardNo}
```

## ES APIs

```http
POST /employees/es/search
POST /employees/es/documents/{idCardNo}
DELETE /employees/es/documents/{idCardNo}
POST /employees/es/bulk?page=1&size=500
POST /employees/es/rebuild/full
POST /employees/es/rebuild/incremental
GET  /employees/es/rebuild/tasks/{taskId}
GET  /employees/es/rebuild/tasks
```

The ES document uses these searchable fields:

```json
{
  "idCardNo": "...",
  "chineseName": "...",
  "contactAddress": "..."
}
```

The service also exposes an internal source endpoint for rebuild jobs:

```http
GET /internal/es/employees?cursor=0&batchSize=500&since=2026-01-01
```

## ES Sync Events

`POST /employees`, `PUT /employees/{idCardNo}`, and `DELETE /employees/{idCardNo}` publish employee change events to Kafka.
`employee-service` consumes the same topic and refreshes Elasticsearch asynchronously:

- `UPSERT`: rebuilds the single employee document with the configured embedding field.
- `DELETE`: deletes the single employee document from the ES index.

Config Server profile `application-emp.yml` provides:

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092

employee:
  kafka:
    change-topic: employee-change-topic
    es-sync-group: employee-es-sync-group
```
