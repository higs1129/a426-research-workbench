package com.higs.linkconsole;

import android.content.Context;
import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import javax.net.ssl.SSLException;

final class NetworkRepository {
    interface Callback {
        void onComplete(NetworkSnapshot snapshot);
    }

    interface ClashSelectionCallback {
        void onComplete(boolean success, String message);
    }

    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor();
    private static final ExecutorService PROBE_EXECUTOR = Executors.newFixedThreadPool(2);
    private static final String TAILSCALE_RUN_URL =
            "https://a426.tailabd98b.ts.net/netcheck/api/run";
    private static final String CLASH_BASE_URL = "http://localhost:9090";
    private static final String CLASH_TEST_URL = "https://www.gstatic.com/generate_204";
    private static final String REMOTE_PROBE_URL = "https://chatgpt.com/api/auth/session";
    private static final int REMOTE_PROBE_ATTEMPTS = 3;

    private NetworkRepository() {}

    static void refresh(Context context, Callback callback) {
        Context appContext = context.getApplicationContext();
        EXECUTOR.execute(() -> {
            NetworkSnapshot snapshot = new NetworkSnapshot();
            snapshot.mode = VpnModeDetector.detect(appContext);
            snapshot.updatedAt = System.currentTimeMillis();
            Future<?> remoteFuture = null;

            if (snapshot.mode == NetworkSnapshot.Mode.TAILSCALE
                    || snapshot.mode == NetworkSnapshot.Mode.CLASH) {
                remoteFuture = PROBE_EXECUTOR.submit(() -> probeRemote(snapshot));
            } else {
                snapshot.remoteStatus = "当前未检测 Remote";
                snapshot.remoteDetail = "启用 Tailscale 或 Clash 后再检测当前 VPN 的网络入口";
            }

            if (snapshot.mode == NetworkSnapshot.Mode.TAILSCALE) {
                probeTailscale(snapshot);
            } else {
                snapshot.tailscaleStatus = "当前未启用 Tailscale";
                snapshot.tailscaleDetail = "切换后可检测手机到 A426 的真实路径";
            }

            probeClash(appContext, snapshot, snapshot.mode == NetworkSnapshot.Mode.CLASH);
            awaitProbe(remoteFuture, snapshot);
            finalizeCurrentSummary(snapshot);
            WidgetState.save(appContext, snapshot);
            NetworkWidgetProvider.updateAll(appContext);
            callback.onComplete(snapshot);
        });
    }

    static void selectClashAutomatic(Context context, ClashSelectionCallback callback) {
        Context appContext = context.getApplicationContext();
        EXECUTOR.execute(() -> {
            String secret = WidgetState.getClashSecret(appContext).trim();
            if (secret.isEmpty()) {
                callback.onComplete(false, "尚未保存 Clash 控制接口 Secret");
                return;
            }

            Exception lastError = null;
            for (int attempt = 0; attempt < 5; attempt++) {
                try {
                    callback.onComplete(true, selectClashAutomaticNow(secret));
                    return;
                } catch (Exception error) {
                    lastError = error;
                    if (attempt < 4) {
                        try {
                            Thread.sleep(700L + attempt * 350L);
                        } catch (InterruptedException interrupted) {
                            Thread.currentThread().interrupt();
                            callback.onComplete(false, "等待 Clash 控制接口时被中断");
                            return;
                        }
                    }
                }
            }
            callback.onComplete(false, friendlyClashSelectionError(lastError));
        });
    }

