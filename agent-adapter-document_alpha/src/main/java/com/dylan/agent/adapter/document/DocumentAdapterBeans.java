package com.dylan.agent.adapter.document;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class DocumentAdapterBeans {

    @Bean
    DocumentRetrievalMapper documentRetrievalMapper() {
        return new DocumentRetrievalMapper();
    }

    @Bean
    DocumentEvidenceMapper documentEvidenceMapper() {
        return new DocumentEvidenceMapper();
    }

    @Bean
    DocumentRetrievalResponseBindingValidator documentRetrievalResponseBindingValidator() {
        return new DocumentRetrievalResponseBindingValidator();
    }
}
