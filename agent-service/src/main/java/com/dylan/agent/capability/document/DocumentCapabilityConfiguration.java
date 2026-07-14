package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingPort;
import com.dylan.agent.capability.document.acl.*;
import com.dylan.agent.capability.document.generation.DocumentCitationVerifier;
import com.dylan.agent.capability.document.generation.DocumentGenerationEvidenceProjector;
import com.dylan.agent.capability.document.generation.DocumentGenerationInputProjector;
import com.dylan.agent.capability.document.generation.EvidenceContextPackageFactory;
import com.dylan.agent.capability.document.generation.DocumentGenerationPort;
import com.dylan.agent.capability.document.generation.DocumentGeneratedTextCandidateFactory;
import com.dylan.agent.capability.document.evidence.DocumentEvidenceVisibilityProjector;
import com.dylan.agent.capability.document.provider.DocumentProviderAdapterClient;
import com.dylan.agent.capability.document.provider.DocumentProviderAdapterProperties;
import com.dylan.agent.capability.document.provider.DocumentProviderOperationRequestBinder;
import com.dylan.agent.capability.document.provider.DocumentProviderOutboundPolicyReferenceVerifier;
import com.dylan.agent.capability.document.provider.DocumentProviderOperationBindingRegistry;
import com.dylan.agent.capability.document.provider.security.DocumentProviderOutboundFieldProjector;
import com.dylan.agent.capability.document.provider.security.DocumentProviderOutboundPolicyCanonicalizer;
import com.dylan.agent.capability.document.provider.security.DocumentProviderOutboundPolicyDecisionFactory;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer;
import com.dylan.agent.capability.document.governance.provider.DocumentProviderActivationReadView;
import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import com.dylan.agent.capability.document.rerank.DocumentRerankPort;
import com.dylan.agent.capability.document.rewrite.DocumentQueryRewritePort;
import com.dylan.agent.capability.document.rewrite.RewriteCandidateNormalizer;
import com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjector;
import com.dylan.agent.capability.document.profile.DocumentProfileAssetRegistry;
import com.dylan.agent.capability.document.profile.DocumentPolicyConstraintRegistry;
import com.dylan.agent.capability.document.profile.DocumentRetrievalProfileResolver;
import com.dylan.agent.capability.document.security.DocumentRevocationGuard;
import com.dylan.agent.capability.document.governance.emergency.DocumentEmergencyControlReadPort;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.definition.ContextWriteDeclaration;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.resource.DocumentResourceLimits;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.metadata.result.ResultValueMaskingSupport;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;
import java.time.Clock;
import java.util.List;
import java.util.Set;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(prefix = "agent.kernel", name = "enabled", havingValue = "true")
@org.springframework.boot.context.properties.EnableConfigurationProperties(DocumentProviderAdapterProperties.class)
public class DocumentCapabilityConfiguration {

    @Bean
    DocumentRetrievalProfileResolver documentRetrievalProfileResolver(
            DocumentProfileAssetRegistry profileRegistry,
            DocumentPolicyConstraintRegistry policyRegistry) {
        return new DocumentRetrievalProfileResolver(profileRegistry, policyRegistry);
    }

    @Bean
    DocumentPlanningProfileProjector documentPlanningProfileProjector() {
        return new DocumentPlanningProfileProjector();
    }

    @Bean
    com.dylan.agent.planning.PlanningArtifactAssembler documentPlanningArtifactAssembler(
            DocumentRetrievalProfileResolver profiles,
            DocumentPlanningProfileProjector projector,
            ObjectMapper mapper) {
        return new DocumentPlanningArtifactAssembler(profiles, projector, mapper);
    }

    @Bean
    DocumentPlanValidator documentPlanValidator(
            FilterNormalizer filterNormalizer,
            com.dylan.agent.planning.filter.FieldConstraintValidator fieldConstraintValidator) {
        return new DocumentPlanValidator(filterNormalizer, fieldConstraintValidator);
    }

