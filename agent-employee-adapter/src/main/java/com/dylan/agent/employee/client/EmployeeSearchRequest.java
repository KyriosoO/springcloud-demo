package com.dylan.agent.employee.client;

import java.util.List;

public record EmployeeSearchRequest(
		String keyword,
		Integer from,
		Integer size,
		List<EmployeeSearchFilter> filters,
		List<EmployeeSearchSort> sorts) {

	public EmployeeSearchRequest {
		filters = filters == null ? List.of() : List.copyOf(filters);
		sorts = sorts == null ? List.of() : List.copyOf(sorts);
	}

	public record EmployeeSearchFilter(String field, String operator, String value, List<String> values) {
		public EmployeeSearchFilter {
			values = values == null ? List.of() : List.copyOf(values);
		}
	}

	public record EmployeeSearchSort(String field, String direction) {
	}
}
