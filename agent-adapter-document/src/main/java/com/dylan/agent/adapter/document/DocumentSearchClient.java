package com.dylan.agent.adapter.document;

import com.dylan.esquery.api.model.document.HybridSearchRequest;
import com.dylan.esquery.api.model.document.HybridSearchResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

@FeignClient(
        name = "es-query-service",
        path = "/es",
        contextId = "agent2document")
public interface DocumentSearchClient {

    @PostMapping(
            value = "/internal/document-search/hybrid",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    HybridSearchResponse documentHybridSearch(@RequestBody HybridSearchRequest request);

}
