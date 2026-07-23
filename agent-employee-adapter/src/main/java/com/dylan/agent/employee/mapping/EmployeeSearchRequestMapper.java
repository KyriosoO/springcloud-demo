package com.dylan.agent.employee.mapping;

import java.util.List;

import org.springframework.stereotype.Component;

import com.dylan.agent.employee.api.model.AgentEmployeeFilter;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.api.model.AgentQueryOperator;
import com.dylan.agent.employee.client.EmployeeSearchRequest;
import com.dylan.agent.employee.client.EmployeeSearchRequest.EmployeeSearchFilter;
import com.dylan.agent.employee.client.EmployeeSearchRequest.EmployeeSearchSort;

@Component
public class EmployeeSearchRequestMapper {

	public EmployeeSearchRequest map(AgentEmployeeQueryRequest request) {
		List<EmployeeSearchFilter> filters = request.filters().stream().map(this::mapFilter).toList();
		List<EmployeeSearchSort> sorts = request.sorts().stream()
				.map(sort -> new EmployeeSearchSort(sort.field().jsonName(), sort.direction().name()))
				.toList();
		int from = Math.multiplyExact(request.page().number(), request.page().size());
		return new EmployeeSearchRequest(null, from, request.page().size(), filters, sorts);
	}

	private EmployeeSearchFilter mapFilter(AgentEmployeeFilter filter) {
		if (filter.operator() == AgentQueryOperator.EQ) {
			return new EmployeeSearchFilter(filter.field().jsonName(), "eq", filter.values().getFirst(), List.of());
		}
		return new EmployeeSearchFilter(filter.field().jsonName(), "in", null, filter.values());
	}
}