    private static void probeTailscale(NetworkSnapshot snapshot) {
        try {
            String body = request(
                    TAILSCALE_RUN_URL,
                    "POST",
                    "",
                    "{}",
                    8_000,
                    38_000,
                    true);
            JSONObject root = new JSONObject(body);
            if (!root.optBoolean("ok", false)) {
                throw new IOException("A426 诊断未完成");
            }
            JSONObject path = root.optJSONObject("path");
            if (path == null) {
                throw new IOException("诊断结果缺少路径");
            }
            String pathName = path.optString("path", "unknown");
            String relay = path.optString("relay", "");
            JSONObject rtt = path.optJSONObject("rtt_ms");
            double p50 = rtt == null ? -1 : rtt.optDouble("p50", -1);
            double p95 = rtt == null ? -1 : rtt.optDouble("p95", -1);
            double jitter = rtt == null ? -1 : rtt.optDouble("jitter", -1);
            int latency = p50 >= 0 ? (int) Math.round(p50) : -1;
            double loss = path.optDouble("loss_pct", -1);

            String routeLabel;
            switch (pathName) {
                case "direct_ipv6":
                    routeLabel = "IPv6 点对点直连";
                    break;
                case "direct_ipv4":
                    routeLabel = "IPv4 点对点直连";
                    break;
                case "peer_relay":
                    routeLabel = "自建 Peer Relay";
                    break;
                case "derp":
                    routeLabel = relay.isEmpty()
                            ? "公共 DERP 中继"
                            : "DERP " + relay.toUpperCase(Locale.ROOT);
                    break;
                case "unreachable":
                    routeLabel = "A426 无法探测到手机";
                    break;
                default:
                    routeLabel = "路径待确认";
                    break;
            }

            snapshot.tailscaleStatus = routeLabel;
            StringBuilder detail = new StringBuilder();
            if (latency >= 0) {
                detail.append("到 A426：p50 ").append(latency).append(" ms");
            }
            if (p95 >= 0) {
                if (detail.length() > 0) detail.append(" · ");
                detail.append("p95 ").append(Math.round(p95)).append(" ms");
            }
            if (jitter >= 0) {
                if (detail.length() > 0) detail.append(" · ");
                detail.append("抖动 ").append(Math.round(jitter)).append(" ms");
            }
            if (loss >= 0) {
                if (detail.length() > 0) detail.append(" · ");
                detail.append("丢包 ").append(formatNumber(loss)).append("%");
            }
            JSONArray transitions = path.optJSONArray("path_transitions");
            if (transitions != null && transitions.length() > 1) {
                detail.append(" · 本轮发生路径切换");
            }
            snapshot.tailscaleDetail = detail.length() == 0 ? "已连接，暂无延迟样本" : detail.toString();
            snapshot.currentRoute = routeLabel;
            snapshot.latencyMs = latency;
            snapshot.tailscaleP95Ms = p95 >= 0 ? (int) Math.round(p95) : -1;
            snapshot.tailscaleJitterMs = jitter >= 0 ? (int) Math.round(jitter) : -1;
            snapshot.tailscaleLossPct = loss;
        } catch (Exception error) {
            snapshot.tailscaleStatus = "Tailscale 已启用，诊断不可达";
            snapshot.tailscaleDetail = friendlyError(error);
            snapshot.currentRoute = "Tailscale 路径暂不可用";
            snapshot.note = "确认 A426 在线、Tailscale DNS 正常后重试";
        }
    }

    private static void probeClash(Context context, NetworkSnapshot snapshot, boolean measureDelay) {
        String secret = WidgetState.getClashSecret(context).trim();
        if (secret.isEmpty()) {
            snapshot.clashStatus = "尚未配置控制接口";
            snapshot.clashDetail = "在下方填写 Clash External Controller Secret";
            return;
        }

        try {
            request(CLASH_BASE_URL + "/version", "GET", secret, null, 2_000, 3_000, false);
            JSONObject configs = new JSONObject(
                    request(CLASH_BASE_URL + "/configs", "GET", secret, null, 2_000, 3_000, false));
            JSONObject proxyRoot = new JSONObject(
                    request(CLASH_BASE_URL + "/proxies", "GET", secret, null, 2_000, 4_000, false));

            String mode = configs.optString("mode", "unknown");
            JSONObject proxies = proxyRoot.optJSONObject("proxies");
            ClashRoute route = resolveClashRoute(proxies);
            String node = route.leafNode;
            int delay = findHistoryDelay(proxies, node);
            if (measureDelay && node != null && !node.isEmpty()) {
                int measured = measureClashDelay(secret, node);
                if (measured >= 0) delay = measured;
            }

            snapshot.clashStatus = route.display.isEmpty() ? "控制接口在线" : route.display;
            String modeLabel = "模式 " + mode.toUpperCase(Locale.ROOT);
            String policyLabel = route.automatic ? "自动策略已接管" : "当前为手动/固定选择";
            snapshot.clashDetail = delay >= 0
                    ? modeLabel + " · " + policyLabel + " · 实际节点 " + delay + " ms"
                    : modeLabel + " · " + policyLabel + " · 暂无节点延迟样本";

            if (snapshot.mode == NetworkSnapshot.Mode.CLASH) {
                snapshot.currentRoute = route.display.isEmpty() ? "Clash 代理已启用" : route.display;
                snapshot.latencyMs = delay;
            }
        } catch (Exception error) {
            if (isAuthorizationError(error)) {
                snapshot.clashStatus = "Secret 不匹配";
                snapshot.clashDetail = "请核对 Clash 覆写设置中的 Secret";
            } else {
                snapshot.clashStatus = "本机控制接口不可达";
                snapshot.clashDetail = "确认 Clash 正在运行且监听 127.0.0.1:9090";
            }
            if (snapshot.mode == NetworkSnapshot.Mode.CLASH) {
                snapshot.currentRoute = "Clash 已启用，节点信息不可读";
            }
        }
    }

