package com.higs.linkconsole;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

final class CodexTaskSnapshot {
    static final class Task {
        String name = "未命名任务";
        String status = "stopped";
        long updatedAt = 0L;
    }

    final List<Task> tasks = new ArrayList<>();
    boolean available;
    String host = "A426";
    int activeCount;
    long generatedAt;
    long fetchedAt;
    long attemptedAt;
    String error = "";

    boolean isFresh(long maxAgeMs) {
        return available
                && error.isEmpty()
                && fetchedAt > 0L
                && System.currentTimeMillis() - fetchedAt <= maxAgeMs;
    }

    static CodexTaskSnapshot fromJson(JSONObject root) {
        CodexTaskSnapshot snapshot = new CodexTaskSnapshot();
        snapshot.available = root.optBoolean("ok", false);
        snapshot.host = clean(root.optString("host", "A426"), "A426");
        snapshot.activeCount = Math.max(0, root.optInt("active_count", 0));
        snapshot.generatedAt = root.optLong("generated_at_ms", 0L);
        snapshot.fetchedAt = root.optLong("client_fetched_at_ms", 0L);

        JSONArray items = root.optJSONArray("tasks");
        if (items == null) return snapshot;
        for (int index = 0; index < items.length(); index++) {
            JSONObject item = items.optJSONObject(index);
            if (item == null) continue;
            Task task = new Task();
            task.name = clean(item.optString("name", "未命名任务"), "未命名任务");
            task.status = clean(item.optString("status", "stopped"), "stopped");
            task.updatedAt = item.optLong("updated_at_ms", 0L);
            snapshot.tasks.add(task);
        }
        return snapshot;
    }

    int recentCompletedCount() {
        int count = 0;
        for (Task task : tasks) {
            if ("completed".equals(task.status)) count++;
        }
        return count;
    }

    int stoppedCount() {
        int count = 0;
        for (Task task : tasks) {
            if ("stopped".equals(task.status)) count++;
        }
        return count;
    }

    String summary() {
        if (!available) return "尚未读取 A426 任务状态";
        if (tasks.isEmpty()) return "最近 90 分钟没有任务变化";
        StringBuilder value = new StringBuilder();
        if (activeCount > 0) value.append(activeCount).append(" 个正在运行");
        int completed = recentCompletedCount();
        if (completed > 0) {
            if (value.length() > 0) value.append(" · ");
            value.append(completed).append(" 个刚完成");
        }
        int stopped = stoppedCount();
        if (stopped > 0) {
            if (value.length() > 0) value.append(" · ");
            value.append(stopped).append(" 个已停止");
        }
        return value.length() == 0 ? "任务状态已同步" : value.toString();
    }

    private static String clean(String value, String fallback) {
        if (value == null) return fallback;
        String cleaned = value.replaceAll("\\s+", " ").trim();
        return cleaned.isEmpty() ? fallback : cleaned;
    }
}
