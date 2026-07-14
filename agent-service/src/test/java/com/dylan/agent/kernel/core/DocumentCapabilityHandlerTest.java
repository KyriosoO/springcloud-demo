package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;
import com.dylan.agent.adapter.api.operation.CapabilityOperationSuccess;
import com.dylan.agent.adapter.api.operation.CapabilityOperationTermination;
import com.dylan.agent.adapter.api.operation.ProviderSafeIdentity;
import com.dylan.agent.api.plan.*;
import com.dylan.agent.capability.document.*;
import com.dylan.agent.capability.document.acl.*;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingPort;
import com.dylan.agent.capability.document.evidence.DocumentEvidenceVisibilityProjector;
import com.dylan.agent.capability.document.generation.*;
import com.dylan.agent.capability.document.governance.emergency.*;
import com.dylan.agent.capability.document.provider.DocumentProviderOperationRequestBinder;
import com.dylan.agent.capability.document.provider.security.*;
import com.dylan.agent.mask.*;
import com.dylan.agent.capability.document.rerank.DocumentRerankPort;
import com.dylan.agent.capability.document.rewrite.*;
import com.dylan.agent.capability.document.security.DocumentRevocationGuard;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentCapabilityHandlerTest {
    @Test
    void searchUsesProtectedFilterAndReturnsStableCitationIds() {
        AtomicReference<DocumentRetrievalCommand> captured = new AtomicReference<>();
        DocumentRetrievableAdapter adapter = retrievalAdapter(captured, false);
        DocumentCapabilityHandler handler = handler();
        ValidatedDocumentExecutionParameters request = ValidatedDocumentPlanTestSupport.request(
                DocumentPlanOperation.SEARCH, "policy_document", "税收优惠", true);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                "document.search", "policy_document", request);

        var result = handler.execute(plan, DocumentCapabilityHandlerTestSupport.context(adapter)).output();

        assertThat(captured.get().protectedFilter()).isNotNull();
        assertThat(result.getDocumentResult().getCitations()).hasSize(1);
        assertThat(result.getDocumentResult().getCitations().getFirst().getCitationId()).isEqualTo("C1");
    }

    @Test
    void aclDenialPreventsQueryRewriteBeforeRetrieval() {
        AtomicBoolean rewriteInvoked = new AtomicBoolean();
        DocumentQueryRewritePort rewrite = request -> {
            rewriteInvoked.set(true);
            throw new AssertionError("rewrite must not run before ACL authorization");
        };
        DocumentAclScopePort deniedAcl = request -> new DocumentAclScopeDenied(
                DocumentAclDenyReason.SUBJECT_NOT_ALLOWED, "acl-denied", metadata(
                request.operationContext(), "acl-authority", CapabilityOperationTermination.REJECTED));
        DocumentCapabilityHandler handler = handler(
                request -> { throw new AssertionError("embedding must not run"); },
                request -> { throw new AssertionError("rerank must not run"); },
                rewrite,
                request -> { throw new AssertionError("generation must not run"); },
                deniedAcl,
                currentness());
        ValidatedDocumentExecutionParameters request = ValidatedDocumentPlanTestSupport.request(
                DocumentPlanOperation.SEARCH, "policy_document", "税收优惠", true);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                "document.search", "policy_document", request, null,
                com.dylan.agent.capability.document.profile.DocumentFeaturePolicy.OPTIONAL,
                com.dylan.agent.capability.document.profile.DocumentFeaturePolicy.DISABLED,
                com.dylan.agent.capability.document.profile.DocumentFeaturePolicy.DISABLED);

        assertThatThrownBy(() -> handler.execute(
                plan, DocumentCapabilityHandlerTestSupport.context(retrievalAdapter(new AtomicReference<>(), false))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("document ACL scope denied");
        assertThat(rewriteInvoked).isFalse();
    }

    @Test
    void invalidCandidateBindingPreventsRerankProviderInvocation() {
        AtomicBoolean rerankInvoked = new AtomicBoolean();
        DocumentRerankPort rerank = request -> {
            rerankInvoked.set(true);
            throw new AssertionError("rerank must not receive an unbound candidate");
        };
        DocumentCapabilityHandler handler = handler(
                request -> { throw new AssertionError("embedding must not run"); },
                rerank,
                request -> { throw new AssertionError("rewrite must not run"); },
                request -> { throw new AssertionError("generation must not run"); },
                allowedAcl(),
                currentness());
        DocumentChannelProfileProjection channels = new DocumentChannelProfileProjection(
                10, 10, 60, 20, 1,
                List.of(DocumentRetrievalChannel.BM25), List.of(DocumentRetrievalChannel.BM25),
                Map.of(DocumentRetrievalChannel.BM25, 1), true, 1);
        ValidatedDocumentExecutionParameters request = new ValidatedDocumentExecutionParameters(
                DocumentPlanOperation.SEARCH, "税收优惠", List.of(), List.of(), 5, 1, 5,
                null, true, DocumentRetrievalMode.KEYWORD, channels, null);
        ValidatedDocumentPlan plan = ValidatedDocumentPlanTestSupport.documentPlan(
                "document.search", "policy_document", request, null,
                com.dylan.agent.capability.document.profile.DocumentFeaturePolicy.DISABLED,
                com.dylan.agent.capability.document.profile.DocumentFeaturePolicy.DISABLED,
                com.dylan.agent.capability.document.profile.DocumentFeaturePolicy.OPTIONAL);

        assertThatThrownBy(() -> handler.execute(
                plan, DocumentCapabilityHandlerTestSupport.context(retrievalAdapter(new AtomicReference<>(), true))))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("document hit security binding mismatch");
        assertThat(rerankInvoked).isFalse();
    }

    private static DocumentRetrievableAdapter retrievalAdapter(
            AtomicReference<DocumentRetrievalCommand> captured,
            boolean invalidCandidateProfileBinding) {
        return (request, operationContext) -> {
            captured.set(request);
            var protectedBinding = request.protectedFilter();
            var security = new DocumentCandidateSecurityBinding(
                    operationContext.invocationId(), operationContext.requestCorrelationId(),
                    operationContext.resourceLimits().reference().registrationIdentity(), protectedBinding.corpusKey(),
                    new DocumentTargetBindingReference("3.0.0", "e".repeat(64), "f".repeat(64), "1".repeat(64)),
                    protectedBinding.filterDigest(), protectedBinding.aclEvidenceDigest(),
                    new DocumentAclObjectRef("acl-1", "acl-v1"),
                    invalidCandidateProfileBinding ? "0".repeat(64) : protectedBinding.profileProjectionDigest(),
                    operationContext.resourceLimits().reference());
            var hit = new AclBoundDocumentHit("candidate-1",new DocumentCandidateIdentity("doc-1","v1","chunk-1",0),
                    "政策","policy",null,null,null,"税收优惠证据",null,"税收优惠证据",null,List.of(),List.of(),null,null,
                    BigDecimal.ONE,BigDecimal.ONE,List.of("BM25"),List.of(),security);
            var binding = new DocumentRetrievalResponseBinding(operationContext.requestCorrelationId(),operationContext.operationId(),
                    protectedBinding.corpusKey(),security.targetBinding(),protectedBinding.profileProjectionDigest(),operationContext.resourceLimits().reference(),
                    operationContext.resourceLimits().reference().canonicalDigest(),protectedBinding.filterDigest(),protectedBinding.aclEvidenceDigest());
            var result = new AdapterDocumentRetrievalResult(List.of(hit),new AdapterDocumentRetrievalDiagnostics(),binding,1);
            var metadata = new CapabilityOperationMetadata(operationContext.operationId(),operationContext.operationType(),
                    new ProviderSafeIdentity("es-query-service",Optional.empty()),1,1,CapabilityOperationTermination.SUCCEEDED,
                    "document-retrieval-ok",operationContext.resourceLimits().reference(),false,false,false);
            return new CapabilityOperationSuccess<>(result,metadata);
        };
    }

    private static DocumentCapabilityHandler handler() {
        DocumentEmbeddingPort embedding = request -> { throw new AssertionError("embedding must not run"); };
        DocumentRerankPort rerank = request -> { throw new AssertionError("rerank must not run"); };
        DocumentQueryRewritePort rewrite = request -> { throw new AssertionError("rewrite must not run"); };
        DocumentGenerationPort generation = request -> { throw new AssertionError("generation must not run"); };
        return handler(embedding, rerank, rewrite, generation, allowedAcl(), currentness());
    }

    private static DocumentAclScopePort allowedAcl() {
        return request -> {
            Instant now = Instant.now();
            var scope = new DocumentAclScopeSnapshot(
                    "tenant-1", "user-1", Set.of("dept-1"), Set.of("role-1"), Set.of(),
                    new AllPrincipalVisibleDocuments(), Set.of(), "acl-v1", "perm-v1",
                    now.minusSeconds(1), now.plusSeconds(30), "authority-evidence", "a".repeat(64));
            var metadata = new com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata(
                    request.operationContext().operationId(), request.operationContext().operationType(),
                    new com.dylan.agent.adapter.api.operation.ProviderSafeIdentity("acl-authority", Optional.empty()),
                    1, 1, com.dylan.agent.adapter.api.operation.CapabilityOperationTermination.SUCCEEDED,
                    "acl-diagnostic", request.operationContext().resourceLimits().reference(),
                    false, false, false);
            return new DocumentAclScopeAllowed(scope, metadata);
        };
    }

    private static DocumentAclCurrentnessPort currentness() {
        return new DocumentAclCurrentnessPort() {
            @Override public DocumentAclCurrentnessDecision verifyScope(DocumentAclScopeCurrentnessRequest request) {
                return current(request.operationContext());
            }
            @Override public DocumentAclCurrentnessDecision verifyCandidates(DocumentAclCandidateCurrentnessRequest request) {
                return current(request.operationContext());
            }
            private DocumentAclCurrentnessDecision current(com.dylan.agent.adapter.api.operation.CapabilityOperationContext context) {
                Instant now = Instant.now();
                var metadata = metadata(context, "acl", CapabilityOperationTermination.SUCCEEDED);
                return new DocumentAclCurrentnessDecision(
                        DocumentCurrentnessOutcome.ALLOW, "acl-v1", "perm-v1", "decision-v1",
                        now, now.plusSeconds(2), "CURRENT", metadata);
            }
        };
    }

    private static CapabilityOperationMetadata metadata(
            com.dylan.agent.adapter.api.operation.CapabilityOperationContext context,
            String provider,
            CapabilityOperationTermination termination) {
        return new CapabilityOperationMetadata(
                context.operationId(), context.operationType(),
                new ProviderSafeIdentity(provider, Optional.empty()), 1, 1, termination,
                "diagnostic", context.resourceLimits().reference(), false, false, false);
    }

    private static DocumentCapabilityHandler handler(
            DocumentEmbeddingPort embedding,
            DocumentRerankPort rerank,
            DocumentQueryRewritePort rewrite,
            DocumentGenerationPort generation,
            DocumentAclScopePort acl,
            DocumentAclCurrentnessPort currentness) {
        DocumentEmergencyControlReadPort emergency = (targets, deadline) -> new DocumentEmergencyView(
                "view-1", targets.stream().map(target -> {
                    var binding=DocumentEmergencyGateCanonicalizer.targetBinding(target);
                    return new DocumentEmergencyView.Decision(binding.targetType().name(),binding.targetKeyDigest(),
                            DocumentEmergencyView.Outcome.NOT_BLOCKED,null);
                }).toList(),
                Instant.now(), Instant.now().plusSeconds(2), "e".repeat(64));
        var binder = new DocumentProviderOperationRequestBinder(new ObjectMapper());
        var masking = new com.dylan.agent.metadata.result.ResultValueMaskingSupport(new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(), new IdCardFieldMasker(), new MobileFieldMasker(),
                new EmailFieldMasker(), new AddressFieldMasker())));
        var fieldProjector = new DocumentProviderOutboundFieldProjector(masking);
        return new DocumentCapabilityHandler(embedding, acl, currentness,
                new DocumentRevocationGuard(currentness, emergency, java.time.Clock.systemUTC(),
                        Duration.ofSeconds(2), DocumentAclCompilerLimits.secureDefaults()),
                new DocumentEvidenceVisibilityProjector(masking), new DocumentGenerationEvidenceProjector(fieldProjector),
                new EvidenceContextPackageFactory(), new DocumentGeneratedTextCandidateFactory(
                        binder, new com.dylan.agent.capability.document.provider.DocumentProviderOperationBindingRegistry(
                                java.time.Clock.systemUTC())),
                new DocumentGenerationInputProjector(), generation,
                new DocumentCitationVerifier(), null, rerank, rewrite, new RewriteCandidateNormalizer(),
                new DocumentRuleExtractor(), binder,
                new DocumentProviderOutboundPolicyDecisionFactory(
                        new DocumentProviderOutboundPolicyCanonicalizer(), java.time.Clock.systemUTC()),
                fieldProjector,
                new DocumentProtectedFilterFactory(DocumentAclCompilerLimits.secureDefaults()), new ObjectMapper());
    }
}
