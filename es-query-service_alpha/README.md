# ES Query Service

This service provides generic Elasticsearch access without depending on business mappings or entity classes.

## Configuration

The service imports configuration from Spring Cloud Config:

```yaml
spring:
  config:
    import: optional:configserver:http://localhost:9888
  profiles:
    active: es
```

The Elasticsearch connection and default exact total-hits threshold are configured in
`config-service/src/main/resources/config/application-es.yml`:

```yaml
es:
  query:
    total-hits-threshold: 10000
```

## Query

```http
POST /es/indexes/{index}/search
Content-Type: application/json
```

The request body is raw Elasticsearch query DSL. When `track_total_hits` is absent or
`null`, the service injects the configured threshold. A caller-provided Elasticsearch
value takes precedence.

Both normal and vector searches return Elasticsearch's native total relation:

- `relation: "eq"` means the total is exact.
- `relation: "gte"` means the value is a lower bound.

## Index Documents

```http
PUT /es/indexes/{index}/documents
DELETE /es/indexes/{index}/documents/{id}
POST /es/indexes/{index}/bulk
```

Documents are generic JSON maps. No Java entity mapping is required.

## Rebuild

```http
POST /es/indexes/{index}/rebuild/full
POST /es/indexes/{index}/rebuild/incremental
GET  /es/rebuild/tasks/{taskId}
```

Rebuild requests pull pages from a business-owned `sourceUrl`. The source endpoint should return:

```json
{
  "documents": [],
  "hasMore": false,
  "nextCursor": null
}
```

The ES service only indexes the returned JSON documents; it does not know business tables or mappings.
