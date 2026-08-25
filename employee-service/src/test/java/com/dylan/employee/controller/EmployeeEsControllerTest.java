package com.dylan.employee.controller;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import com.dylan.employee.security.CapabilityAccessGuard;
import com.dylan.employee.service.EmployeeEsService;
import com.dylan.esquery.api.model.SearchRequest;
import com.dylan.esquery.api.model.SemanticSearchRequest;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.server.ResponseStatusException;

class EmployeeEsControllerTest {

    @Test
    void shouldProtectUnifiedSearchWithEmployeeReadAuthorization() throws Exception {
        EmployeeEsService employeeEsService = mock(EmployeeEsService.class);
        CapabilityAccessGuard accessGuard = mock(CapabilityAccessGuard.class);
        Authentication authentication = mock(Authentication.class);
        SearchRequest request = new SearchRequest();
        EmployeeEsController controller = new EmployeeEsController(employeeEsService, accessGuard);

        controller.search(authentication, request);

        verify(accessGuard).requireEmployeeRead(authentication);
        verify(employeeEsService).search(request);
    }

    @Test
    void shouldProtectVectorSearchWithEmployeeReadAuthorization() {
        EmployeeEsService employeeEsService = mock(EmployeeEsService.class);
        CapabilityAccessGuard accessGuard = mock(CapabilityAccessGuard.class);
        Authentication authentication = mock(Authentication.class);
        SemanticSearchRequest request = new SemanticSearchRequest();
        EmployeeEsController controller = new EmployeeEsController(employeeEsService, accessGuard);

        controller.vectorSearch(authentication, request);

        verify(accessGuard).requireEmployeeRead(authentication);
        verify(employeeEsService).vectorSearch(request);
    }

    @Test
    void shouldRejectUnifiedSearchBeforeExecutingBusinessQuery() {
        EmployeeEsService employeeEsService = mock(EmployeeEsService.class);
        CapabilityAccessGuard accessGuard = mock(CapabilityAccessGuard.class);
        Authentication authentication = mock(Authentication.class);
        doThrow(new ResponseStatusException(HttpStatus.FORBIDDEN))
                .when(accessGuard).requireEmployeeRead(authentication);
        EmployeeEsController controller = new EmployeeEsController(employeeEsService, accessGuard);

        assertThrows(ResponseStatusException.class,
                () -> controller.search(authentication, new SearchRequest()));

        verifyNoInteractions(employeeEsService);
    }

    @Test
    void shouldRejectVectorSearchBeforeExecutingBusinessQuery() {
        EmployeeEsService employeeEsService = mock(EmployeeEsService.class);
        CapabilityAccessGuard accessGuard = mock(CapabilityAccessGuard.class);
        Authentication authentication = mock(Authentication.class);
        doThrow(new ResponseStatusException(HttpStatus.FORBIDDEN))
                .when(accessGuard).requireEmployeeRead(authentication);
        EmployeeEsController controller = new EmployeeEsController(employeeEsService, accessGuard);

        assertThrows(ResponseStatusException.class,
                () -> controller.vectorSearch(authentication, new SemanticSearchRequest()));

        verifyNoInteractions(employeeEsService);
    }
}
