package com.dylan.esquery.config;

import org.apache.http.HttpHost;
import org.apache.http.auth.AuthScope;
import org.apache.http.auth.UsernamePasswordCredentials;
import org.apache.http.impl.client.BasicCredentialsProvider;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

@Configuration
@EnableConfigurationProperties(EsClientProperties.class)
public class EsClientConfiguration {
    @Bean
    @Primary
    @Qualifier("genericRestClient")
    RestClient genericRestClient(EsClientProperties properties) {
        properties.validate();
        return create(properties.getGeneric());
    }

    @Bean
    @Qualifier("documentRestClient")
    RestClient documentRestClient(EsClientProperties properties) {
        properties.validate();
        return create(properties.getDocument());
    }

    private static RestClient create(EsClientProperties.Endpoint endpoint) {
        HttpHost[] hosts = endpoint.getUris().stream().map(HttpHost::create).toArray(HttpHost[]::new);
        var builder = RestClient.builder(hosts);
        if (endpoint.getUsername() != null && !endpoint.getUsername().isBlank()) {
            BasicCredentialsProvider credentials = new BasicCredentialsProvider();
            credentials.setCredentials(AuthScope.ANY,
                    new UsernamePasswordCredentials(endpoint.getUsername(), endpoint.getPassword()));
            builder.setHttpClientConfigCallback(client -> client.setDefaultCredentialsProvider(credentials));
        }
        return builder.build();
    }
}
