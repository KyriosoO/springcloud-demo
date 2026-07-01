package com.dylan.agent.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicReference;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import com.dylan.agent.api.request.PlanGenerateRequest;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.exception.AgentRuntimeException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

@DisplayName("AgentRuntimeClient")
class AgentRuntimeClientTest {

    private HttpServer server;
    private AtomicReference<ResponseSpec> response;
    private AtomicReference<HttpExchange> exchange;
    private AgentProperties properties;

    @BeforeEach
    void setUp() throws IOException {
        response = new AtomicReference<>(new ResponseSpec(200, validResponse()));
        exchange = new AtomicReference<>();
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/runtime/v1/plans/generate", httpExchange -> {
            exchange.set(httpExchange);
            httpExchange.getRequestBody().readAllBytes();
            ResponseSpec spec = response.get();
            if (spec.delayMillis() > 0) {
                try {
                    Thread.sleep(spec.delayMillis());
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }
            byte[] bytes = spec.body().getBytes(java.nio.charset.StandardCharsets.UTF_8);
            httpExchange.getResponseHeaders().set("Content-Type", "application/json");
            httpExchange.sendResponseHeaders(spec.status(), bytes.length);
            httpExchange.getResponseBody().write(bytes);
            httpExchange.close();
        });
        server.start();

        properties = new AgentProperties();
        AgentProperties.RuntimeProperties runtime = new AgentProperties.RuntimeProperties();
        runtime.setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
        runtime.setSharedKey("test-runtime-shared-key");
        runtime.setConnectTimeout(Duration.ofSeconds(1));
        runtime.setReadTimeout(Duration.ofSeconds(1));
        runtime.setMaxResponseBytes(1024);
        properties.setRuntime(runtime);
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    @Test
    @DisplayName("发送 shared key 且不发送用户凭证")
    void shouldSendOnlyRuntimeCredential() {
        client().generate(request());

        assertThat(exchange.get().getRequestHeaders().getFirst("X-Agent-Runtime-Key"))
                .isEqualTo("test-runtime-shared-key");
        assertThat(exchange.get().getRequestHeaders().getFirst("Authorization")).isNull();
        assertThat(exchange.get().getRequestHeaders().getFirst("Cookie")).isNull();
    }

    @Test
    @DisplayName("400 映射为 Runtime 契约错误")
    void shouldMap400() {
        response.set(new ResponseSpec(400,
                "{\"code\":\"RUNTIME_INVALID_REQUEST\",\"message\":\"bad\",\"requestId\":\"turn-001\"}"));
        assertThatThrownBy(() -> client().generate(request()))
                .isInstanceOf(AgentRuntimeException.class);
    }

    @Test
    @DisplayName("422 映射为 Plan 校验错误")
    void shouldMap422() {
        response.set(new ResponseSpec(422,
                "{\"code\":\"RUNTIME_PLAN_INVALID\",\"message\":\"bad\",\"requestId\":\"turn-001\"}"));
        assertThatThrownBy(() -> client().generate(request()))
                .isInstanceOf(AgentPlanValidationException.class);
    }

    @Test
    @DisplayName("错误响应 requestId 不匹配时拒绝")
    void shouldRejectMismatchedErrorRequestId() {
        response.set(new ResponseSpec(422,
                "{\"code\":\"RUNTIME_PLAN_INVALID\",\"message\":\"bad\",\"requestId\":\"other-turn\"}"));
        assertThatThrownBy(() -> client().generate(request()))
                .isInstanceOf(AgentRuntimeException.class)
                .hasMessageContaining("requestId");
    }

    @Test
    @DisplayName("未知 Runtime 错误码不可信")
    void shouldRejectUnknownRuntimeErrorCode() {
        response.set(new ResponseSpec(422,
                "{\"code\":\"UNKNOWN\",\"message\":\"bad\",\"requestId\":\"turn-001\"}"));
        assertThatThrownBy(() -> client().generate(request()))
                .isInstanceOf(AgentRuntimeException.class)
                .hasMessageContaining("未知错误");
    }

    @Test
    @DisplayName("非法 Runtime 错误响应拒绝")
    void shouldRejectMalformedRuntimeErrorResponse() {
        response.set(new ResponseSpec(502, "not-json"));
        assertThatThrownBy(() -> client().generate(request()))
                .isInstanceOf(AgentRuntimeException.class)
                .hasMessageContaining("错误响应");
    }

    @Test
    @DisplayName("非法 JSON 映射为 Runtime 错误")
    void shouldRejectInvalidJson() {
        response.set(new ResponseSpec(200, "not-json"));
        assertThatThrownBy(() -> client().generate(request()))
                .isInstanceOf(AgentRuntimeException.class);
    }

    @Test
    @DisplayName("未知枚举映射为 Plan 校验错误")
    void shouldRejectUnknownEnum() {
        response.set(new ResponseSpec(200, validResponse().replace("\"QUERY\"", "\"UPDATE\"")));
        assertThatThrownBy(() -> client().generate(request()))
                .isInstanceOf(AgentPlanValidationException.class);
    }

    @Test
    @DisplayName("响应体超过上限时拒绝")
    void shouldRejectOversizedBody() {
        properties.getRuntime().setMaxResponseBytes(16);
        assertThatThrownBy(() -> client().generate(request()))
                .isInstanceOf(AgentRuntimeException.class)
                .hasMessageContaining("大小上限");
    }

    @Test
    @DisplayName("读取超时映射为 Runtime 错误")
    void shouldMapTimeout() {
        response.set(new ResponseSpec(200, validResponse(), 200));
        assertThatThrownBy(() -> client(Duration.ofMillis(50)).generate(request()))
                .isInstanceOf(AgentRuntimeException.class);
    }

    private AgentRuntimeClient client() {
        return client(Duration.ofSeconds(1));
    }

    private AgentRuntimeClient client(Duration readTimeout) {
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory();
        requestFactory.setReadTimeout(readTimeout);
        RestClient restClient = RestClient.builder()
                .baseUrl(properties.getRuntime().getBaseUrl())
                .requestFactory(requestFactory)
                .build();
        ObjectMapper mapper = new ObjectMapper()
                .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true);
        return new AgentRuntimeClient(restClient, mapper, properties);
    }

    private PlanGenerateRequest request() {
        PlanGenerateRequest request = new PlanGenerateRequest();
        request.setRequestId("turn-001");
        request.setMessage("岗位是 HRM");
        request.setDomainSchemas(java.util.List.of());
        request.setCapabilities(java.util.List.of());
        return request;
    }

    private String validResponse() {
        return """
                {"requestId":"turn-001","plan":{"planVersion":"1.0","intent":"QUERY",
                "domain":"employee","query":{"filters":[{"field":"position","operator":"EQ",
                "value":"HRM"}],"selectFields":["chineseName"],"page":1,"size":20},"clarify":null}}
                """;
    }

    private record ResponseSpec(int status, String body, long delayMillis) {
        private ResponseSpec(int status, String body) {
            this(status, body, 0);
        }
    }
}
