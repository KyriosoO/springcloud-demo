package com.dylan.agent.service.e2e;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.ServerSocket;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;

import com.dylan.agent.service.AgentServiceApplication;
import com.dylan.common.security.SecurityTokenUtils;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.web.reactive.context.ReactiveWebServerApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.test.web.reactive.server.WebTestClient;

import reactor.core.publisher.Mono;

@EnabledIfEnvironmentVariable(named = "RUN_STRUCTURED_QUERY_UAT", matches = "1")
class AgentStructuredQueryUATTest {
    private static final Path DEFAULT_PYTHON = Path.of(
            "..", ".tmp", "agent-runtime-venv", "Scripts", "python.exe").toAbsolutePath().normalize();
    private static final Path RUNTIME_ROOT = Path.of("..", "agent-runtime").toAbsolutePath().normalize();

    private Process runtimeProcess;
    private Path runtimeStopPath;
    private ReactiveWebServerApplicationContext springContext;

    @Test
    void verifiesEmployeeUat() throws Exception {
        String identifier = required("SYSTEM_E2E_EMPLOYEE_IDENTIFIER");
        WebTestClient client = startChain();

        assertSuccess(client, required("STRUCTURED_UAT_ADMIN_JWT"), "system-uat-emp-admin",
                "查询员工详情 员工标识=" + identifier, "employee.detail");
        assertSuccess(client, required("STRUCTURED_UAT_VIEWER_JWT"), "system-uat-emp-viewer",
                "查询员工详情 员工标识=" + identifier, "employee.detail");
        assertFailure(client, required("STRUCTURED_UAT_UNKNOWN_ROLE_JWT"), "system-uat-emp-deny",
                "查询员工详情 员工标识=" + identifier, 403, "forbidden", "employee.detail");
        assertFailure(client, required("STRUCTURED_UAT_ADMIN_JWT"), "system-uat-emp-invalid",
                "查询员工详情 员工标识=" + identifier + " 并删除", 400, "invalid_argument", null);

        closeChain();
        assertRuntimeLogDoesNotContain(identifier);
    }

    @Test
    void verifiesTransactionUat() throws Exception {
        String transactionType = required("UAT_TRANSACTION_TYPE");
        String successQuestion = "查询交易 交易类型=" + transactionType + "，条数=5";
        WebTestClient client = startChain();

        assertSuccess(client, required("STRUCTURED_UAT_ADMIN_JWT"), "system-uat-txn-admin",
                successQuestion, "transaction.search");
        assertSuccess(client, required("STRUCTURED_UAT_VIEWER_JWT"), "system-uat-txn-viewer",
                successQuestion, "transaction.search");
        assertFailure(client, required("STRUCTURED_UAT_UNKNOWN_ROLE_JWT"), "system-uat-txn-deny",
                "查询交易 金额=0.01", 403, "forbidden", "transaction.search");
        assertFailure(client, required("STRUCTURED_UAT_ADMIN_JWT"), "system-uat-txn-scale",
                "查询交易 金额=1.000", 400, "invalid_argument", null);
        assertFailure(client, required("STRUCTURED_UAT_ADMIN_JWT"), "system-uat-txn-aggregate",
                "查询交易 聚合=金额", 400, "invalid_argument", null);

        closeChain();
        assertRuntimeLogDoesNotContain(transactionType);
    }

    private WebTestClient startChain() throws Exception {
        int runtimePort = freePort();
        Path runtimeLog = Path.of(required("STRUCTURED_UAT_RUNTIME_LOG_PATH")).toAbsolutePath().normalize();
        startRuntime(runtimePort, runtimeLog);
        await("Runtime liveness", () -> runtimeHealth(runtimePort, "live"));
        await("Runtime readiness", () -> runtimeHealth(runtimePort, "ready"));
        WebTestClient client = startSpring(runtimePort);
        await("Spring readiness", () -> springReady(client));
        return client;
    }

