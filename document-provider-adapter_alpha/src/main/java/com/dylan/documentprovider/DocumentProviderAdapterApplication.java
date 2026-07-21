package com.dylan.documentprovider;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication
@org.springframework.scheduling.annotation.EnableScheduling
@org.springframework.boot.context.properties.EnableConfigurationProperties({
        DocumentProviderActivationFeedProperties.class,
        DocumentProviderOperationProperties.class})
public class DocumentProviderAdapterApplication {
    public static void main(String[] args){SpringApplication.run(DocumentProviderAdapterApplication.class,args);}
    @Bean DocumentProviderCanonicalizer documentProviderCanonicalizer(ObjectMapper mapper) {
        return new DocumentProviderCanonicalizer(mapper);
    }
    @Bean java.time.Clock documentProviderClock() { return java.time.Clock.systemUTC(); }
}
