package com.dylan.agent.api.plan;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** CLARIFY 计划的追问规格，包含 1~500 字符的反问文本。 */
@Schema(description = "CLARIFY 计划的追问规格")
public class ClarifySpec {

    @Schema(description = "反问问题文本，1~500 字符", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(min = 1, max = 500)
    private String question;

    public ClarifySpec() {
    }

    public String getQuestion() { return question; }
    public void setQuestion(String question) { this.question = question; }
}
