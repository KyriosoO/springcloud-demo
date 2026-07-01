package com.dylan.agent.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.QueryableAdapterRegistry;
import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.api.request.PlanGenerateRequest;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.capability.AgentCapabilityHandlerRegistry;
import com.dylan.agent.capability.CapabilityDescriptorFactory;
import com.dylan.agent.capability.CapabilityRouteResolver;
import com.dylan.agent.capability.CapabilityRouter;
import com.dylan.agent.capability.clarify.ClarifyCapabilityHandler;
import com.dylan.agent.capability.clarify.ClarifyPlanValidator;
import com.dylan.agent.capability.query.QueryCapabilityHandler;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.client.AgentRuntimeClient;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.conversation.ConversationHandle;
import com.dylan.agent.conversation.ConversationService;
import com.dylan.agent.conversation.TurnHandle;
import com.dylan.agent.exception.AgentException;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.planning.RuntimeDomainSchemaFactory;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.planning.filter.QueryMergeEngine;
import com.dylan.agent.result.AgentResultProcessor;
import com.dylan.agent.security.AgentPermissionService;

@DisplayName("AgentOrchestrator")
class AgentOrchestratorTest {

    private TestConversationService conversationService;
    private AgentOrchestrator orchestrator;
    private AgentUserContext admin;
    private AgentUserContext viewer;
    private boolean runtimeThrows;
    private PlanGenerateResponse runtimeResponse;

    @BeforeEach
    void setUp() {
        conversationService = new TestConversationService();
        runtimeThrows = false;

        AgentProperties p = testProperties();
        var schemaFactory = new RuntimeDomainSchemaFactory(p, null);
        var runtimeClient = new TestRuntimeClient();
        var permissionService = new AgentPermissionService(p);

        var routeResolver = new CapabilityRouteResolver();
        var normalizer = new FilterNormalizer(p);
        var constraints = new FieldConstraintValidator();
        var mergeEngine = new QueryMergeEngine(constraints);
        var queryValidator = new QueryPlanValidator(p, normalizer, constraints, mergeEngine);

        var maskerRegistry = new FieldMaskerRegistry(List.of(new NoneFieldMasker(),
                new IdCardFieldMasker(), new MobileFieldMasker(),
                new EmailFieldMasker(), new AddressFieldMasker()));
        var resultProcessor = new AgentResultProcessor(permissionService, maskerRegistry);

        var adapter = new TestEmployeeAdapter();
        var adapterRegistry = new QueryableAdapterRegistry(List.of(adapter));

        var queryHandler = new QueryCapabilityHandler(
                queryValidator, permissionService, adapterRegistry, resultProcessor);
        var clarifyValidator = new ClarifyPlanValidator(p);
        var clarifyHandler = new ClarifyCapabilityHandler(clarifyValidator);

        var registry = new AgentCapabilityHandlerRegistry(List.of(queryHandler, clarifyHandler));
        var router = new CapabilityRouter(registry);
        var descriptorFactory = new CapabilityDescriptorFactory(registry, adapterRegistry, null, p);

        orchestrator = new AgentOrchestrator(conversationService, schemaFactory, runtimeClient,
                permissionService, p, routeResolver, router, descriptorFactory);

        admin = new AgentUserContext("admin", Set.of("agent:admin", "agent:viewer"));
        viewer = new AgentUserContext("viewer", Set.of("agent:viewer"));
    }

    @Nested
    @DisplayName("QUERY 链")
    class QueryFlow {

        @Test
        @DisplayName("正常 QUERY 返回 RESULT")
        void shouldReturnQueryResult() {
            runtimeResponse = makeQueryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName", "memberNo", "position"));
            AgentChatRequest req = chatRequest(null, "查询岗位是HRM的员工");
            AgentChatResponse resp = orchestrator.chat(admin, req);
            assertThat(resp.getType()).isEqualTo(AgentResponseType.RESULT);
            assertThat(resp.getConversationId()).isNotBlank();
            assertThat(resp.getTurnId()).isNotBlank();
            assertThat(resp.getSummary()).isEqualTo(resp.getMessage()).isNotBlank();
            assertThat(resp.getResult()).isInstanceOf(QueryAgentResultPayload.class);
            QueryAgentResultPayload result = (QueryAgentResultPayload) resp.getResult();
            assertThat(result.getQueryParameters()).isNotNull();
            assertThat(result.getQueryParameters().getDomain()).isEqualTo("employee");
            assertThat(result.getQueryParameters().getFilters()).hasSize(1);
            assertThat(result.getQueryParameters().getFilters().get(0).getField()).isEqualTo("position");
            assertThat(result.getQueryParameters().getFilters().get(0).getOperator()).isEqualTo(AgentOperator.EQ);
            assertThat(result.getQueryParameters().getFilters().get(0).getValue()).isEqualTo("HRM");
            assertThat(result.getQueryParameters().getSelectFields())
                    .containsExactly("chineseName", "memberNo", "position");
            assertThat(result.getQueryParameters().getPage()).isEqualTo(1);
            assertThat(result.getQueryParameters().getSize()).isEqualTo(20);
            assertThat(conversationService.completedTurnId).isNotNull();
        }

