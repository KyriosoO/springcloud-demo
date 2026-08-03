package com.dylan.mqprocedureserver.config;

import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import com.dylan.mqprocedureserver.web.TransactionSearchRequestDeserializer;
import com.dylan.transaction.api.query.TransactionSearchRequest;

@Configuration(proxyBeanMethods = false)
public class TransactionSearchJsonConfiguration {

	@Bean
	Jackson2ObjectMapperBuilderCustomizer transactionSearchRequestJsonCustomizer() {
		return builder -> builder.deserializerByType(
				TransactionSearchRequest.class, new TransactionSearchRequestDeserializer());
	}
}
