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
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;

import com.dylan.agent.service.AgentServiceApplication;
import com.dylan.common.security.SecurityTokenUtils;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
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

class AgentKnowledgeNonLiveE2ETest {
    private static final String ADMIN_TOKEN = "synthetic-knowledge-admin";
    private static final String VIEWER_TOKEN = "synthetic-knowledge-viewer";
    private static final String DENIED_TOKEN = "synthetic-knowledge-denied";
    private static final String SERVICE_TOKEN = "synthetic-knowledge-service";
    private static final Path DEFAULT_PYTHON = Path.of(
            "..", ".tmp", "agent-runtime-venv", "Scripts", "python.exe").toAbsolutePath().normalize();
    private static final Path RUNTIME_ROOT = Path.of("..", "agent-runtime").toAbsolutePath().normalize();

    private final ObjectMapper objectMapper = new ObjectMapper();
    private Process runtimeProcess;
    private Path runtimeStopPath;
    private Path runtimeLogPath;
    private Path evidencePath;
    private Path runRoot;
    private ReactiveWebServerApplicationContext springContext;

    @Test
    void verifiesSpringToCurrentKnowledgeCompositionWithFiniteFailureSemantics() throws Exception {
        int runtimePort = freePort();
        runRoot = Files.createTempDirectory("knowledge-nonlive-");
        runtimeStopPath = runRoot.resolve("runtime.stop");
        runtimeLogPath = runRoot.resolve("runtime.log");
        evidencePath = runRoot.resolve("evidence.json");
        startRuntime(runtimePort);
        await("Runtime liveness", () -> runtimeHealth(runtimePort, "live"));
        await("Runtime readiness", () -> runtimeHealth(runtimePort, "ready"));
        WebTestClient client = startSpring(runtimePort);
        await("Spring readiness", () -> springReady(client));

        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-policy-admin", "现行增值税政策有哪些",
                200, "success", "knowledge.query", null);
        assertOutcome(client, VIEWER_TOKEN, "k-nonlive-law-viewer", "税收法律第一条规定什么",
                200, "success", "knowledge.query", null);
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-multi-domain", "税务政策和税收法律有哪些规定",
                200, "success", "knowledge.query", null);
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-rewrite-fallback", "税务政策改写失败仍如何处理",
                200, "success", "knowledge.query", null);
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-rewrite-invalid", "税务政策改写非法仍如何处理",
                200, "success", "knowledge.query", null);
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-no-result", "不存在资料的税务政策是什么",
                200, "no_result", "knowledge.query", null);
        assertOutcome(client, DENIED_TOKEN, "k-nonlive-read-denied", "现行税务政策是什么",
                403, "forbidden", "knowledge.query", "knowledge.domain_forbidden");
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-partial-path", "税务政策单路失败如何处理",
                200, "success", "knowledge.query", null);
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-all-paths-fail", "税务政策全部检索失败",
                502, "downstream_failure", "knowledge.query", "knowledge.retrieval_failure");
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-policy-missing", "税务政策未分类策略",
                403, "model_egress_denied", "knowledge.query", "knowledge.evidence_egress_denied");
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-invalid-ref", "税务政策非法引用",
                502, "downstream_failure", "knowledge.query", "knowledge.summary_failure");
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-duplicate-ref", "税务政策重复引用",
                502, "downstream_failure", "knowledge.query", "knowledge.summary_failure");
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-summary-failure", "税务政策摘要失败",
                502, "downstream_failure", "knowledge.query", "knowledge.summary_failure");
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-sensitive", "税务政策 password=synthetic-secret",
                403, "model_egress_denied", null, "model.input_denied");
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-second-action", "税务政策 第二动作",
                502, "downstream_failure", null, "model.invalid_output");
        assertOutcome(client, ADMIN_TOKEN, "k-nonlive-unsupported", "不支持能力的税务咨询",
                422, "unsupported", null, "core.no_supported_capability_candidate");
        assertIngressRejected(client, null);
        assertIngressRejected(client, "malformed-token");
        assertIngressRejected(client, SERVICE_TOKEN);

        stopSpring();
        stopRuntime();
        JsonNode evidence = objectMapper.readTree(evidencePath.toFile());
        assertThat(evidence.path("status").asText()).isEqualTo("passed");
        assertThat(evidence.path("cases").size()).isEqualTo(16);
        assertThat(evidence.path("totals").path("businessModel").asInt()).isZero();
        assertThat(evidence.path("totals").path("externalModelOutbound").asInt()).isZero();
        assertThat(evidence.path("cleanup").path("runtimeClosed").asBoolean()).isTrue();
        assertThat(evidence.path("cleanup").path("knowledgeClientsClosed").asBoolean()).isTrue();
        JsonNode sensitive = findCase(evidence, "k-nonlive-sensitive");
        sensitive.path("calls").elements().forEachRemaining(
                node -> assertThat(node.asInt()).isZero());

        String finiteEvidence = Files.readString(evidencePath, StandardCharsets.UTF_8);
        String runtimeLog = Files.exists(runtimeLogPath)
                ? Files.readString(runtimeLogPath, StandardCharsets.UTF_8)
                : "";
        assertThat(finiteEvidence).doesNotContain(
                "synthetic-secret", ADMIN_TOKEN, VIEWER_TOKEN, DENIED_TOKEN, SERVICE_TOKEN);
        assertThat(runtimeLog).doesNotContain(
                "synthetic-secret", ADMIN_TOKEN, VIEWER_TOKEN, DENIED_TOKEN, SERVICE_TOKEN);
    }

    private JsonNode findCase(JsonNode evidence, String caseId) {
        for (JsonNode item : evidence.path("cases")) {
            if (caseId.equals(item.path("caseId").asText())) {
                return item;
            }
        }
        throw new AssertionError("Missing evidence case " + caseId);
    }

    private void assertIngressRejected(WebTestClient client, String token) {
        WebTestClient.RequestBodySpec request = client.post().uri("/api/v1/agent/queries")
                .header("X-Correlation-Id", "k-nonlive-ingress-rejected")
                .contentType(MediaType.APPLICATION_JSON);
        if (token != null) {
            request.header("Authorization", "Bearer " + token);
        }
        request.bodyValue(Map.of("question", "现行增值税政策有哪些"))
                .exchange()
                .expectStatus().isUnauthorized();
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
                .responseTimeout(Duration.ofSeconds(15))
                .build();
    }

    private void assertOutcome(
            WebTestClient client,
            String token,
            String caseId,
            String question,
            int httpStatus,
            String status,
            String capabilityId,
            String failureCode) {
        WebTestClient.BodyContentSpec body = client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer " + token)
                .header("X-Correlation-Id", caseId)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("question", question))
                .exchange()
                .expectStatus().isEqualTo(httpStatus)
                .expectBody()
                .jsonPath("$.status").isEqualTo(status)
                .jsonPath("$.correlationId").isEqualTo(caseId);
        if (capabilityId == null) {
            body.jsonPath("$.capabilityId").doesNotExist();
        } else {
            body.jsonPath("$.capabilityId").isEqualTo(capabilityId);
        }
        if (failureCode == null) {
            body.jsonPath("$.error").doesNotExist();
        } else {
            body.jsonPath("$.error.code").isEqualTo(failureCode);
        }
    }

    private void startRuntime(int runtimePort) throws IOException {
        Path python = configuredPython();
        assertThat(Files.isExecutable(python)).isTrue();
        ProcessBuilder builder = new ProcessBuilder(
                python.toString(), "-m", "tests.system_e2e.knowledge_runtime_server")
                .directory(RUNTIME_ROOT.toFile())
                .redirectErrorStream(true)
                .redirectOutput(runtimeLogPath.toFile());
        builder.environment().put("AGENT_RUNTIME_HOST", "127.0.0.1");
        builder.environment().put("AGENT_RUNTIME_PORT", Integer.toString(runtimePort));
        builder.environment().put("AGENT_MODEL_PROVIDER", "stub");
        builder.environment().put("PYTHONPATH", "src" + java.io.File.pathSeparator + ".");
        builder.environment().put("KNOWLEDGE_NONLIVE_EVIDENCE_PATH", evidencePath.toString());
        builder.environment().put("KNOWLEDGE_NONLIVE_STOP_PATH", runtimeStopPath.toString());
        builder.environment().put("KNOWLEDGE_NONLIVE_ADMIN_TOKEN", ADMIN_TOKEN);
        builder.environment().put("KNOWLEDGE_NONLIVE_VIEWER_TOKEN", VIEWER_TOKEN);
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
            URL health = URI.create(
                    "http://127.0.0.1:" + runtimePort + "/internal/health/" + endpoint).toURL();
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
            Files.writeString(runtimeStopPath, "stop", StandardCharsets.US_ASCII);
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
    void cleanup() throws Exception {
        stopSpring();
        stopRuntime();
        if (runRoot != null && Files.exists(runRoot)) {
            try (var paths = Files.walk(runRoot)) {
                for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) {
                    Files.deleteIfExists(path);
                }
            }
        }
    }

    private static int freePort() {
        try (ServerSocket socket = new ServerSocket(0)) {
            socket.setReuseAddress(false);
            return socket.getLocalPort();
        } catch (IOException failure) {
            throw new IllegalStateException("agent.knowledge-nonlive-port-unavailable", failure);
        }
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class TestAuthenticationConfiguration {
        @Bean
        ReactiveJwtDecoder reactiveJwtDecoder() {
            return token -> {
                if (!List.of(ADMIN_TOKEN, VIEWER_TOKEN, DENIED_TOKEN, SERVICE_TOKEN).contains(token)) {
                    return Mono.error(new JwtException("invalid"));
                }
                Instant now = Instant.now();
                String subject = token.equals(ADMIN_TOKEN) ? "admin"
                        : token.equals(VIEWER_TOKEN) ? "viewer_t"
                        : token.equals(DENIED_TOKEN) ? "denied"
                        : "agent-service";
                String role = token.equals(ADMIN_TOKEN) ? "ADMIN"
                        : token.equals(VIEWER_TOKEN) ? "VIEWER"
                        : "UNKNOWN";
                return Mono.just(Jwt.withTokenValue(token)
                        .header("alg", "none")
                        .subject(subject)
                        .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, token.equals(SERVICE_TOKEN)
                                ? SecurityTokenUtils.SERVICE_TOKEN_TYPE
                                : SecurityTokenUtils.USER_TOKEN_TYPE)
                        .claim("role", List.of(role))
                        .issuedAt(now)
                        .expiresAt(now.plusSeconds(60))
                        .build());
            };
        }
    }
}