        @Test
        @DisplayName("CLARIFY 不调用 Adapter")
        void shouldReturnClarifyWithoutCallingAdapter() {
            runtimeResponse = makeClarifyResponse("请提供更多查询条件。");
            AgentChatRequest req = chatRequest(null, "帮我查员工");
            AgentChatResponse resp = orchestrator.chat(admin, req);
            assertThat(resp.getType()).isEqualTo(AgentResponseType.CLARIFY);
            assertThat(resp.getMessage()).isEqualTo("请提供更多查询条件。");
            assertThat(resp.getSummary()).isEqualTo(resp.getMessage());
            assertThat(resp.getResult()).isNull();
        }
    }

    @Nested
    @DisplayName("权限拒绝")
    class PermissionDenied {

        @Test
        @DisplayName("viewer 查询 idCardNo 返回 ERROR")
        void shouldRejectViewerQueryingIdCard() {
            runtimeResponse = makeQueryResponse("idCardNo", AgentOperator.EQ, "110101199001010011",
                    List.of("chineseName", "idCardNo"));
            AgentChatRequest req = chatRequest(null, "查询身份证号为110101199001010011的员工");
            assertThatThrownBy(() -> orchestrator.chat(viewer, req))
                    .isInstanceOf(AgentException.class);
            assertThat(conversationService.failed).isTrue();
        }
    }

    @Nested
    @DisplayName("Runtime 失败")
    class RuntimeFailure {

        @Test
        @DisplayName("Runtime 不可用时 Turn 标记为 FAILED")
        void shouldMarkTurnFailedOnRuntimeError() {
            runtimeThrows = true;
            AgentChatRequest req = chatRequest(null, "测试");
            assertThatThrownBy(() -> orchestrator.chat(admin, req))
                    .isInstanceOf(AgentException.class)
                    .extracting(e -> ((AgentException) e).getErrorCode())
                    .isEqualTo(AgentErrorCode.AGENT_RUNTIME_UNAVAILABLE);
            assertThat(conversationService.completedTurnId).isNull();
        }
    }

    // helpers

    private AgentChatRequest chatRequest(String conversationId, String message) {
        AgentChatRequest req = new AgentChatRequest();
        req.setConversationId(conversationId);
        req.setMessage(message);
        return req;
    }

