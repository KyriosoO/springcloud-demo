package com.dylan.esquery.document.governance.management;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import java.time.Clock;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

@Configuration
public class DocumentIndexManagementConfiguration {
    @Bean com.dylan.common.security.BoundedRequestBodyFilter documentGovernanceRequestBodyFilter(){return new com.dylan.common.security.BoundedRequestBodyFilter("/internal/document-governance",64*1024L);}
    @Bean DocumentManagementAuthorizationContextResolver documentManagementAuthorizationContextResolver(
            @Value("${es.document.governance.security.allowed-service-subjects:}") String subjects){
        Set<String> allowlist=Arrays.stream(subjects.split(",")).map(String::trim).filter(value->!value.isEmpty()).collect(Collectors.toUnmodifiableSet());
        return new JwtDocumentManagementAuthorizationContextResolver(allowlist);
    }
    @Bean @ConditionalOnMissingBean DocumentApprovalEvidencePort documentApprovalEvidencePort(){return new FailClosedDocumentApprovalEvidencePort();}
    @Bean @ConditionalOnMissingBean Clock documentGovernanceClock(){return Clock.systemUTC();}
}
