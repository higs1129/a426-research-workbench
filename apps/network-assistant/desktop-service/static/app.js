(() => {
  "use strict";

  const STORAGE_KEYS = {
    controllerUrl: "network-check.clash-controller-url",
    controllerSecret: "network-check.clash-controller-secret",
  };
  const DEFAULT_CONTROLLER = "http://127.0.0.1:9090";
  const DELAY_TEST_URL = "https://www.gstatic.com/generate_204";

  const $ = (id) => document.getElementById(id);
  const ui = {
    runButton: $("runButton"),
    runIcon: $("runIcon"),
    runText: $("runText"),
    progressText: $("progressText"),
    progressBar: $("progressBar"),
    headline: $("headline"),
    overallBadge: $("overallBadge"),
    modeValue: $("modeValue"),
    browserRttValue: $("browserRttValue"),
    testedAtValue: $("testedAtValue"),
    tailscaleBadge: $("tailscaleBadge"),
    routeLabel: $("routeLabel"),
    pathValue: $("pathValue"),
    tailLatencyValue: $("tailLatencyValue"),
    tailJitterValue: $("tailJitterValue"),
    tailLossValue: $("tailLossValue"),
    phoneOnlineValue: $("phoneOnlineValue"),
    a426NetworkValue: $("a426NetworkValue"),
    dnsValue: $("dnsValue"),
    relayValue: $("relayValue"),
    tailscaleHint: $("tailscaleHint"),
    clashBadge: $("clashBadge"),
    clashGroupValue: $("clashGroupValue"),
    clashNodeValue: $("clashNodeValue"),
    clashLatencyValue: $("clashLatencyValue"),
    clashModeValue: $("clashModeValue"),
    clashChainValue: $("clashChainValue"),
    clashHint: $("clashHint"),
    internetBadge: $("internetBadge"),
    internetResults: $("internetResults"),
    notesPanel: $("notesPanel"),
    notesList: $("notesList"),
    versionText: $("versionText"),
    settingsButton: $("settingsButton"),
    settingsDialog: $("settingsDialog"),
    settingsForm: $("settingsForm"),
    closeDialogButton: $("closeDialogButton"),
    clearSettingsButton: $("clearSettingsButton"),
    controllerUrlInput: $("controllerUrlInput"),
    controllerSecretInput: $("controllerSecretInput"),
  };

  let running = false;

  function apiUrl(relative) {
    return new URL(`./api/${relative.replace(/^\/+/, "")}`, window.location.href).toString();
  }

  function withTimeout(milliseconds) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), milliseconds);
    return { signal: controller.signal, clear: () => window.clearTimeout(timer) };
  }

  async function fetchJson(url, options = {}, timeoutMs = 8000) {
    const timeout = withTimeout(timeoutMs);
    try {
      const response = await fetch(url, {
        cache: "no-store",
        credentials: "omit",
        ...options,
        signal: timeout.signal,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const error = new Error(payload?.error || `http_${response.status}`);
        error.status = response.status;
        throw error;
      }
      return payload;
    } finally {
      timeout.clear();
    }
  }

  function setChip(element, text, state = "neutral") {
    element.textContent = text;
    element.classList.remove("neutral", "good", "warn", "bad");
    element.classList.add(state);
  }

  function setOverall(text, state) {
    const label = ui.overallBadge.querySelector("span:last-child");
    label.textContent = text;
    ui.overallBadge.classList.remove("idle", "running", "good", "warn", "bad");
    ui.overallBadge.classList.add(state);
  }

  function setProgress(percent, text) {
    ui.progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    ui.progressText.textContent = text;
  }

  function formatMs(value) {
    return Number.isFinite(Number(value)) ? `${Math.round(Number(value))} ms` : "—";
  }

  function formatPercent(value) {
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(Number(value) % 1 ? 1 : 0)}%` : "—";
  }

  function formatTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(date);
  }

  function median(values) {
    if (!values.length) return null;
    const ordered = [...values].sort((a, b) => a - b);
    const middle = Math.floor(ordered.length / 2);
    return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
  }

  async function measureDashboardRtt(samples = 4) {
    const measurements = [];
    for (let index = 0; index < samples; index += 1) {
      const started = performance.now();
      await fetchJson(`${apiUrl("echo")}?sample=${Date.now()}-${index}`, {}, 5000);
      measurements.push(performance.now() - started);
    }
    return {
      available: true,
      samples: measurements.map((value) => Math.round(value)),
      medianMs: Math.round(median(measurements)),
    };
  }

  async function runTailscaleCheck() {
    const payload = await fetchJson(apiUrl("run"), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Network-Diagnostic": "1" },
      body: "{}",
    }, 35000);
    return { available: true, payload };
  }

  function safeControllerUrl(value) {
    let parsed;
    try {
      parsed = new URL((value || DEFAULT_CONTROLLER).trim());
    } catch {
      throw new Error("controller_url_invalid");
    }
    const loopback = parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost" || parsed.hostname === "[::1]";
    if (!loopback || !["http:", "https:"].includes(parsed.protocol)) {
      throw new Error("controller_must_be_loopback");
    }
    parsed.pathname = parsed.pathname.replace(/\/+$/, "");
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString().replace(/\/$/, "");
  }

  function controllerSettings() {
    const storage = window.isSecureContext ? localStorage : sessionStorage;
    return {
      url: safeControllerUrl(storage.getItem(STORAGE_KEYS.controllerUrl) || DEFAULT_CONTROLLER),
      secret: storage.getItem(STORAGE_KEYS.controllerSecret) || "",
    };
  }

  function controllerHeaders(secret) {
    return secret ? { Authorization: `Bearer ${secret}` } : {};
  }

  function chooseProxyGroup(proxies) {
    const groups = Object.entries(proxies || {}).filter(([, value]) => value && typeof value.now === "string");
    if (!groups.length) return null;
    const preferred = [
      /节点选择/i,
      /选择代理/i,
      /^proxy$/i,
      /^global$/i,
      /proxy/i,
    ];
    for (const pattern of preferred) {
      const match = groups.find(([name]) => pattern.test(name));
      if (match) return match;
    }
    return groups[0];
  }

  function resolveProxyChain(proxies, groupName) {
    const chain = [];
    const seen = new Set();
    let current = groupName;
    while (current && !seen.has(current) && chain.length < 12) {
      seen.add(current);
      chain.push(current);
      const proxy = proxies?.[current];
      if (!proxy || typeof proxy.now !== "string" || !proxy.now || proxy.now === current) break;
      current = proxy.now;
    }
    return chain;
  }

  function latestHistoryDelay(proxy) {
    const history = Array.isArray(proxy?.history) ? proxy.history : [];
    for (let index = history.length - 1; index >= 0; index -= 1) {
      const delay = Number(history[index]?.delay);
      if (delay > 0) return delay;
    }
    return null;
  }

  function mostCommonConnectionChain(connections) {
    const counts = new Map();
    for (const connection of connections || []) {
      if (!Array.isArray(connection?.chains) || !connection.chains.length) continue;
      const chain = connection.chains.join(" → ");
      counts.set(chain, (counts.get(chain) || 0) + 1);
    }
    const ordered = [...counts.entries()].sort((left, right) => right[1] - left[1]);
    return ordered[0] ? { chain: ordered[0][0], count: ordered[0][1] } : null;
  }

  async function runClashCheck() {
    const settings = controllerSettings();
    const headers = controllerHeaders(settings.secret);
    const request = (path, timeout = 7000) => fetchJson(`${settings.url}${path}`, { headers }, timeout);
    const [version, configs, proxyPayload, connectionPayload] = await Promise.all([
      request("/version"),
      request("/configs"),
      request("/proxies"),
      request("/connections").catch(() => ({ connections: [] })),
    ]);
    const proxies = proxyPayload?.proxies || {};
    const selected = chooseProxyGroup(proxies);
    const groupName = selected?.[0] || "未找到策略组";
    const chain = selected ? resolveProxyChain(proxies, groupName) : [];
    const nodeName = chain.at(-1) || "—";
    const node = proxies[nodeName];
    let delay = latestHistoryDelay(node);
    let delaySource = delay ? "history" : null;
    if (nodeName !== "—" && !["DIRECT", "REJECT", "REJECT-DROP", "PASS"].includes(nodeName.toUpperCase())) {
      try {
        const delayPayload = await request(
          `/proxies/${encodeURIComponent(nodeName)}/delay?url=${encodeURIComponent(DELAY_TEST_URL)}&timeout=5000`,
          8000,
        );
        if (Number(delayPayload?.delay) > 0) {
          delay = Number(delayPayload.delay);
          delaySource = "active";
        }
      } catch {
        // A recent history value is still useful; keep it if the active probe is blocked.
      }
    }
    return {
      available: true,
      version: version?.version || version?.meta || "已连接",
      mode: configs?.mode || "—",
      groupName,
      nodeName,
      chain,
      delay,
      delaySource,
      activeConnections: Array.isArray(connectionPayload?.connections) ? connectionPayload.connections.length : 0,
      commonConnection: mostCommonConnectionChain(connectionPayload?.connections),
    };
  }

  async function probePublicSite(url, timeoutMs = 6500) {
    const timeout = withTimeout(timeoutMs);
    const started = performance.now();
    try {
      await fetch(`${url}${url.includes("?") ? "&" : "?"}_=${Date.now()}`, {
        mode: "no-cors",
        cache: "no-store",
        credentials: "omit",
        signal: timeout.signal,
      });
      return { ok: true, latencyMs: Math.round(performance.now() - started) };
    } catch {
      return { ok: false, latencyMs: null };
    } finally {
      timeout.clear();
    }
  }

  async function runInternetCheck() {
    const [domestic, overseas] = await Promise.all([
      probePublicSite("https://www.baidu.com/favicon.ico"),
      probePublicSite("https://www.gstatic.com/generate_204"),
    ]);
    return { domestic, overseas };
  }

  function renderTailscale(result) {
    if (!result?.available || !result.payload?.ok) {
      setChip(ui.tailscaleBadge, "不可达", "bad");
      ui.pathValue.textContent = "未连到 A426";
      ui.routeLabel.textContent = "路径不可用";
      ui.tailscaleHint.textContent = "若页面来自离线缓存，这通常表示当前未连上 Tailscale；也可能是 A426 诊断服务未运行。";
      return { severity: "bad", path: "unreachable" };
    }

    const data = result.payload;
    const path = data.path || {};
    const peer = data.peer || {};
    const network = data.a426_network || {};
    const dns = data.a426_dns || {};
    const labels = {
      direct_ipv6: "IPv6 点对点直连",
      direct_ipv4: "IPv4 点对点直连",
      peer_relay: "自建 Peer Relay",
      derp: `DERP ${String(path.relay || "").toUpperCase()}`.trim(),
      unreachable: "探测不到手机",
      unknown: "路径未知",
    };
    const pathLabel = labels[path.path] || path.path || "—";
    const direct = String(path.path || "").startsWith("direct_");
    const relayed = path.path === "derp" || path.path === "peer_relay";
    const state = direct ? "good" : relayed ? "warn" : "bad";
    setChip(ui.tailscaleBadge, direct ? "已直连" : relayed ? "经中继" : "异常", state);
    ui.routeLabel.textContent = pathLabel;
    ui.pathValue.textContent = pathLabel;
    ui.tailLatencyValue.textContent = formatMs(path.rtt_ms?.p50);
    ui.tailJitterValue.textContent = formatMs(path.rtt_ms?.jitter);
    ui.tailLossValue.textContent = formatPercent(path.loss_pct);
    ui.phoneOnlineValue.textContent = peer.control_online ? "在线" : path.received ? "控制面离线，探测仍可达" : "离线";
    ui.a426NetworkValue.textContent = network.ok
      ? `${network.udp ? "UDP✓" : "UDP×"} / ${network.ipv6 ? "IPv6✓" : "IPv6×"}`
      : "未取得状态";
    ui.dnsValue.textContent = dns.ready ? "可用" : dns.magic?.ok ? "仅 MagicDNS 可用" : "异常";
    ui.relayValue.textContent = path.last_derp_relay
      ? String(path.last_derp_relay).toUpperCase()
      : network.preferred_derp?.code
        ? `${String(network.preferred_derp.code).toUpperCase()}（A426 首选）`
        : "无";
    ui.tailscaleHint.textContent = direct
      ? "A426 已直接碰到手机，不经过 DERP；这里的延迟是 Tailscale 节点间往返时间。"
      : path.path === "peer_relay"
        ? "当前借助你自己的 Peer Relay 转发，不是 Tailscale 公共 DERP。"
        : path.path === "derp"
          ? "当前无法建立点对点通道，流量正经 Tailscale 公共 DERP 中继。"
          : "A426 暂时无法反向探测到手机。";
    return { severity: state, path: path.path, data };
  }

  function renderClash(result) {
    if (!result?.available) {
      setChip(ui.clashBadge, "未读取", "neutral");
      ui.clashGroupValue.textContent = "策略组";
      ui.clashNodeValue.textContent = "—";
      ui.clashLatencyValue.textContent = "—";
      ui.clashModeValue.textContent = "—";
      ui.clashChainValue.textContent = "未连到手机本机控制接口";
      ui.clashHint.textContent = result?.configured
        ? "控制器不可达：检查 Clash Meta 是否运行、端口、Secret、CORS 和本地网络权限。"
        : "还未配置本机控制接口；这不代表 Clash 一定没有运行。";
      return { severity: "neutral", available: false };
    }

    const delayState = Number(result.delay) > 0 && result.delay < 500 ? "good" : Number(result.delay) >= 500 ? "warn" : "neutral";
    setChip(ui.clashBadge, "控制器在线", delayState);
    ui.clashGroupValue.textContent = result.groupName;
    ui.clashNodeValue.textContent = result.nodeName;
    ui.clashLatencyValue.textContent = formatMs(result.delay);
    ui.clashModeValue.textContent = String(result.mode || "—").toUpperCase();
    if (result.commonConnection) {
      ui.clashChainValue.textContent = `活跃连接常用：${result.commonConnection.chain}（${result.commonConnection.count} 条）`;
    } else if (result.chain.length) {
      ui.clashChainValue.textContent = `当前选择：${result.chain.join(" → ")}`;
    } else {
      ui.clashChainValue.textContent = "控制器在线，但没有找到可读的策略链";
    }
    ui.clashHint.textContent = result.delaySource === "active"
      ? `已通过当前节点主动测速；内核 ${result.version}。Rule 模式下，每个请求仍可能命中不同规则。`
      : `显示的是节点最近一次历史延迟；内核 ${result.version}。Rule 模式下不存在唯一的全局“当前节点”。`;
    return { severity: delayState, available: true };
  }

  function renderInternet(result) {
    const rows = ui.internetResults.querySelectorAll("div");
    const values = [result?.domestic, result?.overseas];
    rows.forEach((row, index) => {
      const strong = row.querySelector("strong");
      strong.textContent = values[index]?.ok ? `可达 · ${formatMs(values[index].latencyMs)}` : "不可达";
    });
    const both = values.every((value) => value?.ok);
    const any = values.some((value) => value?.ok);
    setChip(ui.internetBadge, both ? "均可达" : any ? "部分可达" : "不可达", both ? "good" : any ? "warn" : "bad");
    return { severity: both ? "good" : any ? "warn" : "bad", both, any };
  }

  function renderNotes(tailscale, clash, internet) {
    const notes = [];
    if (tailscale.path === "direct_ipv6") notes.push("手机与 A426 当前通过 IPv6 点对点直连，这是延迟最低、路径最稳定的状态。");
    if (tailscale.path === "direct_ipv4") notes.push("手机与 A426 当前通过 IPv4 点对点直连，没有经过公共中继。");
    if (tailscale.path === "derp") notes.push("当前走公共 DERP。它保证可连接，但通常比直连多一段路程，切换地区或网络后可能改变。");
    if (tailscale.path === "peer_relay") notes.push("当前走自建 Peer Relay；它比远距离公共 DERP 更可控，但仍多一次转发。");
    if ((tailscale.data?.path?.path_transitions || []).length > 1) notes.push(`本轮探测发生过路径切换：${tailscale.data.path.path_transitions.join(" → ")}。页面以最后一次成功探测作为“当前路径”。`);
    if (tailscale.data?.a426_network?.mapping_varies_by_destination) notes.push("A426 检测到映射随目标变化，这类 NAT 会降低 IPv4 UDP 穿透成功率；IPv6 直连仍可能成功。");
    if (tailscale.data?.a426_dns && !tailscale.data.a426_dns.ready) notes.push("A426 的 Tailscale 公共 DNS 自检未完全通过。它与是否直连是两件事，但可能导致网页打不开或出现 DNS unavailable。");
    if (clash.available) notes.push("Clash 控制器可读说明内核正在运行；这里展示的是策略选择/活跃连接链，不等于所有 App 都必然走同一节点。");
    if (!clash.available) notes.push("未读到 Clash 控制器，因此无法判断节点；这不能单独证明 Clash 没有接管网络。");
    if (!internet.both) notes.push("公网探测只反映当前浏览器路径。国内可达而海外不可达时，优先检查 Clash 规则、节点与 DNS。");
    ui.notesList.replaceChildren(...notes.map((note) => {
      const item = document.createElement("li");
      item.textContent = note;
      return item;
    }));
    ui.notesPanel.hidden = notes.length === 0;
  }

  function inferMode(tailscale, clash) {
    const tailAvailable = tailscale?.available && tailscale.payload?.ok;
    const clashAvailable = clash?.available;
    if (tailAvailable && clashAvailable) return "Tailnet 可达 · Clash 内核在线";
    if (tailAvailable) return tailscale.payload.path?.direct_established ? "Tailscale 直连" : "Tailscale 中继";
    if (clashAvailable) return "Clash 可用";
    return "当前路径未知";
  }

  function friendlyRunError(reason) {
    const message = String(reason?.message || reason || "");
    if (message === "diagnostic_already_running") return "A426 正在执行上一轮检测，请稍后再试";
    if (message.includes("controller_must_be_loopback")) return "控制器地址只能使用 127.0.0.1、localhost 或 ::1";
    if (message.includes("controller_url_invalid")) return "Clash 控制器地址格式不正确";
    if (reason?.name === "AbortError") return "连接超时";
    return "连接不可达或权限配置不完整";
  }

  async function runAllChecks() {
    if (running) return;
    running = true;
    ui.runButton.disabled = true;
    ui.runIcon.textContent = "⌁";
    ui.runText.textContent = "检测中";
    setOverall("正在检测", "running");
    setProgress(8, "正在同时检查 Tailscale、Clash 与公网路径…");
    ui.notesPanel.hidden = true;

    const tasks = [
      runTailscaleCheck(),
      measureDashboardRtt(),
      runClashCheck(),
      runInternetCheck(),
    ];
    let finished = 0;
    const tracked = tasks.map((promise) => promise.finally(() => {
      finished += 1;
      setProgress(8 + finished * 21, `已完成 ${finished} / ${tasks.length} 项检测`);
    }));
    const [tailSettled, rttSettled, clashSettled, internetSettled] = await Promise.allSettled(tracked);

    const tailscale = tailSettled.status === "fulfilled"
      ? tailSettled.value
      : { available: false, error: friendlyRunError(tailSettled.reason) };
    const rtt = rttSettled.status === "fulfilled" ? rttSettled.value : { available: false };
    const settingsStorage = window.isSecureContext ? localStorage : sessionStorage;
    const clashConfigured = Boolean(settingsStorage.getItem(STORAGE_KEYS.controllerSecret) || settingsStorage.getItem(STORAGE_KEYS.controllerUrl));
    const clash = clashSettled.status === "fulfilled"
      ? clashSettled.value
      : { available: false, configured: clashConfigured, error: friendlyRunError(clashSettled.reason) };
    const internet = internetSettled.status === "fulfilled"
      ? internetSettled.value
      : { domestic: { ok: false }, overseas: { ok: false } };

    const tailView = renderTailscale(tailscale);
    const clashView = renderClash(clash);
    const internetView = renderInternet(internet);
    ui.browserRttValue.textContent = rtt.available ? formatMs(rtt.medianMs) : "不可达";
    ui.testedAtValue.textContent = formatTime(new Date().toISOString());
    ui.modeValue.textContent = inferMode(tailscale, clash);
    renderNotes(tailView, clashView, internetView);

    const severities = [tailView.severity, internetView.severity, clashView.severity];
    if (tailView.severity === "good" && internetView.any) {
      setOverall("连接可用", severities.includes("warn") ? "warn" : "good");
      ui.headline.textContent = tailView.path.startsWith("direct_")
        ? "手机与 A426 已经直连，当前链路状态不错。"
        : "连接可用，但仍经过中继；下面能看到具体路径。";
    } else if (tailView.severity === "bad" && clashView.available) {
      setOverall("Clash 可用", "warn");
      ui.headline.textContent = "当前读不到 A426，但手机上的 Clash Meta 控制器仍然可用。";
    } else {
      setOverall("需要检查", "bad");
      ui.headline.textContent = "至少一条关键路径不可达，按下面的结果逐项排查。";
    }

    setProgress(100, "检测完成 · 所有测试均为只读");
    ui.runButton.disabled = false;
    ui.runIcon.textContent = "↻";
    ui.runText.textContent = "重新检测";
    running = false;
  }

  function openSettings() {
    const storage = window.isSecureContext ? localStorage : sessionStorage;
    ui.controllerUrlInput.value = storage.getItem(STORAGE_KEYS.controllerUrl) || DEFAULT_CONTROLLER;
    ui.controllerSecretInput.value = storage.getItem(STORAGE_KEYS.controllerSecret) || "";
    if (typeof ui.settingsDialog.showModal === "function") ui.settingsDialog.showModal();
    else ui.settingsDialog.setAttribute("open", "");
  }

  function closeSettings() {
    if (typeof ui.settingsDialog.close === "function") ui.settingsDialog.close();
    else ui.settingsDialog.removeAttribute("open");
  }

  function saveSettings(event) {
    event.preventDefault();
    try {
      const url = safeControllerUrl(ui.controllerUrlInput.value);
      const storage = window.isSecureContext ? localStorage : sessionStorage;
      storage.setItem(STORAGE_KEYS.controllerUrl, url);
      storage.setItem(STORAGE_KEYS.controllerSecret, ui.controllerSecretInput.value);
      closeSettings();
      runAllChecks();
    } catch (error) {
      ui.controllerUrlInput.setCustomValidity(friendlyRunError(error));
      ui.controllerUrlInput.reportValidity();
    }
  }

  function clearSettings() {
    localStorage.removeItem(STORAGE_KEYS.controllerUrl);
    localStorage.removeItem(STORAGE_KEYS.controllerSecret);
    sessionStorage.removeItem(STORAGE_KEYS.controllerUrl);
    sessionStorage.removeItem(STORAGE_KEYS.controllerSecret);
    ui.controllerUrlInput.value = DEFAULT_CONTROLLER;
    ui.controllerSecretInput.value = "";
    setChip(ui.clashBadge, "未配置", "neutral");
  }

  async function loadVersion() {
    try {
      const health = await fetchJson(apiUrl("health"), {}, 4000);
      ui.versionText.textContent = `网络体检 v${health.version}`;
    } catch {
      ui.versionText.textContent = "网络体检 · 离线外壳";
    }
  }

  ui.runButton.addEventListener("click", runAllChecks);
  ui.settingsButton.addEventListener("click", openSettings);
  ui.closeDialogButton.addEventListener("click", closeSettings);
  ui.clearSettingsButton.addEventListener("click", clearSettings);
  ui.settingsForm.addEventListener("submit", saveSettings);
  ui.controllerUrlInput.addEventListener("input", () => ui.controllerUrlInput.setCustomValidity(""));

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => {}));
  }
  loadVersion();
})();
