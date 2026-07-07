package com.dylan.esquery.service;

import com.dylan.esquery.api.model.HybridSearchHit;
import com.dylan.esquery.api.model.HybridSearchRequest;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 使用 RRF 将关键词召回和向量召回结果融合为稳定排序。
 */
@Component
public class HybridSearchMerger {

	private static final MathContext SCORE_CONTEXT = MathContext.DECIMAL64;
	private static final String EMBEDDING_FIELD = "embedding";

	private final ObjectMapper objectMapper;

	public HybridSearchMerger(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	public List<HybridSearchHit> merge(
			List<JsonNode> keywordHits,
			List<JsonNode> vectorHits,
			HybridSearchRequest request) {
		int rrfK = positiveOrDefault(request.getRrfK(), 60, "rrfK");
		int topK = positiveOrDefault(request.getTopK(), 8, "topK");
		Map<String, MergeCandidate> candidates = new LinkedHashMap<>();
		addHits(candidates, keywordHits, "KEYWORD", rrfK);
		addHits(candidates, vectorHits, "VECTOR", rrfK);
		return candidates.values().stream()
				.map(MergeCandidate::toHit)
				.sorted(Comparator
						.comparing(HybridSearchHit::getRrfScore, Comparator.nullsLast(Comparator.reverseOrder()))
						.thenComparing(HybridSearchHit::getScore, Comparator.nullsLast(Comparator.reverseOrder()))
						.thenComparing(HybridSearchHit::getDocumentId, Comparator.nullsLast(String::compareTo))
						.thenComparing(HybridSearchHit::getChunkIndex, Comparator.nullsLast(Integer::compareTo)))
				.limit(topK)
				.toList();
	}

	private void addHits(
			Map<String, MergeCandidate> candidates,
			List<JsonNode> hits,
			String channel,
			int rrfK) {
		for (int i = 0; i < hits.size(); i++) {
			JsonNode hit = hits.get(i);
			JsonNode source = hit.path("_source");
			String key = firstText(source, "chunkId", firstText(source, "documentId", text(hit, "_id", "hit-" + i)));
			MergeCandidate candidate = candidates.computeIfAbsent(key, ignored -> new MergeCandidate(toBaseHit(hit)));
			int rank = i + 1;
			candidate.add(channel, rank, hitScore(hit), rrfContribution(rrfK, rank));
		}
	}

	private HybridSearchHit toBaseHit(JsonNode hit) {
		JsonNode source = hit.path("_source");
		HybridSearchHit target = new HybridSearchHit();
		target.setDocumentId(firstText(source, "documentId", text(hit, "_id", null)));
		target.setChunkId(firstText(source, "chunkId", target.getDocumentId()));
		target.setChunkIndex(integer(source, "chunkIndex"));
		target.setTitle(text(source, "title", null));
		target.setSourceType(text(source, "sourceType", null));
		target.setSection(text(source, "section", null));
		target.setPage(integer(source, "page"));
		target.setSourceUri(text(source, "sourceUri", null));
		target.setSnippet(firstText(source, "snippet", text(source, "content", null)));
		target.setContent(text(source, "content", null));
		target.setContextBefore(stringList(source.path("contextBefore")));
		target.setContextAfter(stringList(source.path("contextAfter")));
		target.setCharStart(integer(source, "charStart"));
		target.setCharEnd(integer(source, "charEnd"));
		if (source.isObject()) {
			@SuppressWarnings("unchecked")
			Map<String, Object> metadata = objectMapper.convertValue(source, Map.class);
			metadata.remove(EMBEDDING_FIELD);
			target.setMetadata(metadata);
		}
		return target;
	}

	private static BigDecimal rrfContribution(int rrfK, int rank) {
		return BigDecimal.ONE.divide(BigDecimal.valueOf((long) rrfK + rank), SCORE_CONTEXT);
	}

	private static BigDecimal hitScore(JsonNode hit) {
		JsonNode score = hit.path("_score");
		return score.isNumber() ? score.decimalValue() : null;
	}

	static int positiveOrDefault(Integer value, int defaultValue, String name) {
		int resolved = value == null ? defaultValue : value;
		if (resolved <= 0) {
			throw new IllegalArgumentException(name + " must be greater than 0");
		}
		return resolved;
	}

	private static Integer integer(JsonNode source, String field) {
		JsonNode value = source.path(field);
		return value.isInt() ? value.asInt() : null;
	}

	private static String firstText(JsonNode source, String field, String fallback) {
		String value = text(source, field, null);
		return value == null || value.isBlank() ? fallback : value;
	}

	private static String text(JsonNode source, String field, String fallback) {
		JsonNode value = source.path(field);
		if (value.isMissingNode() || value.isNull()) {
			return fallback;
		}
		return value.asText();
	}

	private static List<String> stringList(JsonNode node) {
		if (!node.isArray()) {
			return List.of();
		}
		List<String> values = new ArrayList<>();
		node.forEach(item -> values.add(item.asText()));
		return values;
	}

	private static final class MergeCandidate {
		private final HybridSearchHit hit;
		private BigDecimal rrfScore = BigDecimal.ZERO;
		private BigDecimal maxScore;
		private final List<String> channels = new ArrayList<>();

		private MergeCandidate(HybridSearchHit hit) {
			this.hit = hit;
		}

		private void add(String channel, int rank, BigDecimal sourceScore, BigDecimal rrfContribution) {
			channels.add(channel);
			rrfScore = rrfScore.add(rrfContribution, SCORE_CONTEXT);
			if (sourceScore != null && (maxScore == null || sourceScore.compareTo(maxScore) > 0)) {
				maxScore = sourceScore;
			}
			if ("KEYWORD".equals(channel)) {
				hit.setKeywordRank(rank);
			}
			if ("VECTOR".equals(channel)) {
				hit.setVectorRank(rank);
			}
		}

		private HybridSearchHit toHit() {
			hit.setRrfScore(rrfScore);
			hit.setScore(maxScore);
			hit.setRetrievalChannels(List.copyOf(channels));
			return hit;
		}
	}
}
