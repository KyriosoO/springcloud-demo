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
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.definition.ContextWriteDeclaration;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.planning.filter.FilterNormalizer;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

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
    DocumentCapabilityHandler documentCapabilityHandler() {
        return new DocumentCapabilityHandler();
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
}