    private static void finalizeCurrentSummary(NetworkSnapshot snapshot) {
        switch (snapshot.mode) {
            case NONE:
                snapshot.currentRoute = "当前流量直接走手机网络";
                snapshot.latencyMs = -1;
                break;
            case UNKNOWN:
                snapshot.currentRoute = "检测到其他 VPN，无法识别归属";
                snapshot.latencyMs = -1;
                break;
            case CLASH:
                if (snapshot.currentRoute == null || snapshot.currentRoute.isEmpty()) {
                    snapshot.currentRoute = "Clash Meta";
                }
                break;
            case TAILSCALE:
                break;
        }
        finalizeDiagnosticNote(snapshot);
    }

    private static void finalizeDiagnosticNote(NetworkSnapshot snapshot) {
        boolean remoteUnstable = snapshot.remoteAttempts > 0
                && snapshot.remoteSuccesses < snapshot.remoteAttempts;
        if (snapshot.mode == NetworkSnapshot.Mode.TAILSCALE && snapshot.latencyMs >= 0) {
            boolean firstLegUnstable = snapshot.tailscaleLossPct > 0
                    || snapshot.tailscaleJitterMs >= 60
                    || (snapshot.tailscaleP95Ms >= 0
                    && snapshot.tailscaleP95Ms - snapshot.latencyMs >= 100);
            if (firstLegUnstable) {
                snapshot.note = remoteUnstable
                        ? "本轮手机到 A426 的首段已出现抖动、长尾或丢包；晚高峰首先应检查当前 Wi-Fi/5G 与 DERP/直连路径。"
                        : "Remote 入口本轮可达，但手机到 A426 的首段波动明显，持续交互仍可能卡顿。";
            } else if (remoteUnstable) {
                snapshot.note = "本轮到 A426 的首段相对正常，但 Remote 入口不稳定；问题更可能位于 A426 出口、代理节点或目标服务方向。";
            }
        } else if (snapshot.mode == NetworkSnapshot.Mode.CLASH && remoteUnstable) {
            snapshot.note = "节点测速只代表测试网址；Remote 入口仍不稳定，需结合实际节点选择链与三次 HTTPS 探测判断。";
        }
    }

    private static void awaitProbe(Future<?> future, NetworkSnapshot snapshot) {
        if (future == null) return;
        try {
            future.get();
        } catch (Exception error) {
            snapshot.remoteStatus = "Remote 探测未完成";
            snapshot.remoteDetail = "探测任务异常，请重新检测";
        }
    }

