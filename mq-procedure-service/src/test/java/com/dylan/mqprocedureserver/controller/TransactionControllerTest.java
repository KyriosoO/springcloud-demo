package com.dylan.mqprocedureserver.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.reactive.server.WebTestClient;

import com.dylan.mqprocedureserver.service.TransactionOperKafkaProducer;
import com.dylan.mqprocedureserver.service.TransactionOperMQProducer;
import com.dylan.mqprocedureserver.service.TransactionService;
import com.dylan.transaction.api.query.TransactionSearchResponse;

class TransactionControllerTest {

    private TransactionService service;
    private WebTestClient client;

    @BeforeEach
    void setUp() {
        service = mock(TransactionService.class);
        TransactionController controller = new TransactionController(
                mock(TransactionOperKafkaProducer.class),
                mock(TransactionOperMQProducer.class),
                service);
        client = WebTestClient.bindToController(controller)
                .controllerAdvice(new TransactionExceptionHandler())
                .build();
    }

    @Test
    void shouldExposeSearchContract() throws Exception {
        TransactionSearchResponse response = new TransactionSearchResponse();
        response.setRows(List.of());
        response.setTotal(100);
        response.setTotalExact(false);
        response.setPage(2);
        response.setSize(20);
        when(service.search(any())).thenReturn(response);

        client.post().uri("/txn/search")
                .bodyValue("""
                        {
                          "condition":{"transTypeContains":"PAY"},
                          "page":2,
                          "size":20
                        }
                        """)
                .header("Content-Type", "application/json")
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.rows").isArray()
                .jsonPath("$.total").isEqualTo(100)
                .jsonPath("$.totalExact").isEqualTo(false)
                .jsonPath("$.page").isEqualTo(2)
                .jsonPath("$.size").isEqualTo(20);
    }

    @Test
    void shouldMapInvalidSearchToBadRequest() throws Exception {
        when(service.search(any())).thenThrow(new IllegalArgumentException("至少需要一个查询条件。"));

        client.post().uri("/txn/search")
                .bodyValue("""
                        {"condition":{},"page":1,"size":20}
                        """)
                .header("Content-Type", "application/json")
                .exchange()
                .expectStatus().isBadRequest()
                .expectBody()
                .jsonPath("$.code").isEqualTo("INVALID_TRANSACTION_SEARCH_REQUEST")
                .jsonPath("$.message").isEqualTo("至少需要一个查询条件。");
    }
}
