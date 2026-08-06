package com.dylan.employee.live;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.mockingDetails;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

import com.dylan.employee.event.WorkflowInboxProcessor;
import com.dylan.employee.mapper.EmployeeMapper;
import com.dylan.employee.service.EmployeeService;
import com.fasterxml.jackson.databind.ObjectMapper;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_GATEWAY_LOG_LIVE", matches = "1")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "spring.cloud.config.enabled=false",
        "spring.config.import=",
        "spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/",
        "spring.profiles.active=datasource,emp,ai-provider",
        "eureka.client.enabled=false",
        "spring.kafka.listener.auto-startup=false",
        "employee.workflow.inbox-retry-delay-ms=3600000",
        "common.security.secrets.source-order[0]=environment",
        "common.security.secrets.allow-config-values=false",
        "common.security.secrets.fail-fast=true",
        "common.security.secrets.jwt.active-key-id=ACTIVE",
        "common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
        "common.security.secrets.jwt.keys.ACTIVE.value="
})
class EmployeeGatewayLogSafetyLiveIntegrationTest {
    private static final Duration GATEWAY_START_TIMEOUT = Duration.ofSeconds(60);
    private static final Duration GATEWAY_STOP_TIMEOUT = Duration.ofSeconds(5);

    @LocalServerPort
    private int employeePort;
    @Autowired
    private ObjectMapper objectMapper;
    @MockitoSpyBean
    private EmployeeService employeeService;
    @MockitoBean
    private EmployeeMapper employeeMapper;
    @MockitoBean
    private WorkflowInboxProcessor workflowInboxProcessor;

    @Test
    void gatewayForwardsSingleSyntheticRequestWithoutPersistingSensitiveValues() throws Exception {
        Path gatewayJar = Path.of(required("EMPLOYEE_GATEWAY_LIVE_GATEWAY_JAR"));
        Path gatewayOut = Path.of(required("EMPLOYEE_GATEWAY_LIVE_GATEWAY_OUT_PATH"));
        Path gatewayErr = Path.of(required("EMPLOYEE_GATEWAY_LIVE_GATEWAY_ERR_PATH"));
        Path javaMetrics = Path.of(required("EMPLOYEE_GATEWAY_LIVE_JAVA_METRICS_PATH"));
        int gatewayPort = requiredPort("EMPLOYEE_GATEWAY_LIVE_GATEWAY_PORT");
        String token = required("EMPLOYEE_GATEWAY_LIVE_JWT");
        String sentinel = required("EMPLOYEE_GATEWAY_LIVE_SENTINEL");
        String correlationId = required("EMPLOYEE_GATEWAY_LIVE_CORRELATION_ID");

        assertThat(gatewayJar).as("employee.gateway_live_jar_missing").isRegularFile();
        Process gateway = startGateway(gatewayJar, gatewayOut, gatewayErr, gatewayPort);
        try {
            waitForListener(gateway, gatewayPort);
            clearInvocations(employeeService, employeeMapper);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + gatewayPort + "/employees/" + sentinel))
                    .timeout(Duration.ofSeconds(10))
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                    .header("X-Correlation-Id", correlationId)
                    .GET()
                    .build();
            HttpResponse<Void> response = HttpClient.newBuilder()
                    .followRedirects(HttpClient.Redirect.NEVER)
                    .connectTimeout(Duration.ofSeconds(5))
                    .build()
                    .send(request, HttpResponse.BodyHandlers.discarding());

            if (response.statusCode() != 400) {
                throw new IllegalStateException(statusFailure(response.statusCode()));
            }
            long serviceDetailCalls = invocationCount(employeeService, "detail");
            long mapperDetailCalls = invocationCount(employeeMapper, "selectByIdCardNo");
            long otherServiceCalls = mockingDetails(employeeService).getInvocations().stream()
                    .filter(invocation -> invocation.getMethod().getDeclaringClass().equals(EmployeeService.class))
                    .filter(invocation -> !invocation.getMethod().getName().equals("detail"))
                    .count();
            assertThat(serviceDetailCalls).as("employee.gateway_live_service_count_invalid").isEqualTo(1);
            assertThat(mapperDetailCalls).as("employee.gateway_live_mapper_count_invalid").isEqualTo(1);
            assertThat(otherServiceCalls).as("employee.gateway_live_scope_invalid").isZero();

