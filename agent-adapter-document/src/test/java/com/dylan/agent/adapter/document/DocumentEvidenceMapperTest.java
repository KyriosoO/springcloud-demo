package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.adapter.api.operation.*;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.DocumentTargetBindingDto;
import com.dylan.esquery.api.model.document.*;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentEvidenceMapperTest {
    @Test
    void mapsOnlyAlreadyBoundTypedHit() {
        DocumentCandidateIdentity identity = new DocumentCandidateIdentity("doc-1", "v1", "chunk-1", 0);
        ResourceLimitReference limits = new ResourceLimitReference(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, "d".repeat(64), "inv-1", "document-reg");
        DocumentCandidateSecurityBinding security = new DocumentCandidateSecurityBinding(
                "inv-1", "corr-1", "document-reg", new DocumentCorpusKey("policy", "document"),
                new DocumentTargetBindingReference("3.0.0", "e".repeat(64), "f".repeat(64), "1".repeat(64)),
                "a".repeat(64), "b".repeat(64), new DocumentAclObjectRef("acl-1", "v1"),
                "c".repeat(64), limits);
        AclBoundDocumentHit hit = new AclBoundDocumentHit(
                "candidate-1", identity, "政策", "policy", null, null, null, "证据", null,
                null, null, List.of(), List.of(), null, null, BigDecimal.ONE, BigDecimal.ONE,
                List.of("BM25"), List.of("sourceType"), security);
        var wireLimit = new ResourceLimitBindingDto("agent", "DocumentResourceLimit", "v1", "d".repeat(64), "inv-1", "document-reg");
        HybridSearchResponse response = new HybridSearchResponse(new DocumentSearchResponseBinding("corr-1", "op-1",
                new DocumentCorpusKeyDto("policy", "document"),new DocumentTargetBindingDto("3.0.0", "e".repeat(64), "f".repeat(64), "1".repeat(64)),
                "c".repeat(64),wireLimit,"d".repeat(64),"a".repeat(64),"b".repeat(64)),List.of(),
                List.of(new DocumentChannelResultSummary(DocumentSearchChannel.BM25, DocumentChannelResultSummary.Outcome.SUCCEEDED, 0, null)),
                new HybridRetrievalDiagnostics(0,0,0,0,false,false));

        var command = command(security, limits);
        var result = new DocumentEvidenceMapper().toAdapterResult(response, List.of(hit), command, context(limits));

        assertThat(result.hits()).containsExactly(hit);
        assertThat(result.binding().targetBinding()).isEqualTo(security.targetBinding());
    }

    private DocumentRetrievalCommand command(DocumentCandidateSecurityBinding security,ResourceLimitReference limits){
        var filter=new DocumentProtectedFilterBinding(security.corpusKey(),new DocumentAllOf(List.of(
                new DocumentExactTerm(DocumentAclIndexField.TENANT_ID,"tenant-1"))),security.protectedFilterDigest(),security.aclEvidenceDigest(),
                security.profileProjectionDigest(),limits);
        var execution=new DocumentRetrievalExecutionBinding("tax-v2","v2",security.profileProjectionDigest(),limits,limits.canonicalDigest(),security.aclEvidenceDigest());
        return new DocumentRetrievalCommand(security.corpusKey(),execution,List.of(),filter,new DocumentPreparedQuery("tax",List.of(),List.of(),Optional.empty()),
                new DocumentRetrievalChannels(List.of(DocumentRetrievalChannel.BM25),List.of(DocumentRetrievalChannel.BM25),Map.of(DocumentRetrievalChannel.BM25,1),10),
                new DocumentFusionSpec(60,50),new DocumentDedupSpec(5,3),new DocumentContextSpec(0,0,0));
    }
    private CapabilityOperationContext context(ResourceLimitReference limits){return new CapabilityOperationContext("inv-1","corr-1","document.search","op-1",
            CapabilityOperationType.of("DOCUMENT_RETRIEVAL"),Instant.now().plusSeconds(60),()->false,new CapabilityResourceLimitView(){
                @Override public <T extends CapabilityResourceLimit>T require(com.dylan.agent.api.contract.common.ContractRef ref,Class<T> type){throw new UnsupportedOperationException();}
                @Override public ResourceLimitReference reference(){return limits;}});}
}