    @Bean
    DocumentCapabilityHandler documentCapabilityHandler(
            DocumentEmbeddingPort embeddingPort,
            DocumentAclScopePort aclScopePort,
            DocumentAclCurrentnessPort aclCurrentnessPort,
            DocumentRevocationGuard revocationGuard,
            DocumentEvidenceVisibilityProjector visibilityProjector,
            DocumentGenerationEvidenceProjector generationEvidenceProjector,
            EvidenceContextPackageFactory evidenceContextPackageFactory,
            DocumentGeneratedTextCandidateFactory generatedTextCandidateFactory,
            DocumentGenerationInputProjector generationInputProjector,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier,
            DocumentRerankPort rerankPort,
            DocumentQueryRewritePort rewritePort,
            RewriteCandidateNormalizer rewriteCandidateNormalizer,
            DocumentRuleExtractor ruleExtractor,
            DocumentProviderOperationRequestBinder providerRequestBinder,
            DocumentProviderOutboundPolicyDecisionFactory providerPolicyDecisionFactory,
            DocumentProviderOutboundFieldProjector providerFieldProjector,
            DocumentProtectedFilterFactory protectedFilterFactory,
            ObjectMapper objectMapper,
            ObjectProvider<DocumentObservabilitySupport> observabilitySupport) {
        return new DocumentCapabilityHandler(
                embeddingPort,
                aclScopePort,
                aclCurrentnessPort,
                revocationGuard,
                visibilityProjector,
                generationEvidenceProjector,
                evidenceContextPackageFactory,
                generatedTextCandidateFactory,
                generationInputProjector,
                generationPort,
                citationVerifier,
                observabilitySupport.getIfAvailable(),
                rerankPort,
                rewritePort,
                rewriteCandidateNormalizer,
                ruleExtractor,
                providerRequestBinder,
                providerPolicyDecisionFactory,
                providerFieldProjector,
                protectedFilterFactory,
                objectMapper);
    }

    @Bean
    DocumentRuleExtractor documentRuleExtractor() {
        return new DocumentRuleExtractor();
    }

    @Bean
    RewriteCandidateNormalizer rewriteCandidateNormalizer() {
        return new RewriteCandidateNormalizer();
    }

    @Bean
    DocumentProviderCanonicalizer documentProviderCanonicalizer(ObjectMapper objectMapper) {
        return new DocumentProviderCanonicalizer(objectMapper);
    }

    @Bean
    DocumentProviderOperationRequestBinder documentProviderOperationRequestBinder(
            DocumentProviderCanonicalizer canonicalizer,
            Clock clock) {
        return new DocumentProviderOperationRequestBinder(canonicalizer, clock);
    }

    @Bean
    DocumentProviderOutboundPolicyCanonicalizer documentProviderOutboundPolicyCanonicalizer() {
        return new DocumentProviderOutboundPolicyCanonicalizer();
    }

    @Bean
    DocumentProviderOutboundPolicyDecisionFactory documentProviderOutboundPolicyDecisionFactory(
            DocumentProviderOutboundPolicyCanonicalizer canonicalizer,
            Clock clock) {
        return new DocumentProviderOutboundPolicyDecisionFactory(canonicalizer, clock);
    }

    @Bean
    DocumentProviderOutboundFieldProjector documentProviderOutboundFieldProjector(
            ResultValueMaskingSupport masking) {
        return new DocumentProviderOutboundFieldProjector(masking);
    }

    @Bean
    DocumentProviderOutboundPolicyReferenceVerifier documentProviderOutboundPolicyReferenceVerifier(
            DocumentProviderOperationRequestBinder binder,
            Clock clock) {
        return new DocumentProviderOutboundPolicyReferenceVerifier(binder, clock);
    }

    @Bean
    DocumentGeneratedTextCandidateFactory documentGeneratedTextCandidateFactory(
            DocumentProviderOperationRequestBinder binder,
            DocumentProviderOperationBindingRegistry operationBindingRegistry) {
        return new DocumentGeneratedTextCandidateFactory(binder, operationBindingRegistry);
    }

    @Bean
    DocumentProviderOperationBindingRegistry documentProviderOperationBindingRegistry(Clock clock) {
        return new DocumentProviderOperationBindingRegistry(clock);
    }

