package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.DocumentCandidateSecurityBinding;
import com.dylan.agent.adapter.api.document.DocumentRetrievalResponseBinding;
import com.dylan.agent.adapter.api.document.DocumentTargetBindingReference;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

/** 使用可信执行绑定和已完成的 generation projection 构造唯一 ECP-1。 */
public final class EvidenceContextPackageFactory {
    public EvidenceContextPackage create(
            EvidenceContextPackageRequest request,
            DocumentGenerationEvidenceProjection projection) {
        DocumentRetrievalResponseBinding binding = request.responseBinding();
        String targetDigest = binding.targetBinding().canonicalDigest();
        String policyDigest = request.outboundPolicyDecision().canonicalDigest();
        if (!request.plan().selectedCorpus().equals(request.outboundPolicyDecision().corpusKey())
                || !binding.profileProjectionDigest().equals(
                        request.outboundPolicyDecision().profileProjectionDigest())
                || !binding.resourceLimitReference().equals(
                        request.outboundPolicyDecision().resourceLimitReference())
                || !binding.authorizationBindingDigest().equals(
                        request.outboundPolicyDecision().authorizationBindingDigest())) {
            throw new IllegalArgumentException("generation outbound policy binding mismatch");
        }
        String digest = canonicalDigest(
                request, binding, targetDigest, policyDigest, projection.items(), projection.usage());
        return new EvidenceContextPackage(
                "ECP-" + digest.substring(0, 24), request.context().invocationId(),
                request.context().requestCorrelationId(), request.context().capabilityId(),
                request.plan().parameters().operation(), request.plan().selectedCorpus(),
                binding.profileProjectionDigest(), binding.resourceLimitReference(), AgentExecutionContracts.DOCUMENT_RESULT,
                binding.authorizationBindingDigest(), binding.aclEvidenceDigest(), targetDigest,
                binding.protectedFilterDigest(), policyDigest, projection.items(), projection.usage(), digest);
    }

    private static String canonicalDigest(
            EvidenceContextPackageRequest request,
            DocumentRetrievalResponseBinding binding,
            String targetDigest,
            String policyDigest,
            List<GenerationEvidencePackageItem> items,
            DocumentEvidenceUsage usage) {
        DigestWriter writer = new DigestWriter();
        writer.text("ECP-1");
        writer.text(request.context().invocationId());
        writer.text(request.context().requestCorrelationId());
        writer.text(request.context().capabilityId());
        writer.text(request.plan().parameters().operation().name());
        writer.text(request.plan().selectedCorpus().domain());
        writer.text(request.plan().selectedCorpus().materialType());
        writer.text(binding.profileProjectionDigest());
        writer.text(binding.resourceLimitReference().canonicalDigest());
        writer.text(AgentExecutionContracts.DOCUMENT_RESULT.namespace());
        writer.text(AgentExecutionContracts.DOCUMENT_RESULT.name());
        writer.text(AgentExecutionContracts.DOCUMENT_RESULT.version());
        writer.text(binding.authorizationBindingDigest());
        writer.text(binding.aclEvidenceDigest());
        writer.text(targetDigest);
        writer.text(binding.protectedFilterDigest());
        writer.text(policyDigest);
        writer.integer(usage.itemCount());
        writer.integer(usage.evidenceChars());
        writer.integer(usage.contextChars());
        writer.bool(usage.truncated());
        for (GenerationEvidencePackageItem item : items) {
            writer.text(item.citationId());
            writer.text(item.candidateId());
            writer.text(item.identity().documentId());
            writer.text(item.identity().documentVersion());
            writer.text(item.identity().chunkId());
            writer.integer(item.identity().chunkIndex());
            writer.text(item.outboundTitle());
            writer.text(item.outboundSection());
            writer.integer(item.outboundPage());
            writer.text(item.outboundText());
            security(writer, item.securityBinding());
        }
        return writer.hex();
    }

    private static void security(DigestWriter writer, DocumentCandidateSecurityBinding binding) {
        writer.text(binding.invocationId());
        writer.text(binding.requestCorrelationId());
        writer.text(binding.registrationIdentity());
        writer.text(binding.corpusKey().domain());
        writer.text(binding.corpusKey().materialType());
        writer.text(binding.targetBinding().manifestDigest());
        writer.text(binding.targetBinding().attestationDigest());
        writer.text(binding.protectedFilterDigest());
        writer.text(binding.aclEvidenceDigest());
        writer.text(binding.aclObjectRef().aclRef());
        writer.text(binding.aclObjectRef().aclVersion());
        writer.text(binding.profileProjectionDigest());
        writer.text(binding.resourceLimitReference().canonicalDigest());
    }

    private static final class DigestWriter {
        private final MessageDigest digest;

        private DigestWriter() {
            try {
                digest = MessageDigest.getInstance("SHA-256");
            } catch (NoSuchAlgorithmException ex) {
                throw new IllegalStateException(ex);
            }
        }

        private void text(String value) {
            if (value == null) {
                integer(-1);
                return;
            }
            byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
            integer(bytes.length);
            digest.update(bytes);
        }

        private void integer(Integer value) {
            digest.update(ByteBuffer.allocate(4).putInt(value == null ? -1 : value).array());
        }

        private void bool(boolean value) {
            digest.update((byte) (value ? 1 : 0));
        }

        private String hex() {
            return HexFormat.of().formatHex(digest.digest());
        }
    }
}