    private static void probeRemote(NetworkSnapshot snapshot) {
        List<Integer> successfulLatency = new ArrayList<>();
        List<Integer> successfulStatuses = new ArrayList<>();
        String lastError = "";
        for (int attempt = 0; attempt < REMOTE_PROBE_ATTEMPTS; attempt++) {
            try {
                RemoteSample sample = probeRemoteOnce();
                successfulLatency.add(sample.latencyMs);
                successfulStatuses.add(sample.httpStatus);
            } catch (Exception error) {
                lastError = friendlyRemoteError(error);
            }
        }

        snapshot.remoteAttempts = REMOTE_PROBE_ATTEMPTS;
        snapshot.remoteSuccesses = successfulLatency.size();
        if (successfulLatency.isEmpty()) {
            snapshot.remoteStatus = "Remote 网络入口不可达";
            snapshot.remoteDetail = "HTTPS 0/" + REMOTE_PROBE_ATTEMPTS + " 成功"
                    + (lastError.isEmpty() ? "" : " · " + lastError);
            return;
        }

        successfulLatency.sort(Integer::compareTo);
        int median = successfulLatency.get(successfulLatency.size() / 2);
        int min = successfulLatency.get(0);
        int max = successfulLatency.get(successfulLatency.size() - 1);
        snapshot.remoteLatencyMs = median;
        boolean complete = successfulLatency.size() == REMOTE_PROBE_ATTEMPTS;
        boolean volatileResponse = max - min >= 500 || median >= 1_500;
        if (!complete) {
            snapshot.remoteStatus = "Remote 网络入口不稳定";
        } else if (volatileResponse) {
            snapshot.remoteStatus = "Remote 入口可达但波动较大";
        } else {
            snapshot.remoteStatus = "Remote 网络入口可达";
        }

        StringBuilder detail = new StringBuilder()
                .append("HTTPS ").append(successfulLatency.size()).append("/")
                .append(REMOTE_PROBE_ATTEMPTS).append(" 成功")
                .append(" · 中位响应 ").append(median).append(" ms")
                .append(" · 范围 ").append(min).append("–").append(max).append(" ms");
        if (!successfulStatuses.isEmpty()) {
            detail.append(" · HTTP ").append(successfulStatuses.get(successfulStatuses.size() - 1));
        }
        if (!complete && !lastError.isEmpty()) detail.append(" · ").append(lastError);
        snapshot.remoteDetail = detail.toString();
    }

    private static RemoteSample probeRemoteOnce() throws IOException {
        long started = System.nanoTime();
        HttpURLConnection connection = (HttpURLConnection) new URL(REMOTE_PROBE_URL).openConnection();
        connection.setConnectTimeout(4_000);
        connection.setReadTimeout(5_000);
        connection.setRequestMethod("GET");
        connection.setInstanceFollowRedirects(false);
        connection.setUseCaches(false);
        connection.setRequestProperty("Connection", "close");
        connection.setRequestProperty("Accept", "application/json,text/plain,*/*");
        connection.setRequestProperty("User-Agent", "LinkConsole/0.4 Android");
        int status = connection.getResponseCode();
        int elapsed = (int) Math.round((System.nanoTime() - started) / 1_000_000.0);
        connection.disconnect();
        if (status < 200 || status >= 500) {
            throw new IOException("HTTP " + status);
        }
        return new RemoteSample(elapsed, status);
    }

    private static String selectClashAutomaticNow(String secret) throws IOException, JSONException {
        request(CLASH_BASE_URL + "/version", "GET", secret, null, 2_000, 3_000, false);
        JSONObject root = new JSONObject(
                request(CLASH_BASE_URL + "/proxies", "GET", secret, null, 2_000, 4_000, false));
        JSONObject proxies = root.optJSONObject("proxies");
        String selector = findPrimarySelector(proxies);
        if (selector == null) throw new IOException("没有找到外层节点选择组");
        String automaticGroup = findAutomaticGroup(proxies, selector);
        if (automaticGroup == null) throw new IOException("节点选择中没有 URL-Test 自动组");

        request(
                CLASH_BASE_URL + "/proxies/" + Uri.encode(selector),
                "PUT",
                secret,
                new JSONObject().put("name", automaticGroup).toString(),
                2_000,
                4_000,
                false);

        // URL-Test/Fallback groups may retain a manually pinned `fixed` node.
        // Clearing it is best effort: older Mihomo versions may reject DELETE.
        try {
            request(
                    CLASH_BASE_URL + "/proxies/" + Uri.encode(automaticGroup),
                    "DELETE",
                    secret,
                    null,
                    2_000,
                    4_000,
                    false);
        } catch (Exception ignored) {
            // The group delay request below also clears fixed automatic selection.
        }
        try {
            measureClashGroup(secret, automaticGroup);
        } catch (Exception ignored) {
            // Selection is still valid even if some nodes time out during refresh.
        }

        JSONObject verifiedRoot = new JSONObject(
                request(CLASH_BASE_URL + "/proxies", "GET", secret, null, 2_000, 4_000, false));
        JSONObject verified = verifiedRoot.optJSONObject("proxies");
        JSONObject selectorState = verified == null ? null : verified.optJSONObject(selector);
        if (selectorState == null || !automaticGroup.equals(selectorState.optString("now", ""))) {
            throw new IOException("外层节点选择没有切到自动组");
        }
        ClashRoute route = resolveClashRoute(verified);
        String leaf = route.leafNode == null || route.leafNode.isEmpty() ? "等待测速" : route.leafNode;
        return "Clash 自动选择已接管：" + automaticGroup + " → " + leaf;
    }

