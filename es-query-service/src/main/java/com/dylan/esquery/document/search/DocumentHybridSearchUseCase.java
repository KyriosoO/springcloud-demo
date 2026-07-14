package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.DocumentChannelResultSummary;
import com.dylan.esquery.api.model.document.DocumentSearchResponseBinding;
import com.dylan.esquery.api.model.document.HybridRetrievalDiagnostics;
import com.dylan.esquery.api.model.document.HybridSearchRequest;
import com.dylan.esquery.api.model.document.HybridSearchResponse;
import com.dylan.esquery.document.DocumentCorpusCatalog;
import com.dylan.esquery.document.DocumentCorpusDefinition;
import com.dylan.esquery.document.DocumentIndexTargetResolver;
import com.dylan.esquery.document.ResolvedIndexTargetRef;
import com.dylan.esquery.security.DocumentProtectedFilterGuard;

import java.io.IOException;
import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

/** Document hybrid 唯一入口：一次解析 target、算法前 binding、RRF 与 selection。 */
public final class DocumentHybridSearchUseCase {
    private final DocumentCorpusCatalog catalog;private final DocumentIndexTargetResolver targetResolver;
    private final DocumentProtectedFilterGuard filterGuard;private final DocumentChannelExecutorRegistry executors;
    private final DocumentRrfMerger merger;private final DocumentResultSelector selector;
    private final DocumentContextWindowLoader contextLoader;private final Clock clock;
    public DocumentHybridSearchUseCase(DocumentCorpusCatalog catalog,DocumentIndexTargetResolver targetResolver,
                                       DocumentProtectedFilterGuard filterGuard,DocumentChannelExecutorRegistry executors,
                                       DocumentRrfMerger merger,DocumentResultSelector selector,
                                       DocumentContextWindowLoader contextLoader,Clock clock){
        this.catalog=catalog;this.targetResolver=targetResolver;this.filterGuard=filterGuard;this.executors=executors;
        this.merger=merger;this.selector=selector;this.contextLoader=contextLoader;this.clock=clock;}

    public HybridSearchResponse search(HybridSearchRequest request) throws IOException{
        validateBoundary(request);filterGuard.requireValid(request);
        DocumentCorpusDefinition corpus=catalog.require(request.corpusKey());
        ResolvedIndexTargetRef target=targetResolver.resolve(request.corpusKey());
        Map<DocumentSearchChannel,List<BoundDocumentChannelHit>> hits=new EnumMap<>(DocumentSearchChannel.class);
        List<DocumentChannelResultSummary> summaries=new ArrayList<>();int rawCount=0;
        for(var channel:request.channels()){
            try{List<BoundDocumentChannelHit> channelHits=executors.execute(channel,request,target,corpus);hits.put(channel.channel(),channelHits);
                rawCount=Math.addExact(rawCount,channelHits.size());summaries.add(new DocumentChannelResultSummary(channel.channel(),DocumentChannelResultSummary.Outcome.SUCCEEDED,channelHits.size(),null));}
            catch(IOException ex){if(channel.required())throw ex;summaries.add(new DocumentChannelResultSummary(channel.channel(),DocumentChannelResultSummary.Outcome.DEGRADED,0,"OPERATIONAL_FAILURE"));}
        }
        if(hits.isEmpty())throw new IllegalStateException("document search has no successful channel");
        var fused=merger.merge(hits,request);var selected=selector.select(fused,request,target.binding());
        var contextResult=contextLoader.loadBatch(selected,request,target,corpus);selected=contextResult.hits();
        int documents=(int)selected.stream().map(hit->hit.documentId()+"|"+hit.documentVersion()).distinct().count();
        var diagnostics=new HybridRetrievalDiagnostics(rawCount,fused.size(),selected.size(),documents,
                fused.size()>=request.fusion().maxFusedCandidates()||selected.size()<fused.size(),contextResult.truncated());
        var binding=new DocumentSearchResponseBinding(request.operationMetadata().requestCorrelationId(),request.operationMetadata().operationId(),
                request.corpusKey(),target.binding(),request.executionBinding().profileProjectionDigest(),request.executionBinding().resourceLimit(),
                request.executionBinding().authorizationBindingDigest(),request.protectedFilterDigest(),request.executionBinding().aclEvidenceDigest());
        requireLive(request);return new HybridSearchResponse(binding,selected,List.copyOf(summaries),diagnostics);
    }
    private void validateBoundary(HybridSearchRequest request){if(request==null)throw new IllegalArgumentException("document request required");
        if(!request.executionBinding().resourceLimit().equals(request.operationMetadata().resourceLimit())
                ||!request.executionBinding().resourceLimit().registrationIdentity().equals(request.operationMetadata().registrationIdentity())){
            throw new IllegalArgumentException("document operation/resource binding mismatch");}
        long total=Math.multiplyExact((long)request.channels().size(),request.channels().stream().mapToInt(c->c.candidateCount()).max().orElseThrow());
        if(total>request.fusion().maxFusedCandidates()*8L)throw new IllegalArgumentException("document channel candidate capacity invalid");requireLive(request);}
    private void requireLive(HybridSearchRequest request){if(!Instant.ofEpochMilli(request.operationMetadata().absoluteDeadlineEpochMilli()).isAfter(clock.instant()))throw new IllegalStateException("document search deadline exceeded");}
}