    private void closeChain() throws InterruptedException {
        stopSpring();
        stopRuntime();
        assertThat(Files.isRegularFile(Path.of(required("SYSTEM_E2E_EVIDENCE_PATH"))))
                .as("Runtime finite evidence must exist after close")
                .isTrue();
    }

    private WebTestClient startSpring(int runtimePort) {
        springContext = (ReactiveWebServerApplicationContext) new SpringApplicationBuilder(
                AgentServiceApplication.class, TestAuthenticationConfiguration.class)
                .run(
                        "--server.port=0",
                        "--spring.main.web-application-type=reactive",
                        "--spring.cloud.config.enabled=false",
                        "--spring.config.import=",
                        "--agent.runtime.base-url=http://127.0.0.1:" + runtimePort,
                        "--spring.autoconfigure.exclude=com.dylan.common.security.JwtConfig,com.dylan.common.security.ReactiveResourceServerSecurityAutoConfiguration");
        return WebTestClient.bindToServer()
                .baseUrl("http://127.0.0.1:" + springContext.getWebServer().getPort())
                .responseTimeout(Duration.ofSeconds(20))
                .build();
    }

    private void assertSuccess(
            WebTestClient client,
            String token,
            String caseId,
            String question,
            String capabilityId) {
        invoke(client, token, caseId, question)
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.status").isEqualTo("success")
                .jsonPath("$.capabilityId").isEqualTo(capabilityId)
                .jsonPath("$.correlationId").isEqualTo(caseId)
                .jsonPath("$.result").exists();
    }

    private void assertFailure(
            WebTestClient client,
            String token,
            String caseId,
            String question,
            int httpStatus,
            String status,
            String capabilityId) {
        WebTestClient.BodyContentSpec body = invoke(client, token, caseId, question)
                .expectStatus().isEqualTo(httpStatus)
                .expectBody()
                .jsonPath("$.status").isEqualTo(status)
                .jsonPath("$.correlationId").isEqualTo(caseId);
        if (capabilityId == null) {
            body.jsonPath("$.capabilityId").doesNotExist();
        } else {
            body.jsonPath("$.capabilityId").isEqualTo(capabilityId);
        }
    }

