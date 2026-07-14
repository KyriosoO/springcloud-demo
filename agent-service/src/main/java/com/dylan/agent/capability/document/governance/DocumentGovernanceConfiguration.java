package com.dylan.agent.capability.document.governance;
import com.dylan.agent.capability.document.governance.emergency.*;
import com.dylan.agent.capability.document.governance.provider.*;
import com.dylan.agent.capability.document.governance.validation.*;
import org.springframework.context.annotation.*;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import java.time.Clock;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;
@Configuration(proxyBeanMethods=false)
public class DocumentGovernanceConfiguration {
 @Bean com.dylan.common.security.BoundedRequestBodyFilter documentGovernanceRequestBodyFilter(){return new com.dylan.common.security.BoundedRequestBodyFilter("/internal/document-governance",64*1024L);}
 @Bean DocumentEmergencyControlReadPort documentEmergencyControlReadPort(JdbcTemplate jdbc,Clock clock){return new JdbcDocumentEmergencyControlRepository(jdbc,clock);}
 @Bean DocumentEmergencyControlService documentEmergencyControlService(JdbcTemplate jdbc,Clock clock,DocumentProviderActivationCoordinator providerActivations){return new DocumentEmergencyControlService(jdbc,clock,providerActivations);}
 @Bean DocumentProviderActivationReadView documentProviderActivationReadView(JdbcTemplate jdbc,Clock clock,com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer canonicalizer){return new JdbcDocumentProviderActivationReadView(jdbc,clock,canonicalizer);}
 @Bean DocumentProviderActivationPublisher documentProviderActivationPublisher(JdbcTemplate jdbc,Clock clock,com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer canonicalizer){return new DocumentProviderActivationPublisher(jdbc,clock,canonicalizer);}
 @Bean DocumentProviderActivationCoordinator documentProviderActivationCoordinator(JdbcTemplate jdbc,Clock clock,com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer canonicalizer){return new DocumentProviderActivationCoordinator(jdbc,clock,java.time.Duration.ofMinutes(2),canonicalizer);}
 @Bean JdbcDocumentValidationReportRepository documentValidationReportRepository(JdbcTemplate jdbc,com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer canonicalizer){return new JdbcDocumentValidationReportRepository(jdbc,canonicalizer);}
 @Bean DocumentReleaseGateEvaluator documentReleaseGateEvaluator(JdbcDocumentValidationReportRepository reports,Clock clock){return new DocumentReleaseGateEvaluator(reports,clock,java.time.Duration.ofMinutes(2));}
 @Bean com.dylan.agent.capability.document.governance.management.DocumentManagementAuthorizationContextResolver documentManagementAuthorizationContextResolver(
         @Value("${agent.document.governance.security.allowed-service-subjects:}") String allowedSubjects){
     Set<String> subjects=Arrays.stream(allowedSubjects.split(",")).map(String::trim).filter(value->!value.isEmpty()).collect(Collectors.toUnmodifiableSet());
     return new com.dylan.agent.capability.document.governance.management.JwtDocumentManagementAuthorizationContextResolver(subjects);
 }
 @Bean
 @org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean(com.dylan.agent.capability.document.governance.management.DocumentApprovalEvidencePort.class)
 com.dylan.agent.capability.document.governance.management.DocumentApprovalEvidencePort documentApprovalEvidencePort(){
     return new com.dylan.agent.capability.document.governance.management.FailClosedDocumentApprovalEvidencePort();
 }
 @Bean
 @org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean(DocumentEmergencyResolutionEvidencePort.class)
 DocumentEmergencyResolutionEvidencePort documentEmergencyResolutionEvidencePort(){return new FailClosedDocumentEmergencyResolutionEvidencePort();}
 @Bean
 @org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean(DocumentProviderConsumerCoveragePort.class)
 DocumentProviderConsumerCoveragePort documentProviderConsumerCoveragePort(){return new FailClosedDocumentProviderConsumerCoveragePort();}
 @Bean DocumentProviderManagementService documentProviderManagementService(JdbcTemplate jdbc,Clock clock,
         JdbcDocumentValidationReportRepository reports,DocumentReleaseGateEvaluator gates,
         DocumentProviderActivationCoordinator coordinator,
         com.dylan.agent.capability.document.governance.management.DocumentApprovalEvidencePort approvals,
         DocumentProviderConsumerCoveragePort coverage){
     return new DocumentProviderManagementService(jdbc,clock,reports,gates,coordinator,approvals,coverage);
 }
 @Bean DocumentEmergencyGateEvidenceIssuer documentEmergencyGateEvidenceIssuer(
         DocumentEmergencyControlReadPort readPort,
         ObjectProvider<com.dylan.common.security.IntegritySigningKeyProvider> signingKeys,
         Clock clock,
         @Value("${agent.document.governance.security.evidence-key-id:document-governance}") String keyId,
         @Value("${agent.document.governance.security.evidence-key-version:unconfigured}") String keyVersion){
     com.dylan.common.security.IntegritySigningKeyProvider failClosed=ref->{throw new IllegalStateException("document governance signing key is unavailable");};
     return new DefaultDocumentEmergencyGateEvidenceIssuer(readPort,signingKeys.getIfAvailable(()->failClosed),
             new com.dylan.common.security.IntegrityKeyRef(keyId,keyVersion),clock,java.time.Duration.ofSeconds(30));
 }
}
