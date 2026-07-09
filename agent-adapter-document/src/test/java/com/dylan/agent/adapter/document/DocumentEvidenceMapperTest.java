package com.dylan.agent.adapter.document;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.dylan.esquery.api.model.HybridRetrievalDiagnostics;
import com.dylan.esquery.api.model.HybridSearchHit;
import com.dylan.esquery.api.model.HybridSearchResponse;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentEvidenceMapperTest {

    @Test
    void mapsElasticHitsToDocumentEvidence() {
        DocumentEvidenceMapper mapper = new DocumentEvidenceMapper(new ObjectMapper(), new DocumentAdapterProperties());

        var result = mapper.toAdapterResult("""
                {
                  "hits": {
                    "hits": [{
                      "_id": "doc-1",
                      "_score": 0.92,
                      "_source": {
                        "chunkId": "c-1",
                        "title": "休假政策",
                        "sourceType": "policy",
                        "section": "年假",
                        "page": 3,
                        "sourceUri": "kb://leave",
                        "embedding": [0.1, 0.2],
                        "content": "员工年假需要直属主管审批。"
                      }
                    }]
                  }
                }
                """, 5);

        assertThat(result.getHits()).singleElement().satisfies(evidence -> {
            assertThat(evidence.getDocumentId()).isEqualTo("doc-1");
            assertThat(evidence.getChunkId()).isEqualTo("c-1");
            assertThat(evidence.getTitle()).isEqualTo("休假政策");
            assertThat(evidence.getSnippet()).isEqualTo("员工年假需要直属主管审批。");
            assertThat(evidence.getPage()).isEqualTo(3);
            assertThat(evidence.getMetadata()).doesNotContainKey("embedding");
        });
        assertThat(result.getCoveredDocumentCount()).isEqualTo(1);
    }

    @Test
    void mapsHybridHitsWithContextAndScores() {
        DocumentEvidenceMapper mapper = new DocumentEvidenceMapper(new ObjectMapper(), new DocumentAdapterProperties());
        HybridSearchHit hit = new HybridSearchHit();
        hit.setDocumentId("doc-1");
        hit.setChunkId("chunk-1");
        hit.setCharStart(10);
        hit.setCharEnd(32);
        hit.setContent("员工年假需要直属主管审批。");
        hit.setRrfScore(new BigDecimal("0.03"));
        hit.setRetrievalChannels(List.of("KEYWORD", "VECTOR"));
        hit.setChannelRanks(Map.of("KEYWORD", 1, "VECTOR", 2));
        hit.setChannelScores(Map.of("KEYWORD", new BigDecimal("1.2")));
        hit.setDedupGroupSize(2);
        hit.setRepresentativeChunk(true);
        hit.setRerankScore(new BigDecimal("0.88"));
        hit.setRerankReasonCode("MODEL_SCORE");
        hit.setMetadata(Map.of("embedding", List.of(0.1, 0.2), "sourceType", "policy"));
        HybridRetrievalDiagnostics diagnostics = new HybridRetrievalDiagnostics();
        diagnostics.setFusionStrategy("RRF");
        diagnostics.setKeywordHitCount(1);
        diagnostics.setVectorHitCount(1);
        diagnostics.setReturnedHitCount(1);
        diagnostics.setFusedCandidateCount(4);
        diagnostics.setDedupedCandidateCount(1);
        diagnostics.setRrfK(60);
        diagnostics.setMaxChunksPerDocument(1);
        diagnostics.setChannelHitCounts(Map.of("KEYWORD", 1, "VECTOR", 1));
        diagnostics.setChannelWeights(Map.of("KEYWORD", 1.0d));
        diagnostics.setPermissionEvidenceId("perm-evidence");
        diagnostics.setPermissionVersion("perm-v1");
        diagnostics.setFilterDigest("sha256:abc123");
        diagnostics.setRerankStatus("SKIPPED");
        diagnostics.setRerankSkippedReason("DISABLED");
        HybridSearchResponse response = new HybridSearchResponse();
        response.setHits(List.of(hit));
        response.setDiagnostics(diagnostics);

        var result = mapper.toAdapterResult(response, 5);

        assertThat(result.getHits()).singleElement().satisfies(evidence -> {
            assertThat(evidence.getChunkId()).isEqualTo("chunk-1");
            assertThat(evidence.getContent()).isEqualTo("员工年假需要直属主管审批。");
            assertThat(evidence.getCharStart()).isEqualTo(10);
            assertThat(evidence.getCharEnd()).isEqualTo(32);
            assertThat(evidence.getRrfScore()).isEqualByComparingTo("0.03");
            assertThat(evidence.getRetrievalChannels()).containsExactly("KEYWORD", "VECTOR");
            assertThat(evidence.getMetadata()).containsEntry("sourceType", "policy");
            assertThat(evidence.getMetadata()).containsEntry("dedupGroupSize", 2);
            assertThat(evidence.getMetadata()).containsEntry("representativeChunk", true);
            assertThat(evidence.getMetadata()).containsEntry("rerankReasonCode", "MODEL_SCORE");
            assertThat(evidence.getMetadata()).containsKeys("channelRanks", "channelScores", "rerankScore");
            assertThat(evidence.getMetadata()).doesNotContainKey("embedding");
        });
        assertThat(result.getRetrievalDiagnostics().getFusionStrategy()).isEqualTo("RRF");
        assertThat(result.getRetrievalDiagnostics().getFusedCandidateCount()).isEqualTo(4);
        assertThat(result.getRetrievalDiagnostics().getDedupedCandidateCount()).isEqualTo(1);
        assertThat(result.getRetrievalDiagnostics().getChannelHitCounts()).containsEntry("KEYWORD", 1);
        assertThat(result.getRetrievalDiagnostics().getPermissionEvidenceId()).isEqualTo("perm-evidence");
        assertThat(result.getRetrievalDiagnostics().getPermissionVersion()).isEqualTo("perm-v1");
        assertThat(result.getRetrievalDiagnostics().getFilterDigest()).isEqualTo("sha256:abc123");
        assertThat(result.getRetrievalDiagnostics().getRerankStatus()).isEqualTo("SKIPPED");
    }
}
