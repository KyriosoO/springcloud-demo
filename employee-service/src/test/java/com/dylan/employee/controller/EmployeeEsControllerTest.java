package com.dylan.employee.controller;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import com.dylan.employee.security.CapabilityAccessGuard;
import com.dylan.employee.service.EmployeeEsService;
import com.dylan.esquery.api.model.SearchRequest;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.Authentication;

class EmployeeEsControllerTest {

    @Test
    void shouldProtectUnifiedSearchWithEmployeeQueryScope() throws Exception {
        EmployeeEsService employeeEsService = mock(EmployeeEsService.class);
        CapabilityAccessGuard accessGuard = mock(CapabilityAccessGuard.class);
        Authentication authentication = mock(Authentication.class);
        SearchRequest request = new SearchRequest();
        EmployeeEsController controller = new EmployeeEsController(employeeEsService, accessGuard);

        controller.search(authentication, request);

        verify(accessGuard).requireUserOrAgentScope(authentication, "agent.employee.query");
        verify(employeeEsService).search(request);
    }
}
