package com.dylan.esquery.service;

import com.dylan.esquery.api.model.HybridSearchRequest;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class HybridSearchMergerTest {

	private final ObjectMapper objectMapper = new ObjectMapper();
	private final HybridSearchMerger merger = new HybridSearchMerger(objectMapper);

	@Test
	void mergesKeywordAndVectorHitsByRrf() throws Exception {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setTopK(3);
		request.setRrfK(60);

		List<JsonNode> keywordHits = List.of(hit("doc-1", "chunk-1", 1.2), hit("doc-2", "chunk-2", 1.0));
		List<JsonNode> vectorHits = List.of(hit("doc-2", "chunk-2", 0.9), hit("doc-3", "chunk-3", 0.8));

		var hits = merger.merge(keywordHits, vectorHits, request);

		assertThat(hits).hasSize(3);
		assertThat(hits.get(0).getChunkId()).isEqualTo("chunk-2");
		assertThat(hits.get(0).getRetrievalChannels()).containsExactly("KEYWORD", "VECTOR");
		assertThat(hits.get(0).getKeywordRank()).isEqualTo(2);
		assertThat(hits.get(0).getVectorRank()).isEqualTo(1);
		assertThat(hits.get(0).getCharStart()).isEqualTo(10);
		assertThat(hits.get(0).getCharEnd()).isEqualTo(32);
		assertThat(hits.get(0).getMetadata()).doesNotContainKey("embedding");
	}

	@Test
	void fallsBackToDocumentIdWhenChunkIdIsMissing() throws Exception {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setTopK(2);
		request.setRrfK(60);

		JsonNode keywordHit = objectMapper.readTree("""
				{
				  "_id": "hit-1",
				  "_score": 1.0,
				  "_source": {
				    "documentId": "doc-1",
				    "chunkIndex": 1,
				    "title": "休假政策"
				  }
				}
				""");
		JsonNode vectorHit = objectMapper.readTree("""
				{
				  "_id": "hit-2",
				  "_score": 0.8,
				  "_source": {
				    "documentId": "doc-1",
				    "chunkIndex": 1,
				    "title": "休假政策"
				  }
				}
				""");

		var hits = merger.merge(List.of(keywordHit), List.of(vectorHit), request);

		assertThat(hits).hasSize(1);
		assertThat(hits.get(0).getDocumentId()).isEqualTo("doc-1");
		assertThat(hits.get(0).getChunkId()).isEqualTo("doc-1");
		assertThat(hits.get(0).getRetrievalChannels()).containsExactly("KEYWORD", "VECTOR");
	}

	private JsonNode hit(String documentId, String chunkId, double score) throws Exception {
		return objectMapper.readTree("""
				{
				  "_id": "%s",
				  "_score": %s,
				  "_source": {
				    "documentId": "%s",
				    "chunkId": "%s",
				    "chunkIndex": 1,
				    "charStart": 10,
				    "charEnd": 32,
				    "title": "休假政策",
				    "embedding": [0.1, 0.2],
				    "content": "员工年假需要直属主管审批。"
				  }
				}
				""".formatted(documentId, score, documentId, chunkId));
	}
}
