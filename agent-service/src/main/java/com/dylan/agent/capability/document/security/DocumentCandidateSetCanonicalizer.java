package com.dylan.agent.capability.document.security;

import com.dylan.agent.adapter.api.document.SafeDocumentCandidate;
import com.dylan.agent.api.contract.common.ContractRef;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

/** DCS-1：绑定稳定输出顺序、candidate security identity 与 output contract。 */
public final class DocumentCandidateSetCanonicalizer {
    public String digest(List<SafeDocumentCandidate> candidates, List<String> evidenceRefs, ContractRef outputContract) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            update(digest, "DCS-1");
            for (SafeDocumentCandidate candidate : List.copyOf(candidates)) {
                var identity = candidate.identity();
                var binding = candidate.securityBinding();
                update(digest, candidate.candidateId());
                update(digest, identity.documentId());
                update(digest, identity.documentVersion());
                update(digest, identity.chunkId());
                update(digest, Integer.toString(identity.chunkIndex()));
                update(digest, binding.protectedFilterDigest());
                update(digest, binding.aclEvidenceDigest());
                update(digest, binding.aclObjectRef().aclRef());
                update(digest, binding.aclObjectRef().aclVersion());
                update(digest, binding.targetBinding().manifestDigest());
                update(digest, binding.targetBinding().attestationDigest());
                update(digest, binding.profileProjectionDigest());
                update(digest, binding.resourceLimitReference().canonicalDigest());
            }
            for (String ref : List.copyOf(evidenceRefs == null ? List.of() : evidenceRefs)) update(digest, ref);
            update(digest, outputContract.namespace());
            update(digest, outputContract.name());
            update(digest, outputContract.version());
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = String.valueOf(value).getBytes(StandardCharsets.UTF_8);
        digest.update(new byte[] {(byte) (bytes.length >>> 24), (byte) (bytes.length >>> 16),
                (byte) (bytes.length >>> 8), (byte) bytes.length});
        digest.update(bytes);
    }
}
