package com.dylan.agent.employee.client;

import java.time.Duration;

public interface EmployeeSearchClient {

	String search(EmployeeSearchRequest request, Duration timeout);
}
