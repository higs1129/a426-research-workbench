package com.higs.linkconsole;

final class NetworkSnapshot {
    enum Mode {
        TAILSCALE,
        CLASH,
        NONE,
        UNKNOWN
    }

    Mode mode = Mode.UNKNOWN;
    String currentRoute = "等待检测";
    int latencyMs = -1;
    int tailscaleP95Ms = -1;
    int tailscaleJitterMs = -1;
    double tailscaleLossPct = -1;
    String tailscaleStatus = "未检测";
    String tailscaleDetail = "启用 Tailscale 后可检测直连、Peer Relay 或 DERP";
    String remoteStatus = "未检测";
    String remoteDetail = "启用 Tailscale 或 Clash 后检测 ChatGPT Remote 网络入口";
    int remoteLatencyMs = -1;
    int remoteSuccesses = 0;
    int remoteAttempts = 0;
    String clashStatus = "未检测";
    String clashDetail = "填写本机控制接口 Secret 后可读取模式与节点";
    String note = "";
    long updatedAt = 0L;

    String modeLabel() {
        switch (mode) {
            case TAILSCALE:
                return "Tailscale";
            case CLASH:
                return "Clash Meta";
            case NONE:
                return "未启用 VPN";
            default:
                return "其他 VPN";
        }
    }

    String latencyLabel() {
        return latencyMs >= 0 ? latencyMs + " ms" : "—";
    }

    String widgetRouteLabel() {
        if (remoteAttempts <= 0) return currentRoute;
        String remoteLabel;
        if (remoteSuccesses == remoteAttempts) {
            remoteLabel = "Remote 通";
        } else if (remoteSuccesses > 0) {
            remoteLabel = "Remote " + remoteSuccesses + "/" + remoteAttempts;
        } else {
            remoteLabel = "Remote 不通";
        }
        return currentRoute + " · " + remoteLabel;
    }
}
