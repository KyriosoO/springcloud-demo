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
import com.dylan.agent.capability.document.embedding.DisabledDocumentEmbeddingPort;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingPort;
import com.dylan.agent.capability.document.embedding.HttpDocumentEmbeddingClient;
import com.dylan.agent.capability.document.acl.DisabledDocumentAclScopePort;
import com.dylan.agent.capability.document.acl.DocumentAclScopePort;
import com.dylan.agent.capability.document.acl.HttpDocumentAclScopeClient;
import com.dylan.agent.capability.document.generation.DisabledDocumentGenerationPort;
import com.dylan.agent.capability.document.generation.DocumentCitationVerifier;
import com.dylan.agent.capability.document.generation.DocumentEvidenceContextPacker;
import com.dylan.agent.capability.document.generation.DocumentEvidencePreSecurityFilter;
import com.dylan.agent.capability.document.generation.DocumentGenerationPort;
import com.dylan.agent.capability.document.generation.HttpDocumentGenerationClient;
import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import com.dylan.agent.capability.document.rerank.DisabledDocumentRerankPort;
import com.dylan.agent.capability.document.rerank.DocumentRerankPort;
import com.dylan.agent.capability.document.rerank.HttpDocumentRerankClient;
import com.dylan.agent.capability.document.rewrite.DisabledDocumentQueryRewritePort;
import com.dylan.agent.capability.document.rewrite.DocumentQueryRewritePort;
import com.dylan.agent.capability.document.rewrite.RewriteCandidateNormalizer;
import com.dylan.agent.capability.document.rewrite.RuntimeDocumentQueryRewriteClient;
import com.dylan.agent.capability.document.security.DocumentRevocationGuard;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.definition.ContextWriteDeclaration;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.List;
import java.util.Set;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(prefix = "agent.kernel", name = "enabled", havingValue = "true")
@ConditionalOnProperty(prefix = "agent.document", name = "enabled", havingValue = "true")
public class DocumentCapabilityConfiguration {

    @Bean
    DocumentPlanValidator documentPlanValidator(
            AgentProperties properties,
            FilterNormalizer filterNormalizer,
            com.dylan.agent.planning.filter.FieldConstraintValidator fieldConstraintValidator,
            com.dylan.agent.metadata.domain.internal.DomainCatalogView domainCatalogView) {
        return new DocumentPlanValidator(properties, filterNormalizer, fieldConstraintValidator, domainCatalogView);
    }

