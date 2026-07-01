package com.dylan.agent.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.api.request.PlanGenerateRequest;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.response.QueryAgentResultPayload;
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
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.planning.RuntimeDomainSchemaProjection;
import com.dylan.agent.planning.filter.FieldConstraintValidator;
import com.dylan.agent.planning.filter.FilterNormalizer;
import com.dylan.agent.planning.filter.QueryMergeEngine;
import com.dylan.agent.result.AgentResultProcessor;
import com.dylan.agent.security.AgentPermissionService;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

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

        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        var catalogView = DomainMetadataTestSupport.catalogView();
        var schemaProjection = new RuntimeDomainSchemaProjection(properties, catalogView);
        var runtimeClient = new TestRuntimeClient();
        var permissionService = new AgentPermissionService(properties, catalogView);

        var normalizer = new FilterNormalizer(properties);
        var constraints = new FieldConstraintValidator();
        var mergeEngine = new QueryMergeEngine(constraints);
        var queryValidator = new QueryPlanValidator(properties, normalizer, constraints, mergeEngine, catalogView);

        var maskerRegistry = new FieldMaskerRegistry(List.of(new NoneFieldMasker(),
                new IdCardFieldMasker(), new MobileFieldMasker(),
                new EmailFieldMasker(), new AddressFieldMasker()));
        var resultProcessor = new AgentResultProcessor(permissionService, maskerRegistry);

        var adapterPortResolver =
                DomainMetadataTestSupport.adapterPortResolver(new TestEmployeeAdapter(), null);
        var queryHandler = new QueryCapabilityHandler(
                queryValidator, permissionService, adapterPortResolver, resultProcessor);
        var clarifyHandler = new ClarifyCapabilityHandler(new ClarifyPlanValidator(catalogView));

        var registry = new AgentCapabilityHandlerRegistry(List.of(queryHandler, clarifyHandler));
        var router = new CapabilityRouter(registry);
        var descriptorFactory = new CapabilityDescriptorFactory(registry, adapterPortResolver, catalogView);

        orchestrator = new AgentOrchestrator(conversationService, schemaProjection, runtimeClient,
                permissionService, properties, new CapabilityRouteResolver(), router, descriptorFactory);

        admin = new AgentUserContext("admin", Set.of("agent:admin", "agent:viewer"));
        viewer = new AgentUserContext("viewer", Set.of("agent:viewer"));
    }

    @Nested
    @DisplayName("QUERY 链路")
    class QueryFlow {

        @Test
        @DisplayName("正常 QUERY 返回 RESULT")
        void shouldReturnQueryResult() {
            runtimeResponse = makeQueryResponse("position", AgentOperator.EQ, "HRM",
                    List.of("chineseName", "memberNo", "position"));
            AgentChatRequest req = chatRequest(null, "查询岗位是 HRM 的员工");

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
        @DisplayName("不支持字段返回 ERROR")
        void shouldRejectUnsupportedField() {
            runtimeResponse = makeQueryResponse("salary", AgentOperator.EQ, "1000",
                    List.of("chineseName", "salary"));
            AgentChatRequest req = chatRequest(null, "查询不存在字段");

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

    private AgentChatRequest chatRequest(String conversationId, String message) {
        AgentChatRequest req = new AgentChatRequest();
        req.setConversationId(conversationId);
        req.setMessage(message);
        return req;
    }

    private PlanGenerateResponse makeQueryResponse(
            String field, AgentOperator op, String value, List<String> selectFields) {
        var resp = new PlanGenerateResponse();
        resp.setRequestId(conversationService.turnId);
        var plan = new com.dylan.agent.api.plan.AgentPlan();
        plan.setPlanVersion("1.0");
        plan.setIntent(AgentIntent.QUERY);
        plan.setDomain("employee");
        var spec = new com.dylan.agent.api.plan.AgentQuerySpec();
        var filter = new com.dylan.agent.api.plan.AgentFilter();
        filter.setField(field);
        filter.setOperator(op);
        filter.setValue(value);
        spec.setFilters(List.of(filter));
        spec.setSelectFields(selectFields);
        spec.setPage(1);
        spec.setSize(20);
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

    class TestConversationService extends ConversationService {
        String completedTurnId = null;
        boolean failed = false;
        String turnId = "test-turn-001";

        TestConversationService() {
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
        public List<com.dylan.agent.api.runtime.RuntimeTurn> loadRecentTurns(
                String conversationId, String userId, int limit) {
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
        TestRuntimeClient() {
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
        @Override
        public AdapterQueryResult query(ValidatedQuery query) {
            return new AdapterQueryResult(List.of(), 0, 1, 20);
        }
    }
}
