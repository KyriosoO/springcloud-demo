package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.provider.DocumentGenerationOperationRequest;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderFinishReason;
import com.dylan.agent.adapter.api.document.provider.DocumentUntrustedGenerationPayload;
import com.dylan.agent.adapter.api.operation.CapabilityOperationOutcome;
import com.dylan.agent.adapter.api.operation.CapabilityOperationSuccess;
import com.dylan.agent.adapter.api.operation.CapabilityOperationTermination;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.capability.document.provider.DocumentProviderOperationRequestBinder;
import com.dylan.agent.capability.document.provider.DocumentProviderOperationBindingRegistry;
import com.dylan.agent.kernel.infrastructure.CandidateCitationReference;
import com.dylan.agent.kernel.infrastructure.CandidateEvidenceReference;
import com.dylan.agent.kernel.infrastructure.CandidateSecurityBinding;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 将 untrusted generation outcome 提升为 trusted local candidate 的唯一工厂。 */
public final class DocumentGeneratedTextCandidateFactory {
    private static final Pattern MARKER = Pattern.compile("\\[(C[1-9][0-9]{0,9})]");
    private static final com.dylan.agent.api.contract.common.ContractRef EVIDENCE_CONTRACT =
            AgentExecutionContracts.ref("EvidenceContextPackage", "1.0.0");

    private final DocumentProviderOperationRequestBinder binder;
    private final DocumentProviderOperationBindingRegistry operationBindingRegistry;

    public DocumentGeneratedTextCandidateFactory(
            DocumentProviderOperationRequestBinder binder,
            DocumentProviderOperationBindingRegistry operationBindingRegistry) {
        this.binder = Objects.requireNonNull(binder, "binder must not be null");
        this.operationBindingRegistry = Objects.requireNonNull(
                operationBindingRegistry, "operationBindingRegistry must not be null");
    }

