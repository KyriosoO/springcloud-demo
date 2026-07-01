package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 已评审 Profile 行为规则的请求级安全投影。
 *
 * <p>只包含行为指令和可选 locale，不包含 Profile ID、capability 清单、权限或预算事实。
 */
@Schema(description = "Profile 行为投影")
public class RuntimeProfileBehaviorProjection {

    @Schema(description = "行为指令列表，最多 20 项", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(max = 20)
    private List<@Size(min = 1, max = 500) String> instructions = Collections.emptyList();

    @Schema(description = "locale（BCP-47），可为 null", nullable = true)
    private String locale;

    public RuntimeProfileBehaviorProjection() {
    }

    public List<String> getInstructions() { return instructions == null ? Collections.emptyList() : Collections.unmodifiableList(instructions); }
    public void setInstructions(List<String> instructions) { this.instructions = instructions == null ? null : new ArrayList<>(instructions); }
    public String getLocale() { return locale; }
    public void setLocale(String locale) { this.locale = locale; }
}
