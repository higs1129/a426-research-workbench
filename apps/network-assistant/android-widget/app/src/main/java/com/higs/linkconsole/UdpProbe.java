package com.higs.linkconsole;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

final class UdpProbe {
    static final String TARGET_HOST = "159.226.35.50";
    static final int TARGET_PORT = 40000;
    private static final int PACKET_COUNT = 3;

    interface Callback {
        void onComplete(Result result);
    }

    static final class Result {
        final boolean success;
        final String status;
        final String detail;

        Result(boolean success, String status, String detail) {
            this.success = success;
            this.status = status;
            this.detail = detail;
        }
    }

    private static final class Candidate {
        final Network network;
        final String label;
        final int score;

        Candidate(Network network, String label, int score) {
            this.network = network;
            this.label = label;
            this.score = score;
        }
    }

    private UdpProbe() {}

    static void send(Context context, Callback callback) {
        Context applicationContext = context.getApplicationContext();
        new Thread(
                () -> callback.onComplete(sendBlocking(applicationContext)),
                "link-console-udp-probe")
                .start();
    }

    private static Result sendBlocking(Context context) {
        ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
        if (manager == null) {
            return failure("系统网络服务不可用");
        }

        Candidate candidate = selectPhysicalNetwork(manager);
        if (candidate == null) {
            return failure("未找到可用的 5G、Wi-Fi 或有线物理网络；请先确认手机已经联网");
        }

        String probeId = Long.toHexString(System.currentTimeMillis()).toUpperCase(Locale.ROOT);
        try (DatagramSocket socket = new DatagramSocket()) {
            // Bind to the physical network explicitly so the probe does not travel through
            // the currently active Tailscale or Clash VpnService.
            candidate.network.bindSocket(socket);
            InetAddress target = InetAddress.getByName(TARGET_HOST);

            for (int sequence = 1; sequence <= PACKET_COUNT; sequence++) {
                String body = "LINK-CONSOLE-UDP-PROBE id=" + probeId
                        + " seq=" + sequence
                        + " time=" + System.currentTimeMillis();
                byte[] payload = body.getBytes(StandardCharsets.UTF_8);
                socket.send(new DatagramPacket(payload, payload.length, target, TARGET_PORT));
                if (sequence < PACKET_COUNT) Thread.sleep(180L);
            }

            return new Result(
                    true,
                    "3 个 UDP 测试包已发送",
                    "探针 " + probeId + " · 经" + candidate.label
                            + "绕过当前 VPN，发往 " + TARGET_HOST + ":" + TARGET_PORT
                            + "。本机发送成功不等于群晖已收到，请以群晖抓包为准。");
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            return failure("测试被中断，请重新发送");
        } catch (Exception exception) {
            String message = exception.getMessage();
            if (message == null || message.trim().isEmpty()) {
                message = exception.getClass().getSimpleName();
            }
            return failure("经" + candidate.label + "发送失败：" + message);
        }
    }

    private static Candidate selectPhysicalNetwork(ConnectivityManager manager) {
        Candidate best = null;
        for (Network network : manager.getAllNetworks()) {
            NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
            if (capabilities == null
                    || capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
                    || !capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) {
                continue;
            }

            String label;
            int score;
            if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                label = " Wi-Fi ";
                score = 30;
            } else if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
                label = "移动数据";
                score = 20;
            } else if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
                label = "有线网络";
                score = 10;
            } else {
                continue;
            }

            if (capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) {
                score += 100;
            }
            Candidate candidate = new Candidate(network, label, score);
            if (best == null || candidate.score > best.score) best = candidate;
        }
        return best;
    }

    private static Result failure(String detail) {
        return new Result(false, "UDP 测试包发送失败", detail);
    }
}