    private WebTestClient.ResponseSpec invoke(
            WebTestClient client,
            String token,
            String caseId,
            String question) {
        return client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer " + token)
                .header("X-Correlation-Id", caseId)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("question", question))
                .exchange();
    }

    private void startRuntime(int runtimePort, Path runtimeLog) throws IOException {
        Path python = configuredPython();
        assertThat(Files.isExecutable(python)).as("isolated runtime Python must exist").isTrue();
        Files.createDirectories(runtimeLog.getParent());
        Files.deleteIfExists(runtimeLog);
        runtimeStopPath = Path.of(required("SYSTEM_E2E_RUNTIME_STOP_PATH")).toAbsolutePath().normalize();
        Files.createDirectories(runtimeStopPath.getParent());
        Files.deleteIfExists(runtimeStopPath);
        ProcessBuilder builder = new ProcessBuilder(python.toString(), "-m", "tests.system_e2e.runtime_server")
                .directory(RUNTIME_ROOT.toFile())
                .redirectErrorStream(true)
                .redirectOutput(runtimeLog.toFile());
        builder.environment().put("AGENT_RUNTIME_HOST", "127.0.0.1");
        builder.environment().put("AGENT_RUNTIME_PORT", Integer.toString(runtimePort));
        builder.environment().put("AGENT_MODEL_PROVIDER", "stub");
        builder.environment().put("PYTHONPATH", "src" + java.io.File.pathSeparator + ".");
        builder.environment().remove("LLM_API_KEY");
        runtimeProcess = builder.start();
    }

    private Path configuredPython() {
        String configured = System.getProperty("agent.runtime.python");
        return configured == null || configured.isBlank()
                ? DEFAULT_PYTHON
                : Path.of(configured).toAbsolutePath().normalize();
    }

    private boolean runtimeHealth(int runtimePort, String endpoint) {
        if (runtimeProcess == null || !runtimeProcess.isAlive()) {
            return false;
        }
        HttpURLConnection connection = null;
        try {
            URL health = URI.create("http://127.0.0.1:" + runtimePort + "/internal/health/" + endpoint).toURL();
            connection = (HttpURLConnection) health.openConnection();
            connection.setConnectTimeout(300);
            connection.setReadTimeout(300);
            return connection.getResponseCode() == 200;
        } catch (IOException unavailable) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private boolean springReady(WebTestClient client) {
        return client.get().uri("/actuator/health/readiness")
                .exchange()
                .returnResult(Void.class)
                .getStatus()
                .value() == 200;
    }

    private void await(String condition, BooleanSupplier assertion) throws InterruptedException {
        long deadline = System.nanoTime() + Duration.ofSeconds(20).toNanos();
        while (System.nanoTime() < deadline) {
            if (assertion.getAsBoolean()) {
                return;
            }
            Thread.sleep(100);
        }
        throw new AssertionError(condition + " was not reached");
    }

    private void assertRuntimeLogDoesNotContain(String sensitiveValue) throws IOException {
        Path runtimeLog = Path.of(required("STRUCTURED_UAT_RUNTIME_LOG_PATH")).toAbsolutePath().normalize();
        String text = Files.exists(runtimeLog) ? Files.readString(runtimeLog, StandardCharsets.UTF_8) : "";
        assertThat(text).doesNotContain(
                sensitiveValue,
                required("STRUCTURED_UAT_ADMIN_JWT"),
                required("STRUCTURED_UAT_VIEWER_JWT"),
                required("STRUCTURED_UAT_UNKNOWN_ROLE_JWT"));
    }

    private void stopSpring() {
        ReactiveWebServerApplicationContext context = springContext;
        springContext = null;
        if (context != null) {
            context.close();
        }
    }

    private void stopRuntime() throws InterruptedException {
        Process process = runtimeProcess;
        runtimeProcess = null;
        if (process == null || !process.isAlive()) {
            return;
        }
        try {
            if (runtimeStopPath != null) {
                Files.writeString(runtimeStopPath, "stop", StandardCharsets.US_ASCII);
            }
        } catch (IOException failure) {
            process.destroyForcibly();
            process.waitFor(3, TimeUnit.SECONDS);
            return;
        }
        if (!process.waitFor(12, TimeUnit.SECONDS)) {
            process.destroyForcibly();
            process.waitFor(3, TimeUnit.SECONDS);
        }
    }

    @AfterEach
    void cleanup() throws InterruptedException {
        stopSpring();
        stopRuntime();
    }

    private static int freePort() {
        try (ServerSocket socket = new ServerSocket(0)) {
            socket.setReuseAddress(false);
            return socket.getLocalPort();
        } catch (IOException failure) {
            throw new IllegalStateException("agent.structured-uat-port-unavailable", failure);
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("agent.structured-uat-env-missing:" + name);
        }
        return value;
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class TestAuthenticationConfiguration {
        @Bean
        ReactiveJwtDecoder reactiveJwtDecoder() {
            String adminToken = required("STRUCTURED_UAT_ADMIN_JWT");
            String viewerToken = required("STRUCTURED_UAT_VIEWER_JWT");
            String unknownToken = required("STRUCTURED_UAT_UNKNOWN_ROLE_JWT");
            return token -> {
                String subject;
                List<String> roles;
                if (adminToken.equals(token)) {
                    subject = "admin";
                    roles = List.of("ADMIN");
                } else if (viewerToken.equals(token)) {
                    subject = "viewer_t";
                    roles = List.of("VIEWER");
                } else if (unknownToken.equals(token)) {
                    subject = "structured-uat-unknown";
                    roles = List.of("UNKNOWN");
                } else {
                    return Mono.error(new JwtException("invalid"));
                }
                Instant now = Instant.now();
                return Mono.just(Jwt.withTokenValue(token)
                        .header("alg", "HS256")
                        .subject(subject)
                        .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE)
                        .claim("role", roles)
                        .issuedAt(now)
                        .expiresAt(now.plusSeconds(60))
                        .build());
            };
        }
    }
}