    @Bean
    DocumentProviderAdapterClient documentProviderAdapterClient(
            DocumentProviderAdapterProperties properties,
            DocumentProviderAuthHeaderProvider authHeaderProvider,
            DocumentProviderActivationReadView activationReadView,
            DocumentProviderOperationRequestBinder binder,
            DocumentProviderOutboundPolicyReferenceVerifier referenceVerifier,
            DocumentProviderOperationBindingRegistry operationBindingRegistry,
            Clock clock,
            ObjectMapper objectMapper) {
        return new DocumentProviderAdapterClient(
                 restClient(properties.getBaseUrl(), properties.getConnectTimeout(), properties.getReadTimeout()),
                 authHeaderProvider, activationReadView, binder, referenceVerifier,
                 operationBindingRegistry, clock, objectMapper,
                 properties.getMaxRequestBytes(), properties.getMaxResponseBytes(),
                 properties.getConnectTimeout().plus(properties.getReadTimeout()));
    }

    @Bean
    DocumentRevocationGuard documentRevocationGuard(
            DocumentAclCurrentnessPort currentnessPort,
            DocumentEmergencyControlReadPort emergencyControlReadPort,
            Clock clock,
            AgentProperties properties,
            DocumentAclCompilerLimits limits) {
        return new DocumentRevocationGuard(currentnessPort, emergencyControlReadPort, clock,
                properties.getDocument().getAcl().getFinalDecisionMaxAge(), limits);
    }

    @Bean
    @ConditionalOnBean(MeterRegistry.class)
    DocumentObservabilitySupport documentObservabilitySupport(MeterRegistry meterRegistry) {
        return new DocumentObservabilitySupport(meterRegistry);
    }

    @Bean
    DocumentAclScopePort documentAclScopePort(
            AgentProperties properties,
            DocumentAclAuthorityCredentialProvider credentialProvider,
            ObjectMapper objectMapper,
            Clock clock,
            DocumentAclCompilerLimits limits) {
        var acl = properties.getDocument().getAcl();
        return new HttpDocumentAclScopeClient(
                restClient(acl.getScopeUrl(), acl.getTimeout()),
                credentialProvider, objectMapper, clock, limits);
    }

    @Bean
    DocumentAclCurrentnessPort documentAclCurrentnessPort(
            AgentProperties properties,
            DocumentAclAuthorityCredentialProvider credentialProvider,
            ObjectMapper objectMapper,
            Clock clock,
            DocumentAclCompilerLimits limits) {
        var acl = properties.getDocument().getAcl();
        return new HttpDocumentAclCurrentnessClient(
                restClient(acl.getScopeUrl(), acl.getTimeout()),
                credentialProvider, objectMapper, clock, limits);
    }

    @Bean
    DocumentAclCompilerLimits documentAclCompilerLimits(AgentProperties properties) {
        var acl = properties.getDocument().getAcl();
        return new DocumentAclCompilerLimits(
                acl.getMaxDepartments(), acl.getMaxRoles(), acl.getMaxAttributes(),
                acl.getMaxAllowedDocumentIds(), acl.getMaxDeniedDocumentIds(),
                acl.getMaxAstNodes(), acl.getMaxAstDepth(), acl.getMaxTerms(),
                acl.getMaxCanonicalBytes(), acl.getMaxWireBytes(), acl.getMaxCurrentnessCandidates(),
                acl.getMaxAuthorityEvidenceTtl());
    }

    @Bean
    DocumentProtectedFilterFactory documentProtectedFilterFactory(DocumentAclCompilerLimits limits) {
        return new DocumentProtectedFilterFactory(limits);
    }

    @Bean
    @ConditionalOnBean(ServiceTokenProvider.class)
    DocumentAclAuthorityCredentialProvider documentAclAuthorityCredentialProvider(
            ServiceTokenProvider serviceTokenProvider) {
        return new DocumentAclAuthorityCredentialProvider(serviceTokenProvider);
    }

    @Bean
    @ConditionalOnBean(ServiceTokenProvider.class)
    DocumentProviderAuthHeaderProvider documentProviderAuthHeaderProvider(ServiceTokenProvider serviceTokenProvider) {
        return new DocumentProviderAuthHeaderProvider(serviceTokenProvider);
    }

    @Bean
    DocumentEvidenceVisibilityProjector documentEvidenceVisibilityProjector(
            ResultValueMaskingSupport masking) {
        return new DocumentEvidenceVisibilityProjector(masking);
    }

    @Bean
    DocumentGenerationEvidenceProjector documentGenerationEvidenceProjector(
            DocumentProviderOutboundFieldProjector fieldProjector) {
        return new DocumentGenerationEvidenceProjector(fieldProjector);
    }

