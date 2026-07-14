package com.dylan.esquery.security;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentProtectedFilterDto;
import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.*;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentProtectedFilterGuardTest {
    @Test
    void acceptsExactDafBindingAndRejectsMutation() {
        DocumentProtectedFilterGuard guard = new DocumentProtectedFilterGuard();
        DocumentProtectedFilterDto root = new DocumentProtectedFilterDto(
                DocumentProtectedFilterDto.Kind.ALL_OF, null, null, List.of(), List.of(
                new DocumentProtectedFilterDto(DocumentProtectedFilterDto.Kind.EXACT,
                        DocumentProtectedFilterDto.Field.TENANT_ID, "tenant-1", List.of(), List.of()),
                new DocumentProtectedFilterDto(DocumentProtectedFilterDto.Kind.EXACT,
                        DocumentProtectedFilterDto.Field.STATUS, "ACTIVE", List.of(), List.of())));
        HybridSearchRequest unsigned = request(root, "0".repeat(64));
        HybridSearchRequest signed = request(root, guard.canonicalDigest(unsigned));

        assertThatCode(() -> guard.requireValid(signed)).doesNotThrowAnyException();

        DocumentProtectedFilterDto mutated = new DocumentProtectedFilterDto(
                DocumentProtectedFilterDto.Kind.EXACT,
                DocumentProtectedFilterDto.Field.TENANT_ID, "tenant-2", List.of(), List.of());
        assertThatThrownBy(() -> guard.requireValid(request(mutated, signed.protectedFilterDigest())))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("digest mismatch");
    }

    private static HybridSearchRequest request(DocumentProtectedFilterDto root, String digest) {
        var limit=new ResourceLimitBindingDto("agent","DocumentResourceLimit","v1","c".repeat(64),"inv-1","reg-1");
        return new HybridSearchRequest(new DocumentCorpusKeyDto("policy", "document"),
                new DocumentSearchExecutionBinding("tax-v2","v2","b".repeat(64),limit,"c".repeat(64),"a".repeat(64)),
                List.of(),root,digest,new DocumentQueryPlan("tax",List.of(),List.of(),java.util.Optional.empty()),
                List.of(new DocumentHybridChannelRequest(DocumentSearchChannel.BM25,true,1,10)),
                new HybridFusionRequest(60,10),new HybridDedupRequest(5,2),new HybridContextRequest(0,0,0),
                new DocumentSearchOperationMetadata("corr-1","op-1","DOCUMENT_RETRIEVAL",
                        java.time.Instant.now().plusSeconds(60).toEpochMilli(),"reg-1",limit));
    }
}
