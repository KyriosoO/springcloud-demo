package com.dylan.employee.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import com.dylan.employee.es.EsQueryClient;
import com.dylan.esquery.api.model.SearchAggregate;
import com.dylan.esquery.api.model.SearchFilter;
import com.dylan.esquery.api.model.SearchMetric;
import com.dylan.esquery.api.model.SearchMetricFunction;
import com.dylan.esquery.api.model.SearchRequest;
import com.dylan.esquery.api.model.SearchSort;
import com.dylan.esquery.api.model.SearchSortDirection;
import com.dylan.esquery.api.model.SemanticSearchRequest;
import com.dylan.esquery.api.model.VectorSearchRequest;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

class EmployeeEsServiceTest {
	private final ObjectMapper objectMapper = new ObjectMapper();
	private EsQueryClient esQueryClient;
	private EmployeeEsService employeeEsService;

	@BeforeEach
	void setUp() {
		esQueryClient = mock(EsQueryClient.class);
		employeeEsService = new EmployeeEsService(
				mock(EmployeeService.class),
				mock(EmployeeEmbeddingService.class),
				esQueryClient,
				objectMapper,
				"employee",
				"http://localhost:9210/internal/es/employees",
				1024);
	}

	@Test
	void searchBuildsExactTotalFilterAndSortDsl() throws Exception {
		when(esQueryClient.search(eq("employee"), anyString())).thenReturn("{}");

		SearchFilter filter = new SearchFilter();
		filter.setField("position");
		filter.setOperator("EQ");
		filter.setValue("HRBP");

		SearchSort sort = new SearchSort();
		sort.setField("chineseName");
		sort.setDirection(SearchSortDirection.DESC);

		SearchRequest request = new SearchRequest();
		request.setFrom(10);
		request.setSize(25);
		request.setFilters(List.of(filter));
		request.setSorts(List.of(sort));

		employeeEsService.search(request);

		JsonNode dsl = capturedDsl();
		assertThat(dsl.path("from").asInt()).isEqualTo(10);
		assertThat(dsl.path("size").asInt()).isEqualTo(25);
		assertThat(dsl.has("track_total_hits")).isFalse();
		assertThat(dsl.at("/query/term/position.keyword").asText()).isEqualTo("HRBP");
		assertThat(dsl.at("/sort/0/chineseName.keyword/order").asText()).isEqualTo("desc");
	}

	@Test
	void searchBuildsNestedTermsAndCountAggregationDsl() throws Exception {
		when(esQueryClient.search(eq("employee"), anyString())).thenReturn("{}");

		SearchMetric metric = new SearchMetric();
		metric.setFunction(SearchMetricFunction.COUNT);
		metric.setAlias("employeeCount");

		SearchAggregate aggregate = new SearchAggregate();
		aggregate.setGroupBy(List.of("position", "chineseName"));
		aggregate.setMetrics(List.of(metric));
		aggregate.setBucketSize(50);

		SearchRequest request = new SearchRequest();
		request.setAggregate(aggregate);

		employeeEsService.search(request);

		JsonNode dsl = capturedDsl();
		assertThat(dsl.path("size").asInt()).isZero();
		assertThat(dsl.at("/aggs/group_by_0_position/terms/field").asText()).isEqualTo("position.keyword");
		assertThat(dsl.at("/aggs/group_by_0_position/terms/size").asInt()).isEqualTo(50);
		assertThat(dsl.at("/aggs/group_by_0_position/aggs/group_by_1_chineseName/terms/field").asText())
				.isEqualTo("chineseName.keyword");
		assertThat(dsl.at(
				"/aggs/group_by_0_position/aggs/group_by_1_chineseName/aggs/employeeCount/value_count/field")
				.asText()).isEqualTo("idCardNo");
	}

	@Test
	void vectorSearchPassesCallerTotalHitsThreshold() {
		when(esQueryClient.vectorSearch(eq("employee"), org.mockito.ArgumentMatchers.any(VectorSearchRequest.class)))
				.thenReturn("{}");
		SemanticSearchRequest request = new SemanticSearchRequest();
		request.setQueryVector(List.of(0.1, 0.2));
		request.setTrackTotalHits(500);

		employeeEsService.vectorSearch(request);

		ArgumentCaptor<VectorSearchRequest> captor = ArgumentCaptor.forClass(VectorSearchRequest.class);
		verify(esQueryClient).vectorSearch(eq("employee"), captor.capture());
		assertThat(captor.getValue().getTrackTotalHits()).isEqualTo(500);
	}

	@Test
	void searchRejectsUnsupportedFieldInsteadOfDroppingFilter() {
		SearchFilter filter = new SearchFilter();
		filter.setField("salaryAccount");
		filter.setOperator("EQ");
		filter.setValue("123");

		SearchRequest request = new SearchRequest();
		request.setFilters(List.of(filter));

		assertThatThrownBy(() -> employeeEsService.search(request))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessage("unsupported employee search filter field: salaryAccount");
	}

	@Test
	void searchRejectsUnsupportedOperator() {
		SearchFilter filter = new SearchFilter();
		filter.setField("position");
		filter.setOperator("GTE");
		filter.setValue("A");

		SearchRequest request = new SearchRequest();
		request.setFilters(List.of(filter));

		assertThatThrownBy(() -> employeeEsService.search(request))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessage("unsupported employee search operator: GTE");
	}

	@Test
	void searchRejectsNumericMetricBecauseEmployeeIndexHasNoNumericFields() {
		SearchMetric metric = new SearchMetric();
		metric.setField("position");
		metric.setFunction(SearchMetricFunction.SUM);

		SearchAggregate aggregate = new SearchAggregate();
		aggregate.setMetrics(List.of(metric));

		SearchRequest request = new SearchRequest();
		request.setAggregate(aggregate);

		assertThatThrownBy(() -> employeeEsService.search(request))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessage("employee index has no numeric fields for metric function SUM");
	}

	private JsonNode capturedDsl() throws Exception {
		ArgumentCaptor<String> captor = ArgumentCaptor.forClass(String.class);
		verify(esQueryClient).search(eq("employee"), captor.capture());
		return objectMapper.readTree(captor.getValue());
	}
}