    private PlanGenerateResponse makeQueryResponse(String field, AgentOperator op, String value, List<String> selectFields) {
        var resp = new PlanGenerateResponse();
        resp.setRequestId(conversationService.turnId);
        var plan = new com.dylan.agent.api.plan.AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.QUERY);
        plan.setDomain("employee");
        var spec = new com.dylan.agent.api.plan.AgentQuerySpec();
        var filter = new com.dylan.agent.api.plan.AgentFilter();
        filter.setField(field); filter.setOperator(op); filter.setValue(value);
        spec.setFilters(List.of(filter));
        spec.setSelectFields(selectFields);
        spec.setPage(1); spec.setSize(20);
        plan.setQuery(spec);
        resp.setPlan(plan);
        return resp;
    }

    private PlanGenerateResponse makeClarifyResponse(String question) {
        var resp = new PlanGenerateResponse();
        resp.setRequestId(conversationService.turnId);
        var plan = new com.dylan.agent.api.plan.AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.CLARIFY);
        plan.setDomain("employee");
        var cs = new com.dylan.agent.api.plan.ClarifySpec();
        cs.setQuestion(question);
        plan.setClarify(cs);
        resp.setPlan(plan);
        return resp;
    }

    private AgentProperties testProperties() {
        AgentProperties p = new AgentProperties();
        p.setIntentRoles(Map.of(
                AgentIntent.QUERY, Set.of("agent:viewer", "agent:admin"),
                AgentIntent.CLARIFY, Set.of("agent:viewer", "agent:admin")));

        AgentProperties.RuntimeProperties rt = new AgentProperties.RuntimeProperties();
        rt.setBaseUrl("http://localhost:9230"); rt.setSharedKey("test-key-at-least-16");
        rt.setConnectTimeout(java.time.Duration.ofSeconds(2)); rt.setReadTimeout(java.time.Duration.ofSeconds(15));
        rt.setMaxResponseBytes(65536);
        p.setRuntime(rt);

        AgentProperties.ConversationProperties c = new AgentProperties.ConversationProperties();
        c.setRecentTurnLimit(6); c.setRetentionDays(7); c.setCleanupDelay(java.time.Duration.ofHours(1));
        p.setConversation(c);

        AgentProperties.QueryProperties q = new AgentProperties.QueryProperties();
        q.setDefaultSize(20); q.setMaxSize(100); q.setMaxResultWindow(10000);
        q.setMaxFilters(5); q.setMaxInValues(20); q.setMaxFilterValueLength(256);
        q.setMaxDownstreamResponseBytes(2097152);
        p.setQuery(q);

        AgentProperties.DomainProperties emp = new AgentProperties.DomainProperties();
        emp.setAliases(List.of("员工", "employee"));
        emp.setAccessRoles(Set.of("agent:viewer", "agent:admin"));
        emp.setDefaultSelectFields(List.of("chineseName", "memberNo", "position"));
        Map<String, AgentProperties.FieldProperties> fields = new java.util.HashMap<>();
        fields.put("chineseName", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin")));
        fields.put("memberNo", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin")));
        fields.put("position", makeFp(Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin")));
        fields.put("contactAddress", makeFp(Set.of("agent:admin"), Set.of("agent:admin")));
        fields.put("idCardNo", makeFp(Set.of("agent:admin"), Set.of("agent:admin")));
        fields.put("phoneNo", makeFp(Set.of("agent:admin"), Set.of("agent:admin")));
        fields.put("email", makeFp(Set.of("agent:admin"), Set.of("agent:admin")));
        emp.setFields(fields);
        p.setDomains(Map.of("employee", emp));
        return p;
    }

    private AgentProperties.FieldProperties makeFp(Set<String> filterRoles, Set<String> displayRoles) {
        var fp = new AgentProperties.FieldProperties();
        fp.setAliases(List.of());
        fp.setType(com.dylan.agent.api.enums.AgentFieldType.STRING);
        fp.setOperators(Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN));
        fp.setFilterRoles(filterRoles); fp.setDisplayRoles(displayRoles); fp.setMask(MaskType.NONE);
        return fp;
    }

    // Test doubles

    class TestConversationService extends ConversationService {
        String completedTurnId = null;
        boolean failed = false;
        String turnId = "test-turn-001";

        public TestConversationService() {
            super(null, null, java.time.Clock.systemUTC(), new com.fasterxml.jackson.databind.ObjectMapper());
        }

        @Override
        public ConversationHandle openConversation(String requestedId, String userId) {
            return new ConversationHandle("test-conv-001");
        }

        @Override
        public TurnHandle startTurn(String conversationId, String userId, String message) {
            return new TurnHandle(turnId);
        }

        @Override
        public List<com.dylan.agent.api.runtime.RuntimeTurn> loadRecentTurns(String conversationId, String userId, int limit) {
            return List.of();
        }

        @Override
        public RuntimeQueryContext loadLatestQueryContext(String conversationId, String userId) {
            return null;
        }

        @Override
        public void completeSuccess(String turnId, AgentIntent intent, AgentResponseType responseType,
                                     String assistantMessage, Object contextToPersist) {
            this.completedTurnId = turnId;
        }

        @Override
        public void completeFailure(String turnId, AgentErrorCode errorCode, String assistantMessage) {
            this.failed = true;
        }
    }

    class TestRuntimeClient extends AgentRuntimeClient {
        public TestRuntimeClient() {
            super(null, null, null);
        }

        @Override
        public PlanGenerateResponse generate(PlanGenerateRequest request) {
            if (runtimeThrows) {
                throw new com.dylan.agent.exception.AgentRuntimeException("Runtime 不可用");
            }
            if (runtimeResponse != null) {
                runtimeResponse.setRequestId(request.getRequestId());
            }
            return runtimeResponse;
        }
    }

    static class TestEmployeeAdapter implements QueryableAdapter {
        @Override public String domain() { return "employee"; }
        @Override public java.util.Set<String> supportedFields() { return java.util.Set.of("chineseName"); }
        @Override public AdapterQueryResult query(ValidatedQuery query) {
            return new AdapterQueryResult(List.of(), 0, 1, 20);
        }
    }
}
