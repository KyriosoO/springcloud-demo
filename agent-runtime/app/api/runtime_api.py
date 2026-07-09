"""当前运行时路由与计划端点。"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.contracts.models import PlanOutcome, PlanRequest, RouteOutcome, RouteRequest
from app.core.document_rewrite import (
    DocumentRewriteRequest,
    DocumentRewriteResponse,
    RuntimeDocumentRewritePlanner,
    get_document_rewrite_planner,
)
from app.core.errors import RuntimeAuthError
from app.core.runtime_planning import (
    RuntimePlanPlanner,
    RuntimeRoutePlanner,
    get_plan_planner,
    get_route_planner,
)
from app.core.settings import Settings, get_settings

router = APIRouter()


async def verify_runtime_key(
    x_agent_runtime_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """以常量时间比较内部调用密钥和配置的共享密钥。"""
    if not x_agent_runtime_key:
        raise RuntimeAuthError("Missing X-Agent-Runtime-Key header")
    expected = settings.runtime_shared_key.get_secret_value()
    if not secrets.compare_digest(x_agent_runtime_key, expected):
        raise RuntimeAuthError("Invalid X-Agent-Runtime-Key")


@router.post(
    "/route",
    response_model=RouteOutcome,
    dependencies=[Depends(verify_runtime_key)],
)
async def route(
    request: RouteRequest,
    http_request: Request,
):
    """将请求解析为能力/领域决策或强类型澄清。"""
    planner = _resolve_planner(http_request, get_route_planner)
    return await planner.route(request)


@router.post(
    "/plan",
    response_model=PlanOutcome,
    dependencies=[Depends(verify_runtime_key)],
)
async def plan(
    request: PlanRequest,
    http_request: Request,
):
    """为已选择的能力生成可执行计划或强类型澄清。"""
    planner = _resolve_planner(http_request, get_plan_planner)
    return await planner.plan(request)


@router.post(
    "/document/rewrite",
    response_model=DocumentRewriteResponse,
    dependencies=[Depends(verify_runtime_key)],
)
async def document_rewrite(
    request: DocumentRewriteRequest,
    http_request: Request,
):
    """生成文档查询改写候选；候选不具备执行权威。"""
    planner: RuntimeDocumentRewritePlanner = _resolve_planner(
        http_request,
        get_document_rewrite_planner,
    )
    return await planner.rewrite(request)


def _resolve_planner(request: Request, dependency):
    # 请求体验证必须先于大模型配置加载；测试覆盖仍使用原始依赖键。
    override = request.app.dependency_overrides.get(dependency)
    return override() if override else dependency()
