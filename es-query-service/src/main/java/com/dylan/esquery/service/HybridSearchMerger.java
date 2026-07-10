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
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

/**
 * 使用 RRF 将关键词召回和向量召回结果融合为稳定排序。
 */
@Component
public class HybridSearchMerger {

	private static final MathContext SCORE_CONTEXT = MathContext.DECIMAL64;
	private static final String EMBEDDING_FIELD = "embedding";
	private static final String EMBEDDING_TEXT_FIELD = "embeddingText";

	private final ObjectMapper objectMapper;

	public HybridSearchMerger(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	public List<HybridSearchHit> merge(
			List<JsonNode> keywordHits,
			List<JsonNode> vectorHits,
			HybridSearchRequest request) {
		Map<String, List<JsonNode>> hitsByChannel = new LinkedHashMap<>();
		hitsByChannel.put("BM25", keywordHits);
		hitsByChannel.put("DENSE_VECTOR", vectorHits);
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
			hitsByChannel.forEach((channel, hits) -> addHits(
					candidates,
					hits,
					channel,
					rrfK,
					channelWeight(request, channel),
					request));
		}
		List<MergeCandidate> sorted = candidates.values().stream()
				.sorted(Comparator
						.comparing(MergeCandidate::rrfScore, Comparator.nullsLast(Comparator.reverseOrder()))
						.thenComparing(MergeCandidate::bestRank, Comparator.nullsLast(Integer::compareTo))
						.thenComparing(MergeCandidate::channelCount, Comparator.reverseOrder())
						.thenComparing(candidate -> candidate.hit.getDocumentId(), Comparator.nullsLast(String::compareTo))
						.thenComparing(candidate -> candidate.hit.getChunkIndex(), Comparator.nullsLast(Integer::compareTo))
						.thenComparing(candidate -> candidate.hit.getChunkId(), Comparator.nullsLast(String::compareTo)))
				.toList();
		Map<String, Long> groupSizes = new HashMap<>();
		for (MergeCandidate candidate : sorted) {
			groupSizes.merge(dedupKey(candidate.hit, request), 1L, Long::sum);
		}
		Map<String, Integer> selectedByDocument = new HashMap<>();
		List<HybridSearchHit> result = new ArrayList<>();
		for (MergeCandidate candidate : sorted) {
			String dedupKey = dedupKey(candidate.hit, request);
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
			double weight,
			HybridSearchRequest request) {
		if (hits == null || hits.isEmpty()) {
			return;
		}
		String normalizedChannel = normalizeChannel(channel);
		for (int i = 0; i < hits.size(); i++) {
			JsonNode hit = hits.get(i);
			JsonNode source = hit.path("_source");
			String key = firstText(source, "chunkId", firstText(source, "documentId", text(hit, "_id", "hit-" + i)));
			String candidateKey = candidateKey(request, key);
			HybridSearchHit baseHit = toBaseHit(hit, request);
			MergeCandidate candidate = candidates.computeIfAbsent(candidateKey, ignored -> new MergeCandidate(baseHit));
			int rank = i + 1;
			candidate.add(normalizedChannel, rank, hitScore(hit), rrfContribution(rrfK, rank, weight), baseHit.getHitFields());
		}
	}

	private HybridSearchHit toBaseHit(JsonNode hit, HybridSearchRequest request) {
		JsonNode source = hit.path("_source");
		HybridSearchHit target = new HybridSearchHit();
		target.setDocumentId(firstText(source, "documentId", text(hit, "_id", null)));
		target.setChunkId(firstText(source, "chunkId", target.getDocumentId()));
		target.setIndexAlias(request.getIndexAlias());
		target.setProfileVersion(request.getProfileVersion());
		target.setPermissionEvidenceId(request.getPermissionEvidenceId());
		target.setChunkIndex(integer(source, "chunkIndex"));
		target.setTitle(text(source, "title", null));
		target.setSourceType(text(source, "sourceType", null));
		target.setSection(text(source, "section", null));
		target.setPage(integer(source, "page"));
		target.setSourceUri(text(source, "sourceUri", null));
		target.setSnippet(firstText(source, "snippet", text(source, "content", null)));
		target.setContent(text(source, "content", null));
		target.setCitationText(text(source, "citationText", null));
		target.setGenerationText(text(source, "generationText", null));
		target.setContextBefore(stringList(source.path("contextBefore")));
		target.setContextAfter(stringList(source.path("contextAfter")));
		List<String> hitFields = stringList(source.path("hitFields"));
		if (hitFields.isEmpty()) {
			hitFields = stringList(hit.path("matched_queries"));
		}
		target.setHitFields(hitFields.isEmpty() ? null : hitFields);
		target.setCharStart(integer(source, "charStart"));
		target.setCharEnd(integer(source, "charEnd"));
		if (source.isObject()) {
			@SuppressWarnings("unchecked")
			Map<String, Object> metadata = objectMapper.convertValue(source, Map.class);
			metadata.remove(EMBEDDING_FIELD);
			metadata.remove(EMBEDDING_TEXT_FIELD);
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

	private static String candidateKey(HybridSearchRequest request, String chunkKey) {
		return nullToEmpty(request.getIndexAlias())
				+ "|" + nullToEmpty(request.getProfileVersion())
				+ "|" + nullToEmpty(request.getPermissionEvidenceId())
				+ "|" + nullToEmpty(chunkKey);
	}

	private static String dedupKey(HybridSearchHit hit, HybridSearchRequest request) {
		String documentKey = hit.getDocumentId() != null && !hit.getDocumentId().isBlank()
				? hit.getDocumentId()
				: hit.getChunkId();
		return nullToEmpty(request.getIndexAlias())
				+ "|" + nullToEmpty(request.getProfileVersion())
				+ "|" + nullToEmpty(request.getPermissionEvidenceId())
				+ "|" + nullToEmpty(documentKey);
	}

	private static String nullToEmpty(String value) {
		return value == null ? "" : value;
	}

	private static final class MergeCandidate {
		private final HybridSearchHit hit;
		private BigDecimal rrfScore = BigDecimal.ZERO;
		private BigDecimal maxScore;
		private final List<String> channels = new ArrayList<>();
		private final Map<String, Integer> channelRanks = new LinkedHashMap<>();
		private final Map<String, BigDecimal> channelScores = new LinkedHashMap<>();
		private final LinkedHashSet<String> hitFields = new LinkedHashSet<>();
		private Integer bestRank;

		private MergeCandidate(HybridSearchHit hit) {
			this.hit = hit;
			if (hit.getHitFields() != null) {
				hitFields.addAll(hit.getHitFields());
			}
		}

		private void add(
				String channel,
				int rank,
				BigDecimal sourceScore,
				BigDecimal rrfContribution,
				List<String> sourceHitFields) {
			if (channelRanks.containsKey(channel)) {
				return;
			}
			channels.add(channel);
			channelRanks.put(channel, rank);
			bestRank = bestRank == null ? rank : Math.min(bestRank, rank);
			rrfScore = rrfScore.add(rrfContribution, SCORE_CONTEXT);
			if (sourceScore != null && (maxScore == null || sourceScore.compareTo(maxScore) > 0)) {
				maxScore = sourceScore;
			}
			if (sourceScore != null) {
				channelScores.put(channel, sourceScore);
			}
			if (sourceHitFields != null) {
				sourceHitFields.stream()
						.filter(value -> value != null && !value.isBlank())
						.forEach(hitFields::add);
			}
			if ("BM25".equals(channel) || "EXACT".equals(channel) || "PHRASE".equals(channel)) {
				hit.setKeywordRank(rank);
			}
			if ("DENSE_VECTOR".equals(channel)) {
				hit.setVectorRank(rank);
			}
		}

		private HybridSearchHit toHit() {
			hit.setRrfScore(rrfScore);
			hit.setScore(maxScore);
			hit.setRetrievalChannels(List.copyOf(channels));
			hit.setChannelRanks(Map.copyOf(channelRanks));
			hit.setChannelScores(Map.copyOf(channelScores));
			if (!hitFields.isEmpty()) {
				hit.setHitFields(List.copyOf(hitFields));
			}
			return hit;
		}

		private BigDecimal rrfScore() {
			return rrfScore;
		}

		private Integer bestRank() {
			return bestRank;
		}

		private Integer channelCount() {
			return channelRanks.size();
		}
	}
}
