package com.dylan.esquery.web;

import java.text.Normalizer;
import java.util.List;

import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeInvalidRequestException;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

public final class KnowledgeSearchJsonCodec {
	public static final int MAX_BODY_BYTES = 128 * 1024;
	private static final int VECTOR_DIMENSION = 1024;

	private final ObjectMapper strictMapper;

	public KnowledgeSearchJsonCodec(ObjectMapper objectMapper) {
		this.strictMapper = objectMapper.copy()
				.enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
				.enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
				.enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
	}

	public KnowledgeSearchRequest decodeRequest(byte[] body) {
		if (body == null || body.length == 0 || body.length > MAX_BODY_BYTES || hasUtf8Bom(body)) {
			throw new KnowledgeInvalidRequestException();
		}
		try {
			KnowledgeSearchRequest request = strictMapper.readValue(body, KnowledgeSearchRequest.class);
			validate(request);
			return request;
		} catch (KnowledgeInvalidRequestException ex) {
			throw ex;
		} catch (Exception ex) {
			throw new KnowledgeInvalidRequestException(ex);
		}
	}

	private static void validate(KnowledgeSearchRequest request) {
		if (request == null || request.schemaVersion() != 1
				|| !List.of("tax.policy", "tax.law").contains(request.logicalDomainId())
				|| !List.of("tax-policy-v1", "tax-law-v1").contains(request.retrievalProfileId())
				|| !("tax.policy".equals(request.logicalDomainId())
						&& "tax-policy-v1".equals(request.retrievalProfileId())
						|| "tax.law".equals(request.logicalDomainId())
						&& "tax-law-v1".equals(request.retrievalProfileId()))
				|| !List.of("keyword", "vector").contains(request.path())
				|| request.limit() < 5 || request.limit() > 20) {
			throw new KnowledgeInvalidRequestException();
		}
		if ("keyword".equals(request.path())) {
			if (!validQueryText(request.queryText()) || request.queryVector() != null) {
				throw new KnowledgeInvalidRequestException();
			}
		} else if (request.queryText() != null || !validVector(request.queryVector())) {
			throw new KnowledgeInvalidRequestException();
		}
	}

	private static boolean validQueryText(String value) {
		return value != null && !value.isBlank() && value.equals(Normalizer.normalize(value, Normalizer.Form.NFC))
				&& value.codePointCount(0, value.length()) <= 1024;
	}

	private static boolean validVector(List<Double> vector) {
		return vector != null && vector.size() == VECTOR_DIMENSION
				&& vector.stream().allMatch(value -> value != null && Double.isFinite(value));
	}

	private static boolean hasUtf8Bom(byte[] body) {
		return body.length >= 3 && (body[0] & 0xff) == 0xef && (body[1] & 0xff) == 0xbb
				&& (body[2] & 0xff) == 0xbf;
	}
}
