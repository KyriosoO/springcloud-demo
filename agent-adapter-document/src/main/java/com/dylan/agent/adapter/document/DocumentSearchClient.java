package com.dylan.agent.adapter.document;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

@FeignClient(
        name = "es-query-service",
        path = "/es",
        contextId = "agent2document")
public interface DocumentSearchClient {

    @PostMapping(
            value = "/indexes/{index}/search",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    String search(@PathVariable("index") String index, @RequestBody String queryDsl);
}