    @Bean
    DocumentCapabilityHandler documentCapabilityHandler(
            AgentProperties properties,
            DocumentEmbeddingPort embeddingPort,
            DocumentAclScopePort aclScopePort,
            DocumentRevocationGuard revocationGuard,
            DocumentEvidencePreSecurityFilter preSecurityFilter,
            DocumentEvidenceContextPacker contextPacker,
            DocumentGenerationPort generationPort,
            DocumentCitationVerifier citationVerifier,
            DocumentRerankPort rerankPort,
            DocumentQueryRewritePort rewritePort,
            RewriteCandidateNormalizer rewriteCandidateNormalizer,
            DocumentRuleExtractor ruleExtractor,
            ObjectProvider<DocumentObservabilitySupport> observabilitySupport) {
        return new DocumentCapabilityHandler(
                properties,
                embeddingPort,
                aclScopePort,
                revocationGuard,
                preSecurityFilter,
                contextPacker,
                generationPort,
                citationVerifier,
                observabilitySupport.getIfAvailable(),
                rerankPort,
                rewritePort,
                rewriteCandidateNormalizer,
                ruleExtractor);
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
    DocumentQueryRewritePort documentQueryRewritePort(
            AgentProperties properties,
            @Qualifier("agentRuntimeRestClient") RestClient runtimeRestClient,
            ObjectMapper objectMapper) {
        if (!properties.getDocument().getRewrite().isEnabled()) {
            return new DisabledDocumentQueryRewritePort();
        }
        return new RuntimeDocumentQueryRewriteClient(runtimeRestClient, objectMapper, properties);
    }

    @Bean
    DocumentRerankPort documentRerankPort(
            AgentProperties properties,
            ObjectProvider<DocumentProviderAuthHeaderProvider> authHeaderProvider) {
        var rerank = properties.getDocument().getRerank();
        if (!rerank.isEnabled()) {
            return new DisabledDocumentRerankPort();
        }
        return new HttpDocumentRerankClient(
                restClient(rerank.getBaseUrl(), rerank.getTimeout()),
                authHeaderProvider.getObject(),
                rerank.getPath(),
                rerank.getModel(),
                rerank.isNormalize(),
                rerank.getMaxDocumentChars());
    }

    @Bean
    DocumentRevocationGuard documentRevocationGuard(AgentProperties properties) {
        return new DocumentRevocationGuard(properties);
    }

    @Bean
    @ConditionalOnBean(MeterRegistry.class)
    DocumentObservabilitySupport documentObservabilitySupport(MeterRegistry meterRegistry) {
        return new DocumentObservabilitySupport(meterRegistry);
    }

    @Bean
    DocumentAclScopePort documentAclScopePort(
            AgentProperties properties,
            ObjectProvider<DocumentProviderAuthHeaderProvider> authHeaderProvider) {
        var acl = properties.getDocument().getAcl();
        if (!acl.isEnabled() || acl.getScopeUrl() == null || acl.getScopeUrl().isBlank()) {
            return new DisabledDocumentAclScopePort();
        }
        return new HttpDocumentAclScopeClient(
                restClient(acl.getScopeUrl(), acl.getTimeout()),
                authHeaderProvider.getObject());
    }

    @Bean
    DocumentEmbeddingPort documentEmbeddingPort(
            AgentProperties properties,
            ObjectProvider<DocumentProviderAuthHeaderProvider> authHeaderProvider) {
        var embedding = properties.getDocument().getEmbedding();
        if (!embedding.isEnabled()) {
            return new DisabledDocumentEmbeddingPort();
        }
        return new HttpDocumentEmbeddingClient(
                restClient(embedding.getBaseUrl(), embedding.getTimeout()),
                authHeaderProvider.getObject());
    }

    @Bean
    @ConditionalOnBean(ServiceTokenProvider.class)
    DocumentProviderAuthHeaderProvider documentProviderAuthHeaderProvider(ServiceTokenProvider serviceTokenProvider) {
        return new DocumentProviderAuthHeaderProvider(serviceTokenProvider);
    }

    @Bean
    DocumentEvidencePreSecurityFilter documentEvidencePreSecurityFilter() {
        return new DocumentEvidencePreSecurityFilter();
    }

    @Bean
    DocumentEvidenceContextPacker documentEvidenceContextPacker() {
        return new DocumentEvidenceContextPacker();
    }

    @Bean
    DocumentGenerationPort documentGenerationPort(
            AgentProperties properties,
            ObjectProvider<DocumentProviderAuthHeaderProvider> authHeaderProvider) {
        var generation = properties.getDocument().getGeneration();
        if (!generation.isEnabled()) {
            return new DisabledDocumentGenerationPort();
        }
        return new HttpDocumentGenerationClient(
                restClient(generation.getBaseUrl(), generation.getTimeout()),
                authHeaderProvider.getObject());
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
                        .contextAccess(new ContextAccessDeclaration(
                                List.of(new ContextReadDeclaration(
                                        RuntimeContextType.DOCUMENT,
                                        AgentExecutionContracts.DOCUMENT_CONTEXT,
                                        DocumentCapabilityContextPayload.class,
                                        false,
                                        Set.of("operation", "domain", "queryText", "filters", "citationIds", "topK"))),
                                List.of(new ContextWriteDeclaration(
                                        RuntimeContextType.DOCUMENT,
                                        AgentExecutionContracts.DOCUMENT_CONTEXT,
                                        DocumentCapabilityContextPayload.class,
                                        Duration.ofDays(7),
                                        Set.of("operation", "domain", "queryText", "filters", "citationIds", "topK")))))
                        .build(),
                DocumentAgentPlan.class,
                validator,
                ValidatedDocumentPlan.class,
                handler,
                DocumentAgentResultPayload.class);
    }

    private RestClient restClient(String baseUrl, Duration timeout) {
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(timeout)
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(timeout);
        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }
}
