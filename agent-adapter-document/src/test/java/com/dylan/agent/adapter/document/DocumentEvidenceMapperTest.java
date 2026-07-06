package com.dylan.agent.adapter.document;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

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
        });
        assertThat(result.getCoveredDocumentCount()).isEqualTo(1);
    }
}
