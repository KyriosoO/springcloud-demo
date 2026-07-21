package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.DocumentChannelRank;
import com.dylan.esquery.api.model.document.HybridSearchRequest;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Document 唯一确定性 RRF；不依赖 task completion 顺序。 */
public final class DocumentRrfMerger {
    public List<FusedDocumentHit> merge(
            Map<DocumentSearchChannel,List<BoundDocumentChannelHit>> hitsByChannel,
            HybridSearchRequest request) {
        Map<DocumentSearchChannel,Integer> weights=new EnumMap<>(DocumentSearchChannel.class);
        request.channels().forEach(channel->weights.put(channel.channel(),channel.weight()));
        Map<ChunkKey,Accumulator> merged=new LinkedHashMap<>();
        for(DocumentSearchChannel channel:DocumentSearchChannel.values()){
            List<BoundDocumentChannelHit> input=new ArrayList<>(hitsByChannel.getOrDefault(channel,List.of()));
            input.sort(Comparator.comparing(BoundDocumentChannelHit::esScore).reversed()
                    .thenComparing(BoundDocumentChannelHit::documentId)
                    .thenComparing(BoundDocumentChannelHit::documentVersion)
                    .thenComparingInt(BoundDocumentChannelHit::chunkIndex)
                    .thenComparing(BoundDocumentChannelHit::chunkId));
            for(int index=0;index<input.size();index++){
                BoundDocumentChannelHit hit=withRank(input.get(index),index+1);
                ChunkKey key=new ChunkKey(hit.documentId(),hit.documentVersion(),hit.chunkId());
                Accumulator existing=merged.get(key);
                if(existing==null){existing=new Accumulator(hit);merged.put(key,existing);}
                else requireSameBinding(existing.representative,hit);
                existing.add(hit,contribution(weights.getOrDefault(channel,0),request.fusion().rrfK(),hit.rank()));
            }
        }
        return merged.values().stream().map(Accumulator::fused)
                .sorted(Comparator.comparing(FusedDocumentHit::rrfScore).reversed()
                        .thenComparingInt(FusedDocumentHit::bestRank)
                        .thenComparing((FusedDocumentHit h)->h.channelRanks().size(),Comparator.reverseOrder())
                        .thenComparing(h->h.representative().documentId())
                        .thenComparing(h->h.representative().documentVersion())
                        .thenComparingInt(h->h.representative().chunkIndex())
                        .thenComparing(h->h.representative().chunkId()))
                .limit(request.fusion().maxFusedCandidates()).toList();
    }

    private static BoundDocumentChannelHit withRank(BoundDocumentChannelHit h,int rank){return new BoundDocumentChannelHit(
            h.channel(),rank,h.esScore(),h.documentId(),h.documentVersion(),h.chunkId(),h.chunkIndex(),h.aclRef(),h.aclVersion(),
            h.title(),h.sourceType(),h.section(),h.page(),h.sourceUri(),h.snippet(),h.content(),h.citationText(),h.generationText(),
            h.charStart(),h.charEnd(),h.contextBefore(),h.contextAfter());}
    private static BigDecimal contribution(int weight,int rrfK,int rank){
        if(weight<=0)throw new IllegalArgumentException("document channel weight missing");
        return BigDecimal.valueOf(weight).divide(BigDecimal.valueOf((long)rrfK+rank),18,RoundingMode.HALF_EVEN);
    }
    private static void requireSameBinding(BoundDocumentChannelHit a,BoundDocumentChannelHit b){
        if(!a.documentId().equals(b.documentId())||!a.documentVersion().equals(b.documentVersion())||!a.chunkId().equals(b.chunkId())
                ||a.chunkIndex()!=b.chunkIndex()||!a.aclRef().equals(b.aclRef())||!a.aclVersion().equals(b.aclVersion())
                ||!java.util.Objects.equals(a.content(),b.content())||!java.util.Objects.equals(a.sourceUri(),b.sourceUri())){
            throw new IllegalArgumentException("document duplicate chunk binding mismatch");
        }
    }
    private static final class Accumulator{
        private final BoundDocumentChannelHit representative;private BigDecimal score=BigDecimal.ZERO.setScale(18);private final List<DocumentChannelRank> ranks=new ArrayList<>();
        private Accumulator(BoundDocumentChannelHit representative){this.representative=representative;}
        private void add(BoundDocumentChannelHit hit,BigDecimal contribution){score=score.add(contribution).setScale(18,RoundingMode.HALF_EVEN);ranks.add(new DocumentChannelRank(hit.channel(),hit.rank(),hit.esScore()));}
        private FusedDocumentHit fused(){int best=ranks.stream().mapToInt(DocumentChannelRank::rank).min().orElseThrow();return new FusedDocumentHit(representative,score,best,List.copyOf(ranks));}
    }
    private record ChunkKey(String documentId,String documentVersion,String chunkId) {}
}
