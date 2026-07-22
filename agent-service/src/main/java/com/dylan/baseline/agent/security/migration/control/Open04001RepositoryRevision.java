package com.dylan.baseline.agent.security.migration.control;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/** 验证受控迁移安全源码与签名记录所绑定提交一致；只读Git元数据。 */
final class Open04001RepositoryRevision {

    private static final Pattern COMMIT = Pattern.compile("[0-9a-f]{40}");
    private static final List<String> SECURITY_PATHS = List.of(
            "agent-service/src/main/java/com/dylan/baseline/agent/security",
            "scripts/security");

    private Open04001RepositoryRevision() {
    }

    static void verify(Path root, String expectedRevision) throws IOException, InterruptedException {
        if (!COMMIT.matcher(expectedRevision).matches()) {
            throw new IllegalArgumentException("repository revision must be a full lowercase Git commit SHA");
        }
        CommandResult resolved = git(root, "rev-parse", "--verify", expectedRevision + "^{commit}");
        if (resolved.exitCode() != 0 || !expectedRevision.equals(resolved.output().strip())) {
            throw new IllegalArgumentException("repository revision is not the exact local Git commit");
        }
        List<String> diff = new ArrayList<>(List.of("diff", "--quiet", expectedRevision, "--"));
        diff.addAll(SECURITY_PATHS);
        if (git(root, diff.toArray(String[]::new)).exitCode() != 0) {
            throw new IllegalArgumentException("security implementation differs from the signed repository revision");
        }
        List<String> status = new ArrayList<>(List.of("status", "--porcelain", "--untracked-files=all", "--"));
        status.addAll(SECURITY_PATHS);
        CommandResult worktree = git(root, status.toArray(String[]::new));
        if (worktree.exitCode() != 0 || !worktree.output().isBlank()) {
            throw new IllegalArgumentException("security implementation worktree is not clean");
        }
    }

    private static CommandResult git(Path root, String... arguments) throws IOException, InterruptedException {
        List<String> command = new ArrayList<>(List.of("git", "-C", root.toString()));
        command.addAll(List.of(arguments));
        Process process = new ProcessBuilder(command).redirectErrorStream(true).start();
        String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        return new CommandResult(process.waitFor(), output);
    }

    private record CommandResult(int exitCode, String output) {
    }
}
