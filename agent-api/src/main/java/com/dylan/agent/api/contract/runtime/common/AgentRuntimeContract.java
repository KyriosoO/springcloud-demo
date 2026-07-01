package com.dylan.agent.api.contract.runtime.common;

/**
 * 唯一契约生成世代标识。
 *
 * <p>{@link #VERSION} 唯一标识整套 Route/Plan Runtime contract generation。
 * OpenAPI {@code info.version}、RouteRequest/PlanRequest {@code contractVersion}
 * 和 Planning Service 不允许出现平行版本轴。
 *
 * <p>此类是不可实例化的 final 工具类。
 */
public final class AgentRuntimeContract {

    /** 整套 Route/Plan 契约的唯一 generation 版本。 */
    public static final String VERSION = "1.0.0";

    private AgentRuntimeContract() {
    }
}
