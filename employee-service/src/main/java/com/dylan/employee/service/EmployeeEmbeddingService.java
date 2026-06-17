package com.dylan.employee.service;

import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

/**
 * 员工向量服务，负责调用本地向量模型生成 embedding。
 */
@Service
public class EmployeeEmbeddingService {
	private final RestTemplate restTemplate;
	private final String provider;
	private final String baseUrl;
	private final String apiKey;
	private final String model;
	private final int defaultDims;

	/**
	 * 创建 EmployeeEmbeddingService 实例并注入所需依赖。
	 */
	public EmployeeEmbeddingService(
			@Value("${employee.embedding.provider:bge}") String provider,
			@Value("${employee.embedding.base-url:http://127.0.0.1:8908}") String baseUrl,
			@Value("${employee.embedding.api-key:}") String apiKey,
			@Value("${employee.embedding.model:bge-m3}") String model,
			@Value("${employee.embedding.dims:1024}") int defaultDims) {
		this.restTemplate = new RestTemplate();
		this.provider = provider == null || provider.isBlank() ? "bge" : provider;
		this.baseUrl = removeTrailingSlash(baseUrl);
		this.apiKey = apiKey;
		this.model = model;
		this.defaultDims = defaultDims;
	}

	/**
	 * 处理 embed 相关逻辑。
	 */
	public List<Double> embed(String text, int dims) {
		if ("bge".equalsIgnoreCase(provider)) {
			return bgeEmbed(text, dims);
		}
		return openAiCompatibleEmbed(text, dims);
	}

	/**
	 * 处理 openAiCompatibleEmbed 相关逻辑。
	 */
	private List<Double> openAiCompatibleEmbed(String text, int dims) {
		if (apiKey == null || apiKey.isBlank()) {
			throw new IllegalStateException("employee.embedding.api-key must be configured before using vector index");
		}
		int targetDims = dims <= 0 ? defaultDims : dims;
		EmbeddingRequest request = new EmbeddingRequest();
		request.setModel(model);
		request.setInput(text == null || text.isBlank() ? " " : text);
		request.setDimensions(targetDims);

		HttpHeaders headers = new HttpHeaders();
		headers.setContentType(MediaType.APPLICATION_JSON);
		headers.setBearerAuth(apiKey);

		EmbeddingResponse response = restTemplate.postForObject(baseUrl + "/embeddings",
				new HttpEntity<>(request, headers), EmbeddingResponse.class);
		if (response == null || response.getData() == null || response.getData().isEmpty()
				|| response.getData().get(0).getEmbedding() == null) {
			throw new IllegalStateException("OpenAI-compatible embedding response is empty");
		}
		return response.getData().get(0).getEmbedding();
	}

	/**
	 * 处理 bgeEmbed 相关逻辑。
	 */
	private List<Double> bgeEmbed(String text, int dims) {
		BgeEmbeddingRequest request = new BgeEmbeddingRequest();
		request.setTexts(List.of(text == null || text.isBlank() ? " " : text));

		HttpHeaders headers = new HttpHeaders();
		headers.setContentType(MediaType.APPLICATION_JSON);
		if (apiKey != null && !apiKey.isBlank()) {
			headers.setBearerAuth(apiKey);
		}

		BgeEmbeddingResponse response = restTemplate.postForObject(baseUrl + "/embed",
				new HttpEntity<>(request, headers), BgeEmbeddingResponse.class);
		if (response == null || response.getVectors() == null || response.getVectors().isEmpty()
				|| response.getVectors().get(0) == null) {
			throw new IllegalStateException("BGE embedding response is empty");
		}
		int targetDims = dims <= 0 ? defaultDims : dims;
		List<Double> vector = response.getVectors().get(0);
		if (targetDims > 0 && vector.size() != targetDims) {
			throw new IllegalStateException("BGE embedding dims mismatch: expected " + targetDims + ", actual "
					+ vector.size());
		}
		return vector;
	}

	/**
	 * 移除或裁剪指定内容。
	 */
	private String removeTrailingSlash(String value) {
		if (value == null || value.isBlank()) {
			return "http://127.0.0.1:8908";
		}
		return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
	}

	public static class EmbeddingRequest {
		private String model;
		private String input;
		private Integer dimensions;

		public String getModel() {
			return model;
		}

		public void setModel(String model) {
			this.model = model;
		}

		public String getInput() {
			return input;
		}

		public void setInput(String input) {
			this.input = input;
		}

		public Integer getDimensions() {
			return dimensions;
		}

		public void setDimensions(Integer dimensions) {
			this.dimensions = dimensions;
		}
	}

	public static class EmbeddingResponse {
		private List<EmbeddingData> data;
		private Map<String, Object> usage;

		public List<EmbeddingData> getData() {
			return data;
		}

		public void setData(List<EmbeddingData> data) {
			this.data = data;
		}

		public Map<String, Object> getUsage() {
			return usage;
		}

		public void setUsage(Map<String, Object> usage) {
			this.usage = usage;
		}
	}

	public static class EmbeddingData {
		private List<Double> embedding;

		public List<Double> getEmbedding() {
			return embedding;
		}

		public void setEmbedding(List<Double> embedding) {
			this.embedding = embedding;
		}
	}

	public static class BgeEmbeddingRequest {
		private List<String> texts;

		public List<String> getTexts() {
			return texts;
		}

		public void setTexts(List<String> texts) {
			this.texts = texts;
		}
	}

	public static class BgeEmbeddingResponse {
		private Integer dim;
		private List<List<Double>> vectors;

		public Integer getDim() {
			return dim;
		}

		public void setDim(Integer dim) {
			this.dim = dim;
		}

		public List<List<Double>> getVectors() {
			return vectors;
		}

		public void setVectors(List<List<Double>> vectors) {
			this.vectors = vectors;
		}
	}
}
