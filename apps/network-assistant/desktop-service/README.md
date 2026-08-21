# A426 网络体检

这是一个只在 Tailnet 内开放的手机 PWA，用一颗按钮同时检查：

- A426 到固定手机的 Tailscale 实际路径：IPv4/IPv6 直连、Peer Relay 或公共 DERP；
- 节点间 RTT 中位数、P95、抖动和丢包；
- A426 当前 UDP、IPv6、NAT 与 Tailscale DNS 状态；
- 手机 Clash Meta 的策略组、实际选择链和节点延迟；
- 手机浏览器当前国内/海外公网可达性。
- A426 本地 Codex 主线程的只读摘要：短标题、运行/完成状态与更新时间。

## 启动

双击 `start_network_diagnostics.bat`，或运行：

```powershell
.\start_network_diagnostics.ps1
```

A426 建议安装一次登录自启动任务。任务会常驻监测服务，异常退出后自动重启：

```powershell
.\install_network_diagnostics_autostart.ps1
```

如需移除：

```powershell
.\install_network_diagnostics_autostart.ps1 -Uninstall
```

后台只监听 `127.0.0.1:8788`。通过 Tailscale Serve 暴露到 Tailnet：

```powershell
tailscale serve --bg --https=443 --set-path /netcheck http://127.0.0.1:8788
```

不要运行 `tailscale serve reset`，因为 A426 上还有其他路径。手机地址：

```text
https://a426.tailabd98b.ts.net/netcheck/
```

完整 PWA 和 Clash 本机控制器读取需要 HTTPS。先在 Tailscale 管理后台的 DNS 页面启用 **HTTPS Certificates**，再配置上述 HTTPS Serve 路径。第一次在 Chrome 打开成功后，可以使用“添加到主屏幕”。页面外壳会被离线缓存；即使随后切换到 Clash，仍可从主屏幕打开并读取手机本机的 Clash 控制器。

若 Tailnet 尚未启用 HTTPS，可临时预览 Tailscale 检测页：

```powershell
tailscale serve --bg --http=80 --set-path /netcheck http://127.0.0.1:8788
```

HTTP 版不承诺能够安装 PWA，也不承诺 Android Chrome 能读取 `127.0.0.1` 的 Clash Controller。

## Clash Meta for Android 一次性配置

在 CMFA 的覆写设置中保持控制器只监听回环地址，并使用一段随机 Secret：

```yaml
external-controller: 127.0.0.1:9090
secret: "替换成你自己的长随机字符串"
external-controller-cors:
  allow-origins:
    - https://a426.tailabd98b.ts.net
  allow-private-network: true
```

然后在网页“配置本机控制接口”中填写：

- 地址：`http://127.0.0.1:9090`
- Secret：上面同一段字符串

HTTPS 下 Secret 写入该应用来源的 `localStorage`；HTTP 预览只使用 `sessionStorage`。Secret 不会发给 A426。Mihomo 的 API 密钥不是只读密钥，因此不得把控制器改成 `0.0.0.0`，也不要把 CORS 来源设为 `*`。

## 边界

- Tailscale 路径由 A426 反向探测，能准确区分本次探测是直连还是中继；A426 的 `netcheck` 只代表 A426 一侧网络。
- Rule 模式下没有一个适用于所有请求的“当前 Clash 节点”。页面显示策略选择链，并在有活跃连接时显示最常用连接链。
- 公网可达性是浏览器探测，不等于 Tailscale 节点间 RTT，也不等于所有 App 的实际路径。
- 工具不会修改 Tailscale 或 Clash 配置，也不保存历史诊断数据。
- Codex 状态接口只读取本机 `state_5.sqlite`、`session_index.jsonl` 与会话日志尾部的生命周期标记；不会返回提示词、回答正文、文件路径或线程 ID。

## 测试

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m unittest discover -s tests -v
python -m py_compile diagnostics.py server.py
node --check static\app.js
node --check static\sw.js
```