            Files.writeString(javaMetrics, objectMapper.writeValueAsString(Map.of(
                    "schemaVersion", 1,
                    "gateway", 1,
                    "servlet", 1,
                    "serviceDetail", serviceDetailCalls,
                    "mapperSelectByIdCardNo", mapperDetailCalls,
                    "otherServiceMethods", otherServiceCalls,
                    "responseStatus", response.statusCode())), StandardCharsets.UTF_8);
        } finally {
            stopGateway(gateway);
        }
    }

    private Process startGateway(Path jar, Path stdout, Path stderr, int gatewayPort) throws Exception {
        ProcessBuilder builder = new ProcessBuilder(
                "java", "-jar", jar.toString(),
                "--server.port=" + gatewayPort,
                "--spring.main.banner-mode=off",
                "--spring.cloud.config.enabled=false",
                "--spring.config.import=",
                "--eureka.client.enabled=false",
                "--spring.cloud.gateway.server.webflux.discovery.locator.enabled=false",
                "--spring.cloud.gateway.discovery.locator.enabled=false",
                "--spring.cloud.gateway.server.webflux.routes[0].id=employee-live-test",
                "--spring.cloud.gateway.server.webflux.routes[0].uri=http://127.0.0.1:" + employeePort,
                "--spring.cloud.gateway.server.webflux.routes[0].predicates[0]=Path=/employees/**",
                "--management.endpoints.enabled-by-default=false",
                "--common.security.secrets.source-order[0]=environment",
                "--common.security.secrets.allow-config-values=false",
                "--common.security.secrets.fail-fast=true",
                "--common.security.secrets.jwt.active-key-id=ACTIVE",
                "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
                "--common.security.secrets.jwt.keys.ACTIVE.value=");
        builder.redirectOutput(stdout.toFile());
        builder.redirectError(stderr.toFile());
        Map<String, String> environment = builder.environment();
        environment.keySet().removeIf(name -> name.startsWith("EMPLOYEE_GATEWAY_LIVE_"));
        environment.remove("RUN_EMPLOYEE_GATEWAY_LOG_LIVE");
        return builder.start();
    }

    private static void waitForListener(Process process, int port) throws Exception {
        long deadline = System.nanoTime() + GATEWAY_START_TIMEOUT.toNanos();
        while (System.nanoTime() < deadline) {
            if (!process.isAlive()) {
                throw new IllegalStateException("employee.gateway_live_process_exited");
            }
            try (Socket socket = new Socket()) {
                socket.connect(new InetSocketAddress("127.0.0.1", port), 200);
                return;
            } catch (java.io.IOException ignored) {
                Thread.sleep(200);
            }
        }
        throw new IllegalStateException("employee.gateway_live_readiness_timeout");
    }

    private static void stopGateway(Process process) throws InterruptedException {
        if (!process.isAlive()) {
            return;
        }
        process.destroy();
        if (!process.waitFor(GATEWAY_STOP_TIMEOUT.toMillis(), TimeUnit.MILLISECONDS)) {
            process.destroyForcibly();
            process.waitFor(GATEWAY_STOP_TIMEOUT.toMillis(), TimeUnit.MILLISECONDS);
        }
    }

    private static long invocationCount(Object mock, String methodName) {
        return mockingDetails(mock).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getName().equals(methodName))
                .count();
    }

    private static int requiredPort(String name) {
        try {
            int port = Integer.parseInt(required(name));
            if (port < 1024 || port > 65535) {
                throw new NumberFormatException();
            }
            return port;
        } catch (NumberFormatException ex) {
            throw new IllegalStateException("employee.gateway_live_port_invalid");
        }
    }

    private static String statusFailure(int status) {
        if (status == 301 || status == 302 || status == 307 || status == 308 || status == 401 || status == 403) {
            return "employee.gateway_live_auth_failed";
        }
        if (status == 404) {
            return "employee.gateway_live_route_missing";
        }
        if (status == 500 || status == 502 || status == 503 || status == 504) {
            return "employee.gateway_live_forwarding_failed";
        }
        return "employee.gateway_live_status_invalid";
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.gateway_live_env_missing:" + name);
        }
        return value;
    }
}