    @Bean
    EvidenceContextPackageFactory evidenceContextPackageFactory() {
        return new EvidenceContextPackageFactory();
    }

    @Bean
    DocumentGenerationInputProjector documentGenerationInputProjector() {
        return new DocumentGenerationInputProjector();
    }

    @Bean
    DocumentCitationVerifier documentCitationVerifier() {
        return new DocumentCitationVerifier();
    }

    @Bean
    CapabilityRegistration<DocumentAgentPlan, ValidatedDocumentPlan, DocumentAgentResultPayload>
    documentSearchRegistration(DocumentPlanValidator validator, DocumentCapabilityHandler handler) {
        return registration(
                DocumentCapabilityIds.SEARCH,
                "Search authorized document evidence with keyword/vector-ready retrieval.",
                List.of("document search", "policy lookup", "knowledge base lookup"),
                List.of("write", "unverified summary"),
                validator,
                handler);
    }

    @Bean
    CapabilityRegistration<DocumentAgentPlan, ValidatedDocumentPlan, DocumentAgentResultPayload>
    documentAnswerRegistration(DocumentPlanValidator validator, DocumentCapabilityHandler handler) {
        return registration(
                DocumentCapabilityIds.ANSWER,
                "Answer questions using authorized document evidence and citations.",
                List.of("document question", "policy answer", "knowledge base answer"),
                List.of("write", "answer without citations"),
                validator,
                handler);
    }

    @Bean
    CapabilityRegistration<DocumentAgentPlan, ValidatedDocumentPlan, DocumentAgentResultPayload>
    documentSummarizeRegistration(DocumentPlanValidator validator, DocumentCapabilityHandler handler) {
        return registration(
                DocumentCapabilityIds.SUMMARIZE,
                "Summarize authorized document evidence with citations.",
                List.of("document summary", "policy summary", "knowledge base summary"),
                List.of("write", "summary without citations"),
                validator,
                handler);
    }

    private CapabilityRegistration<DocumentAgentPlan, ValidatedDocumentPlan, DocumentAgentResultPayload> registration(
            String capabilityId,
            String description,
            List<String> applicability,
            List<String> exclusions,
            DocumentPlanValidator validator,
            DocumentCapabilityHandler handler) {
        return new CapabilityRegistration<>(
                CapabilityDefinition.builder()
                        .capabilityId(capabilityId)
                        .planKind(AgentPlanKind.DOCUMENT)
                        .routingDescriptor(new CapabilityRoutingDescriptor(description, applicability, exclusions))
                        .domainMode(AgentDomainMode.REQUIRED)
                        .adapterRole(AdapterRole.DOCUMENT_RETRIEVABLE)
                        .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                        .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                        .inputContract(AgentExecutionContracts.DOCUMENT_PLAN)
                        .outputContract(AgentExecutionContracts.DOCUMENT_RESULT)
                        .resourceLimitDeclaration(DocumentResourceLimits.declaration(
                                DocumentResourceLimits.intrinsicFor(capabilityId)))
                        .resourceLimitConsumers(DocumentResourceLimits.consumers(capabilityId))
                        .contextAccess(new ContextAccessDeclaration(
                                List.of(new ContextReadDeclaration(
                                        RuntimeContextType.DOCUMENT,
                                        AgentExecutionContracts.DOCUMENT_CONTEXT,
                                        DocumentCapabilityContextPayload.class,
                                        false,
                                        Set.of("operation", "domain", "materialType", "queryText", "filters", "topK", "summaryScope"))),
                                List.of(new ContextWriteDeclaration(
                                        RuntimeContextType.DOCUMENT,
                                        AgentExecutionContracts.DOCUMENT_CONTEXT,
                                        DocumentCapabilityContextPayload.class,
                                        Duration.ofDays(7),
                                        Set.of("operation", "domain", "materialType", "queryText", "filters", "topK", "summaryScope")))))
                        .build(),
                DocumentAgentPlan.class,
                validator,
                ValidatedDocumentPlan.class,
                handler,
                DocumentAgentResultPayload.class);
    }

    private RestClient restClient(String baseUrl, Duration timeout) {
        return restClient(baseUrl, timeout, timeout);
    }

    private RestClient restClient(String baseUrl, Duration connectTimeout, Duration readTimeout) {
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(connectTimeout)
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(readTimeout);
        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }
}
