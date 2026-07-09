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
import java.util.HashMap;
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
		Map<String, List<JsonNode>> hitsByChannel = new LinkedHashMap<>();
		hitsByChannel.put("KEYWORD", keywordHits);
		hitsByChannel.put("VECTOR", vectorHits);
		return merge(hitsByChannel, request);
	}

	public List<HybridSearchHit> merge(
			Map<String, List<JsonNode>> hitsByChannel,
			HybridSearchRequest request) {
		int rrfK = positiveOrDefault(request.getRrfK(), 60, "rrfK");
		int topK = positiveOrDefault(request.getTopK(), 8, "topK");
		int maxChunksPerDocument = positiveOrDefault(request.getMaxChunksPerDocument(), 1, "maxChunksPerDocument");
		Map<String, MergeCandidate> candidates = new LinkedHashMap<>();
		if (hitsByChannel != null) {
			hitsByChannel.forEach((channel, hits) -> addHits(candidates, hits, channel, rrfK, channelWeight(request, channel)));
		}
		List<MergeCandidate> sorted = candidates.values().stream()
				.sorted(Comparator
						.comparing(MergeCandidate::rrfScore, Comparator.nullsLast(Comparator.reverseOrder()))
						.thenComparing(MergeCandidate::maxScore, Comparator.nullsLast(Comparator.reverseOrder()))
						.thenComparing(candidate -> candidate.hit.getDocumentId(), Comparator.nullsLast(String::compareTo))
						.thenComparing(candidate -> candidate.hit.getChunkIndex(), Comparator.nullsLast(Integer::compareTo)))
				.toList();
		Map<String, Long> groupSizes = new HashMap<>();
		for (MergeCandidate candidate : sorted) {
			groupSizes.merge(dedupKey(candidate.hit), 1L, Long::sum);
		}
		Map<String, Integer> selectedByDocument = new HashMap<>();
		List<HybridSearchHit> result = new ArrayList<>();
		for (MergeCandidate candidate : sorted) {
			String dedupKey = dedupKey(candidate.hit);
			int selected = selectedByDocument.getOrDefault(dedupKey, 0);
			if (selected >= maxChunksPerDocument) {
				continue;
			}
			HybridSearchHit hit = candidate.toHit();
			hit.setDedupGroupSize(groupSizes.getOrDefault(dedupKey, 1L).intValue());
			hit.setRepresentativeChunk(selected == 0);
			result.add(hit);
			selectedByDocument.put(dedupKey, selected + 1);
			if (result.size() >= topK) {
				break;
			}
		}
		return result;
	}

	private void addHits(
			Map<String, MergeCandidate> candidates,
			List<JsonNode> hits,
			String channel,
			int rrfK,
			double weight) {
		if (hits == null || hits.isEmpty()) {
			return;
		}
		String normalizedChannel = normalizeChannel(channel);
		for (int i = 0; i < hits.size(); i++) {
			JsonNode hit = hits.get(i);
			JsonNode source = hit.path("_source");
			String key = firstText(source, "chunkId", firstText(source, "documentId", text(hit, "_id", "hit-" + i)));
			MergeCandidate candidate = candidates.computeIfAbsent(key, ignored -> new MergeCandidate(toBaseHit(hit)));
			int rank = i + 1;
			candidate.add(normalizedChannel, rank, hitScore(hit), rrfContribution(rrfK, rank, weight));
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

	private static BigDecimal rrfContribution(int rrfK, int rank, double weight) {
		BigDecimal base = BigDecimal.ONE.divide(BigDecimal.valueOf((long) rrfK + rank), SCORE_CONTEXT);
		return base.multiply(BigDecimal.valueOf(weight), SCORE_CONTEXT);
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

	private static String normalizeChannel(String channel) {
		return channel == null || channel.isBlank()
				? "UNKNOWN"
				: channel.trim().toUpperCase(java.util.Locale.ROOT);
	}

	private static double channelWeight(HybridSearchRequest request, String channel) {
		if (request.getChannelWeights() == null || channel == null) {
			return 1.0d;
		}
		Double weight = request.getChannelWeights().get(channel);
		if (weight == null) {
			weight = request.getChannelWeights().get(normalizeChannel(channel));
		}
		return weight == null || !Double.isFinite(weight) || weight <= 0.0d ? 1.0d : weight;
	}

	private static String dedupKey(HybridSearchHit hit) {
		if (hit.getDocumentId() != null && !hit.getDocumentId().isBlank()) {
			return hit.getDocumentId();
		}
		return hit.getChunkId() == null ? "" : hit.getChunkId();
	}

	private static final class MergeCandidate {
		private final HybridSearchHit hit;
		private BigDecimal rrfScore = BigDecimal.ZERO;
		private BigDecimal maxScore;
		private final List<String> channels = new ArrayList<>();
		private final Map<String, Integer> channelRanks = new LinkedHashMap<>();
		private final Map<String, BigDecimal> channelScores = new LinkedHashMap<>();

		private MergeCandidate(HybridSearchHit hit) {
			this.hit = hit;
		}

		private void add(String channel, int rank, BigDecimal sourceScore, BigDecimal rrfContribution) {
			channels.add(channel);
			channelRanks.put(channel, rank);
			rrfScore = rrfScore.add(rrfContribution, SCORE_CONTEXT);
			if (sourceScore != null && (maxScore == null || sourceScore.compareTo(maxScore) > 0)) {
				maxScore = sourceScore;
			}
			if (sourceScore != null) {
				channelScores.put(channel, sourceScore);
			}
			if ("KEYWORD".equals(channel) || "BM25".equals(channel) || "EXACT".equals(channel) || "PHRASE".equals(channel)) {
				hit.setKeywordRank(rank);
			}
			if ("VECTOR".equals(channel) || "DENSE_VECTOR".equals(channel)) {
				hit.setVectorRank(rank);
			}
		}

		private HybridSearchHit toHit() {
			hit.setRrfScore(rrfScore);
			hit.setScore(maxScore);
			hit.setRetrievalChannels(List.copyOf(channels));
			hit.setChannelRanks(Map.copyOf(channelRanks));
			hit.setChannelScores(Map.copyOf(channelScores));
			return hit;
		}

		private BigDecimal rrfScore() {
			return rrfScore;
		}

		private BigDecimal maxScore() {
			return maxScore;
		}
	}
}
