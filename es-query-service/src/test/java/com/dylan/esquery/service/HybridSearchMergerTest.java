package com.dylan.esquery.service;

import com.dylan.esquery.api.model.HybridSearchRequest;
import com.dylan.esquery.api.model.HybridSearchHit;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class HybridSearchMergerTest {

	private final ObjectMapper objectMapper = new ObjectMapper();
	private final HybridSearchMerger merger = new HybridSearchMerger(objectMapper);

	@Test
	void mergesKeywordAndVectorHitsByRrf() throws Exception {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setTopK(3);
		request.setRrfK(60);
		request.setIndexAlias("agent-doc-tax-policy-read");
		request.setProfileVersion("v2");
		request.setPermissionEvidenceId("perm-evidence");

		List<JsonNode> keywordHits = List.of(hit("doc-1", "chunk-1", 1.2), hit("doc-2", "chunk-2", 1.0));
		List<JsonNode> vectorHits = List.of(hit("doc-2", "chunk-2", 0.9), hit("doc-3", "chunk-3", 0.8));

		var hits = merger.merge(keywordHits, vectorHits, request);

		assertThat(hits).hasSize(3);
		assertThat(hits.get(0).getChunkId()).isEqualTo("chunk-2");
		assertThat(hits.get(0).getRetrievalChannels()).containsExactly("KEYWORD", "VECTOR");
		assertThat(hits.get(0).getKeywordRank()).isEqualTo(2);
		assertThat(hits.get(0).getVectorRank()).isEqualTo(1);
		assertThat(hits.get(0).getIndexAlias()).isEqualTo("agent-doc-tax-policy-read");
		assertThat(hits.get(0).getProfileVersion()).isEqualTo("v2");
		assertThat(hits.get(0).getPermissionEvidenceId()).isEqualTo("perm-evidence");
		assertThat(hits.get(0).getCharStart()).isEqualTo(10);
		assertThat(hits.get(0).getCharEnd()).isEqualTo(32);
		assertThat(hits.get(0).getMetadata()).doesNotContainKey("embedding");
	}

	@Test
	void usesStableTieBreakerInsteadOfSourceScoreAcrossChannels() throws Exception {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setTopK(2);
		request.setRrfK(60);
		Map<String, List<JsonNode>> hitsByChannel = new LinkedHashMap<>();
		hitsByChannel.put("BM25", List.of(hit("doc-b", "doc-b-c1", 100.0)));
		hitsByChannel.put("EXACT", List.of(hit("doc-a", "doc-a-c1", 0.1)));

		var hits = merger.merge(hitsByChannel, request);

		assertThat(hits).hasSize(2);
		assertThat(hits).extracting(HybridSearchHit::getDocumentId)
				.containsExactly("doc-a", "doc-b");
	}

	@Test
	void mapsMatchedQueriesToHitFieldsDiagnostics() throws Exception {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setTopK(1);
		request.setRrfK(60);
		JsonNode exactHit = objectMapper.readTree("""
				{
				  "_id": "chunk-1",
				  "_score": 1.0,
				  "matched_queries": ["EXACT:documentNumber"],
				  "_source": {
				    "documentId": "doc-1",
				    "chunkId": "chunk-1",
				    "chunkIndex": 1,
				    "title": "休假政策"
				  }
				}
				""");

		var hits = merger.merge(Map.of("EXACT", List.of(exactHit)), request);

		assertThat(hits).singleElement()
				.satisfies(hit -> assertThat(hit.getHitFields()).containsExactly("EXACT:documentNumber"));
	}

	@Test
	void mergesHitFieldsFromMultipleChannelsForSameChunk() throws Exception {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setTopK(1);
		request.setRrfK(60);
		Map<String, List<JsonNode>> hitsByChannel = new LinkedHashMap<>();
		hitsByChannel.put("BM25", List.of(hitWithMatchedQueries(
				"doc-1", "chunk-1", 1, 1.0, List.of("BM25:title"))));
		hitsByChannel.put("EXACT", List.of(hitWithMatchedQueries(
				"doc-1", "chunk-1", 1, 0.9, List.of("EXACT:documentNo"))));

		var hits = merger.merge(hitsByChannel, request);

		assertThat(hits).singleElement()
				.satisfies(hit -> assertThat(hit.getHitFields())
						.containsExactly("BM25:title", "EXACT:documentNo"));
	}

	@Test
	void usesChunkIndexAsFinalTieBreakerBeforeChunkId() throws Exception {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setTopK(2);
		request.setRrfK(60);
		request.setMaxChunksPerDocument(2);
		Map<String, List<JsonNode>> hitsByChannel = new LinkedHashMap<>();
		hitsByChannel.put("BM25", List.of(hit("doc-1", "chunk-a", 2, 1.0)));
		hitsByChannel.put("EXACT", List.of(hit("doc-1", "chunk-z", 1, 1.0)));

		var hits = merger.merge(hitsByChannel, request);

		assertThat(hits).extracting(HybridSearchHit::getChunkId)
				.containsExactly("chunk-z", "chunk-a");
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

	@Test
	void fusesMultipleChannelsAndLimitsChunksPerDocument() throws Exception {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setTopK(3);
		request.setRrfK(60);
		request.setMaxChunksPerDocument(1);
		request.setChannelWeights(Map.of("BM25", 2.0d));
		Map<String, List<JsonNode>> hitsByChannel = new LinkedHashMap<>();
		hitsByChannel.put("BM25", List.of(
				hit("doc-1", "doc-1-c1", 1, 1.2),
				hit("doc-2", "doc-2-c1", 1, 1.0)));
		hitsByChannel.put("EXACT", List.of(
				hit("doc-1", "doc-1-c1", 1, 1.1),
				hit("doc-3", "doc-3-c1", 1, 0.9)));
		hitsByChannel.put("PHRASE", List.of(
				hit("doc-1", "doc-1-c2", 2, 1.0)));
		hitsByChannel.put("DENSE_VECTOR", List.of(
				hit("doc-2", "doc-2-c1", 1, 0.8)));

		var hits = merger.merge(hitsByChannel, request);

		assertThat(hits).hasSize(3);
		assertThat(hits).extracting(hit -> hit.getDocumentId())
				.containsExactlyInAnyOrder("doc-1", "doc-2", "doc-3");
		assertThat(hits).filteredOn(hit -> "doc-1".equals(hit.getDocumentId()))
				.singleElement()
				.satisfies(hit -> {
					assertThat(hit.getRetrievalChannels()).contains("BM25", "EXACT");
					assertThat(hit.getChannelRanks()).containsEntry("BM25", 1);
					assertThat(hit.getDedupGroupSize()).isEqualTo(2);
					assertThat(hit.getRepresentativeChunk()).isTrue();
				});
	}

	private JsonNode hit(String documentId, String chunkId, double score) throws Exception {
		return hit(documentId, chunkId, 1, score);
	}

	private JsonNode hit(String documentId, String chunkId, int chunkIndex, double score) throws Exception {
		return objectMapper.readTree("""
				{
				  "_id": "%s",
				  "_score": %s,
				  "_source": {
				    "documentId": "%s",
				    "chunkId": "%s",
				    "chunkIndex": %s,
				    "charStart": 10,
				    "charEnd": 32,
				    "title": "休假政策",
				    "embedding": [0.1, 0.2],
				    "content": "员工年假需要直属主管审批。"
				  }
				}
				""".formatted(documentId, score, documentId, chunkId, chunkIndex));
	}

	private JsonNode hitWithMatchedQueries(
			String documentId,
			String chunkId,
			int chunkIndex,
			double score,
			List<String> matchedQueries) throws Exception {
		return objectMapper.readTree("""
				{
				  "_id": "%s",
				  "_score": %s,
				  "matched_queries": %s,
				  "_source": {
				    "documentId": "%s",
				    "chunkId": "%s",
				    "chunkIndex": %s,
				    "title": "休假政策"
				  }
				}
				""".formatted(chunkId, score, objectMapper.writeValueAsString(matchedQueries),
				documentId, chunkId, chunkIndex));
	}
}