    public DocumentGeneratedTextCandidate create(
            EvidenceContextPackage evidencePackage,
            DocumentGenerationOperationRequest request,
            CapabilityOperationOutcome<DocumentUntrustedGenerationPayload> outcome,
            ValidatedDocumentPlan plan,
            ExecutionScope scope,
            EffectiveCapabilityResourceLimits effectiveLimits) {
        Objects.requireNonNull(evidencePackage, "evidencePackage must not be null");
        Objects.requireNonNull(request, "request must not be null");
        Objects.requireNonNull(plan, "plan must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        Objects.requireNonNull(effectiveLimits, "effectiveLimits must not be null");
        if (!(outcome instanceof CapabilityOperationSuccess<DocumentUntrustedGenerationPayload> success)) {
            throw new IllegalArgumentException("generation outcome must be successful");
        }
        var context = request.operationContext();
        var reference = request.outboundPolicyReference();
        var metadata = success.metadata();
        DocumentResourceLimit limits = effectiveLimits.require(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
        if (!context.invocationId().equals(scope.invocationId())
                || !context.requestCorrelationId().equals(scope.requestCorrelationId())
                || !context.capabilityId().equals(plan.capabilityId())
                || !metadata.operationId().equals(context.operationId())
                || !metadata.operationType().equals(context.operationType())
                || metadata.providerAttempts() != 1
                || metadata.termination() != CapabilityOperationTermination.SUCCEEDED
                || metadata.deadlineTouched() || metadata.cancellationObserved()
                || !metadata.resourceLimitReference().equals(effectiveLimits.reference())
                || !context.absoluteDeadline().equals(scope.absoluteDeadline())) {
            throw new IllegalArgumentException("generation operation metadata binding mismatch");
        }
        if (!evidencePackage.invocationId().equals(scope.invocationId())
                || !evidencePackage.requestCorrelationId().equals(scope.requestCorrelationId())
                || !evidencePackage.capabilityId().equals(plan.capabilityId())
                || !evidencePackage.corpusKey().equals(plan.selectedCorpus())
                || !evidencePackage.profileProjectionDigest().equals(plan.profile().profileProjectionDigest())
                || !evidencePackage.resourceLimitReference().equals(effectiveLimits.reference())
                || !evidencePackage.outputContract().equals(AgentExecutionContracts.DOCUMENT_RESULT)) {
            throw new IllegalArgumentException("generation evidence package binding mismatch");
        }
        if (!request.input().packageId().equals(evidencePackage.packageId())
                || !request.input().packageDigest().equals(evidencePackage.canonicalDigest())
                || request.input().operation() != plan.parameters().operation()
                || !reference.decisionDigest().equals(evidencePackage.providerOutboundPolicyDigest())
                || !reference.inputDigest().equals(binder.digest(request.input()))
                || !reference.invocationId().equals(context.invocationId())
                || !reference.operationId().equals(context.operationId())
                || !reference.operationType().equals(context.operationType())
                || !reference.resourceLimitReference().equals(effectiveLimits.reference())
                || !reference.validUntil().equals(scope.absoluteDeadline())
                || !evidencePackage.authorizationBindingDigest().equals(
                        scope.externalProcessingAuthorizationEvidence().canonicalDigest())) {
            throw new IllegalArgumentException("generation request evidence binding mismatch");
        }

        DocumentUntrustedGenerationPayload payload = success.candidate();
        validatePayload(payload, plan, evidencePackage, limits);
        DocumentProviderBindingReference providerBinding = operationBindingRegistry.consume(metadata);

        List<CandidateEvidenceReference> evidenceRefs = evidencePackage.items().stream()
                .map(item -> new CandidateEvidenceReference(
                        item.citationId(), EVIDENCE_CONTRACT,
                        evidencePackage.authorizationBindingDigest(),
                        evidencePackage.targetBindingDigest()))
                .toList();
        List<CandidateCitationReference> citationRefs = payload.citedIds().stream()
                .map(id -> new CandidateCitationReference(id, id))
                .toList();
        CandidateSecurityBinding securityBinding = new CandidateSecurityBinding(
                scope.invocationId(), scope.requestCorrelationId(), evidencePackage.outputContract(),
                effectiveLimits.reference(), evidenceRefs, citationRefs, metadata);
        return new DocumentGeneratedTextCandidate(
                payload.operation(),
                new DocumentGeneratedContent(
                        payload.answerText(), payload.summaryText(), payload.summaryBullets()),
                payload.citedIds(), evidencePackage.canonicalDigest(), effectiveLimits.reference(),
                evidencePackage.authorizationBindingDigest(), metadata, providerBinding, securityBinding);
    }

    private static void validatePayload(
            DocumentUntrustedGenerationPayload payload,
            ValidatedDocumentPlan plan,
            EvidenceContextPackage evidencePackage,
            DocumentResourceLimit limits) {
        DocumentPlanOperation operation = plan.parameters().operation();
        if (payload == null || payload.finishReason() != DocumentProviderFinishReason.COMPLETED
                || payload.operation() != operation) {
            throw new IllegalArgumentException("generation payload binding invalid");
        }
        boolean answer = operation == DocumentPlanOperation.ANSWER
                && present(payload.answerText()) && !present(payload.summaryText())
                && payload.summaryBullets().isEmpty();
        boolean summary = operation == DocumentPlanOperation.SUMMARIZE
                && !present(payload.answerText())
                && (present(payload.summaryText()) || !payload.summaryBullets().isEmpty());
        if (!answer && !summary) {
            throw new IllegalArgumentException("generation output shape invalid");
        }
        int maxGeneratedChars = effectiveGeneratedChars(plan, limits);
        if (codePoints(payload.answerText()) > maxGeneratedChars
                || codePoints(payload.summaryText()) > Math.min(
                        maxGeneratedChars, limits.output().maxSummaryChars())
                || payload.summaryBullets().size() > limits.output().maxSummaryBullets()
                || payload.summaryBullets().stream().anyMatch(
                        value -> codePoints(value) > limits.output().maxSummaryChars())
                || payload.citedIds().size() > limits.output().maxCitationCount()) {
            throw new IllegalArgumentException("generation payload exceeds effective limits");
        }
        List<String> markerOrder = markerOrder(payload);
        if (!payload.citedIds().equals(markerOrder)
                || new LinkedHashSet<>(payload.citedIds()).size() != payload.citedIds().size()
                || !evidencePackage.citationIds().containsAll(payload.citedIds())) {
            throw new IllegalArgumentException("generation citation binding invalid");
        }
    }

    private static int effectiveGeneratedChars(
            ValidatedDocumentPlan plan,
            DocumentResourceLimit limits) {
        int result = plan.generationOptions()
                .map(options -> options.getMaxOutputChars() == null
                        ? limits.output().maxGeneratedChars()
                        : Math.min(options.getMaxOutputChars(), limits.output().maxGeneratedChars()))
                .orElse(limits.output().maxGeneratedChars());
        var summaryScope = plan.parameters().summaryScope();
        if (plan.parameters().operation() == DocumentPlanOperation.SUMMARIZE
                && summaryScope != null && summaryScope.getMaxSummaryChars() != null) {
            result = Math.min(result, summaryScope.getMaxSummaryChars());
        }
        return result;
    }

    private static List<String> markerOrder(DocumentUntrustedGenerationPayload payload) {
        LinkedHashSet<String> result = new LinkedHashSet<>();
        List<String> values = new ArrayList<>();
        if (payload.answerText() != null) values.add(payload.answerText());
        if (payload.summaryText() != null) values.add(payload.summaryText());
        values.addAll(payload.summaryBullets());
        for (String value : values) {
            Matcher matcher = MARKER.matcher(value);
            while (matcher.find()) result.add(matcher.group(1));
        }
        return List.copyOf(result);
    }

    private static boolean present(String value) {
        return value != null && !value.isBlank();
    }

    private static int codePoints(String value) {
        return value == null ? 0 : value.codePointCount(0, value.length());
    }
}