    private static int measureClashDelay(String secret, String node) {
        try {
            String encodedNode = Uri.encode(node);
            String target = Uri.encode(CLASH_TEST_URL);
            String body = request(
                    CLASH_BASE_URL + "/proxies/" + encodedNode + "/delay?timeout=5000&url=" + target,
                    "GET",
                    secret,
                    null,
                    2_000,
                    7_000,
                    false);
            return new JSONObject(body).optInt("delay", -1);
        } catch (Exception ignored) {
            return -1;
        }
    }

    private static void measureClashGroup(String secret, String group) throws IOException {
        String target = Uri.encode(CLASH_TEST_URL);
        request(
                CLASH_BASE_URL + "/group/" + Uri.encode(group)
                        + "/delay?timeout=5000&url=" + target,
                "GET",
                secret,
                null,
                2_000,
                8_000,
                false);
    }

    private static ClashRoute resolveClashRoute(JSONObject proxies) {
        String primary = findPrimarySelector(proxies);
        if (primary == null) return new ClashRoute("", null, false);

        List<String> selections = new ArrayList<>();
        String current = primary;
        String leaf = null;
        boolean automatic = false;
        for (int depth = 0; depth < 8; depth++) {
            JSONObject entry = proxies.optJSONObject(current);
            if (entry == null) {
                leaf = current;
                if (!current.equals(primary)) selections.add(current);
                break;
            }
            if ("URLTest".equalsIgnoreCase(entry.optString("type", ""))) automatic = true;
            String next = entry.optString("now", "");
            if (next.isEmpty()) {
                if (!current.equals(primary)) leaf = current;
                break;
            }
            if (!"DIRECT".equalsIgnoreCase(next)) selections.add(next);
            JSONObject nextEntry = proxies.optJSONObject(next);
            if (nextEntry == null || nextEntry.optString("now", "").isEmpty()) {
                leaf = next;
                break;
            }
            current = next;
        }
        return new ClashRoute(String.join(" → ", selections), leaf, automatic);
    }

    private static String findPrimarySelector(JSONObject proxies) {
        if (proxies == null) return null;
        String[] preferred = {"节点选择", "PROXY", "Proxy", "代理", "GLOBAL"};
        for (String key : preferred) {
            JSONObject group = proxies.optJSONObject(key);
            if (group != null && "Selector".equalsIgnoreCase(group.optString("type", ""))) {
                return key;
            }
        }
        Iterator<String> keys = proxies.keys();
        while (keys.hasNext()) {
            String key = keys.next();
            JSONObject group = proxies.optJSONObject(key);
            if (group != null && "Selector".equalsIgnoreCase(group.optString("type", ""))
                    && findAutomaticGroup(proxies, key) != null) return key;
        }
        return null;
    }

    private static String findAutomaticGroup(JSONObject proxies, String selector) {
        if (proxies == null || selector == null) return null;
        JSONObject group = proxies.optJSONObject(selector);
        JSONArray members = group == null ? null : group.optJSONArray("all");
        if (members == null) return null;

        for (int index = 0; index < members.length(); index++) {
            String name = members.optString(index, "");
            JSONObject candidate = proxies.optJSONObject(name);
            if ("自动选择".equals(name)
                    && candidate != null
                    && "URLTest".equalsIgnoreCase(candidate.optString("type", ""))) return name;
        }
        for (int index = 0; index < members.length(); index++) {
            String name = members.optString(index, "");
            JSONObject candidate = proxies.optJSONObject(name);
            if (candidate == null || !"URLTest".equalsIgnoreCase(candidate.optString("type", ""))) {
                continue;
            }
            String normalized = name.toLowerCase(Locale.ROOT);
            if (normalized.contains("自动") || normalized.contains("auto")) return name;
        }
        for (int index = 0; index < members.length(); index++) {
            String name = members.optString(index, "");
            JSONObject candidate = proxies.optJSONObject(name);
            if (candidate != null
                    && "URLTest".equalsIgnoreCase(candidate.optString("type", ""))) return name;
        }
        return null;
    }

