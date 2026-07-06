package com.dylan.agent.adapter.document;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class DocumentAdapterBeans {

    @Bean
    DocumentRetrievalMapper documentRetrievalMapper(ObjectMapper objectMapper) {
        return new DocumentRetrievalMapper(objectMapper);
    }

    @Bean
    DocumentEvidenceMapper documentEvidenceMapper(
            ObjectMapper objectMapper,
            DocumentAdapterProperties properties) {
        return new DocumentEvidenceMapper(objectMapper, properties);
    }
}
