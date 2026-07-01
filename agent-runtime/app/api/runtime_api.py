"""FastAPI 路由，/runtime/v1 端点。"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from langgraph.graph.state import CompiledStateGraph

from app.contracts.models import PlanGenerateRequest, PlanGenerateResponse
from app.contracts.semantic_validators import validate_plan_generate_request_semantics
from app.core.errors import RuntimeAuthError, RuntimePlanError, RuntimeProviderError, RuntimeTimeoutError
from app.core.graph import PlanGraphState, get_plan_graph
from app.core.settings import Settings, get_settings

router = APIRouter()


async def verify_runtime_key(
    x_agent_runtime_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """常量时间比较 X-Agent-Runtime-Key 与配置的共享密钥。"""
    if not x_agent_runtime_key:
        raise RuntimeAuthError("Missing X-Agent-Runtime-Key header")
    expected = settings.runtime_shared_key.get_secret_value()
    if not secrets.compare_digest(x_agent_runtime_key, expected):
        raise RuntimeAuthError("Invalid X-Agent-Runtime-Key")


@router.post(
    "/plans/generate",
    response_model=PlanGenerateResponse,
    dependencies=[Depends(verify_runtime_key)],
)
async def generate_plan(
    request: PlanGenerateRequest,
    graph: CompiledStateGraph = Depends(get_plan_graph),
) -> PlanGenerateResponse:
    """从用户自然语言输入生成 QUERY, CLARIFY 或 AGGREGATE plan。"""
    # 入口语义校验：model_validate() 不触发 monkey-patch，此处显式检查
    try:
        validate_plan_generate_request_semantics(request)
    except ValueError as e:
        raise RuntimePlanError(
            "RUNTIME_PLAN_INVALID",
            str(e),
            request_id=request.request_id,
        )

    state: PlanGraphState = {
        "request": request,
        "route_repair_attempted": False,
        "query_repair_attempted": False,
    }

    try:
        final_state = await graph.ainvoke(state)
    except (RuntimeProviderError, RuntimeTimeoutError) as exc:
        exc.request_id = request.request_id
        raise
    except Exception as e:
        # 兜底捕获意外异常（网络、序列化等），包装为 RuntimeProviderError
        raise RuntimeProviderError(
            f"Graph execution failed: {type(e).__name__}",
            request_id=request.request_id,
        )

    # route/query/aggregate 阶段的校验错误在 repair 耗尽后仍可能存在
    if (
        final_state.get("route_validation_errors")
        or final_state.get("query_validation_errors")
        or final_state.get("aggregate_validation_errors")
    ):
        raise RuntimePlanError(
            "RUNTIME_PLAN_INVALID",
            "Plan validation failed after repair",
            request_id=request.request_id,
        )

    plan = final_state.get("plan")
    if plan is None:
        raise RuntimePlanError(
            "RUNTIME_PLAN_INVALID",
            "No plan produced",
            request_id=request.request_id,
        )

    return PlanGenerateResponse(
        request_id=request.request_id,
        plan=plan,
    )