    private static int findHistoryDelay(JSONObject proxies, String node) {
        if (proxies == null || node == null) return -1;
        JSONObject proxy = proxies.optJSONObject(node);
        JSONArray history = proxy == null ? null : proxy.optJSONArray("history");
        if (history == null) return -1;
        for (int index = history.length() - 1; index >= 0; index--) {
            int delay = history.optJSONObject(index) == null
                    ? -1
                    : history.optJSONObject(index).optInt("delay", -1);
            if (delay > 0) return delay;
        }
        return -1;
    }

    private static String request(
            String address,
            String method,
            String secret,
            String body,
            int connectTimeout,
            int readTimeout,
            boolean diagnosticHeader) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection();
        connection.setConnectTimeout(connectTimeout);
        connection.setReadTimeout(readTimeout);
        connection.setRequestMethod(method);
        connection.setUseCaches(false);
        connection.setRequestProperty("Accept", "application/json");
        if (!secret.isEmpty()) {
            connection.setRequestProperty("Authorization", "Bearer " + secret);
        }
        if (diagnosticHeader) {
            connection.setRequestProperty("X-Network-Diagnostic", "1");
        }
        if (body != null) {
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(bytes);
            }
        }

        int status = connection.getResponseCode();
        InputStream stream = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
        String response = readAll(stream);
        connection.disconnect();
        if (status < 200 || status >= 300) {
            throw new IOException("HTTP " + status + ": " + response);
        }
        return response;
    }

    private static String readAll(InputStream stream) throws IOException {
        if (stream == null) return "";
        StringBuilder result = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) result.append(line);
        }
        return result.toString();
    }

    private static String formatNumber(double value) {
        if (Math.rint(value) == value) return String.valueOf((int) value);
        return String.format(Locale.ROOT, "%.1f", value);
    }

    private static boolean isAuthorizationError(Exception error) {
        String message = error.getMessage();
        return message != null && (message.contains("HTTP 401") || message.contains("HTTP 403"));
    }

    private static String friendlyError(Exception error) {
        String name = error.getClass().getSimpleName();
        if (name.contains("UnknownHost")) return "Tailscale DNS 暂不可用";
        if (name.contains("Timeout")) return "连接 A426 超时，请稍后重试";
        String message = error.getMessage();
        return message == null || message.isEmpty() ? "诊断请求失败" : message;
    }

    private static String friendlyRemoteError(Exception error) {
        if (error instanceof UnknownHostException) return "DNS 解析失败";
        if (error instanceof SocketTimeoutException) return "连接或响应超时";
        if (error instanceof SSLException) return "TLS 建连失败";
        String message = error.getMessage();
        if (message != null && message.startsWith("HTTP 5")) return "目标服务返回 " + message;
        return message == null || message.isEmpty() ? "HTTPS 请求失败" : message;
    }

    private static String friendlyClashSelectionError(Exception error) {
        if (error == null) return "控制接口没有响应";
        if (isAuthorizationError(error)) return "Secret 不匹配";
        String message = error.getMessage();
        if (message == null || message.isEmpty()) return "控制接口没有响应";
        if (message.contains("Connection refused") || message.contains("failed to connect")) {
            return "Clash 控制接口尚未就绪";
        }
        return message;
    }

    private static final class RemoteSample {
        final int latencyMs;
        final int httpStatus;

        RemoteSample(int latencyMs, int httpStatus) {
            this.latencyMs = latencyMs;
            this.httpStatus = httpStatus;
        }
    }

    private static final class ClashRoute {
        final String display;
        final String leafNode;
        final boolean automatic;

        ClashRoute(String display, String leafNode, boolean automatic) {
            this.display = display;
            this.leafNode = leafNode;
            this.automatic = automatic;
        }
    }
}
