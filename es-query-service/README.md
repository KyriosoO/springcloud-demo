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

The Elasticsearch connection is expected from `configServer/src/main/resources/config/application-es.yml`.

## Query

```http
POST /es/indexes/{index}/search
Content-Type: application/json
```

The request body is raw Elasticsearch query DSL.

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
