package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.esquery.api.model.document.HybridRetrievalDiagnostics;
import com.dylan.esquery.api.model.document.HybridSearchResponse;

import java.util.List;

/** strict response 到 Adapter bound result 的无损安全映射。 */
public final class DocumentEvidenceMapper {
    public AdapterDocumentRetrievalResult toAdapterResult(HybridSearchResponse response,List<AclBoundDocumentHit> boundHits,
                                                           DocumentRetrievalCommand command,CapabilityOperationContext context){
        var wire=response.binding();
        var binding=new DocumentRetrievalResponseBinding(wire.requestCorrelationId(),wire.operationId(),command.corpusKey(),
                new DocumentTargetBindingReference(wire.targetBinding().schemaVersion(),wire.targetBinding().indexContentDigest(),
                        wire.targetBinding().manifestDigest(),wire.targetBinding().attestationDigest()),wire.profileProjectionDigest(),
                context.resourceLimits().reference(),wire.authorizationBindingDigest(),wire.protectedFilterDigest(),wire.aclEvidenceDigest());
        return new AdapterDocumentRetrievalResult(boundHits,toDiagnostics(response.diagnostics()),binding,command.dedup().maxReturnedDocuments());
    }
    private AdapterDocumentRetrievalDiagnostics toDiagnostics(HybridRetrievalDiagnostics source){
        AdapterDocumentRetrievalDiagnostics target=new AdapterDocumentRetrievalDiagnostics();target.setRetrievalMode("HYBRID");
        target.setReturnedHitCount(source.returnedChunkCount());target.setFusedCandidateCount(source.fusedCandidateCount());
        target.setDedupedCandidateCount(source.returnedChunkCount());target.setFusionStrategy("RRF");target.setRerankStatus("NOT_REQUESTED");
        target.setDegraded(false);return target;
    }
}
