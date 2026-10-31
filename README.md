# OBS Screen Share

Windows 上的个人屏幕分享原型：OBS 采集屏幕、显卡编码，通过自己的服务器转发，对方打开网页观看。

本项目提供一个**绑定指定实体网卡的本地 RTMP → RTMPS 转发器**、OBS 启动脚本和服务器配置示例。它不是完整的桌面客户端，也不会自动安装或配置 OBS、MediaMTX 和证书。

```text
OBS / H.264 + AAC
  → 127.0.0.1:29350
  → 指定实体网卡 / TLS
  → MediaMTX / RTMPS
  → 视频原样转发，音频转换为 Opus
  → 网页 / WebRTC
```

没有 VDO.Ninja 公共服务依赖。观看端无需安装 OBS。

## 依赖

- Windows 10/11、Python 3.10+、OBS Studio。
- Linux 服务器，安装 [MediaMTX](https://github.com/bluenviron/mediamtx)、支持 libopus 的 [FFmpeg](https://ffmpeg.org/)、Nginx。
- 指向服务器的域名和有效的 TLS 证书。
- 服务器需开放 TCP 443、1936、8190；确认云安全组和系统防火墙均允许。8889、8554、9997 只监听回环地址。

## 电脑端配置

1. 复制 `config.example.json` 为 `config.json`。
2. 用 PowerShell 查看网卡：

   ```powershell
   Get-NetAdapter | Select-Object Name, ifIndex, Status
   Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceIndex, IPAddress
   ```

3. 填写服务器真实 IPv4、证书域名、实体网卡索引和本地 IPv4；不要选代理软件的虚拟网卡。更新 OBS 程序路径、配置文件名与场景集合名。
4. 双击 `start.cmd`。这会启动本地转发器和 OBS，不会自动直播。

转发器显式设置 Windows `IP_UNICAST_IF` 并绑定指定源地址，连接固定服务器 IP，以 `tls_hostname` 验证服务器证书。不读取 HTTP/SOCKS 代理设置，失败时不回退到其他网卡或代理。只有 OBS 连接这个本地入口的上传流量受此约束；手机、浏览器和其他程序的路由不在此保证范围内。

更换网卡或本地 IP 后需更新配置并重启转发器。显式接口绑定不能作为对所有第三方 VPN、WFP 网络过滤软件的绝对保证，应结合本地连接和服务器来源地址验证实际路径。

## OBS 配置

先在 OBS 创建与 `config.json` 一致的配置文件及场景集合，添加“显示器采集”或“游戏采集”、桌面声音。按需要启用麦克风。

推流服务选“自定义”，服务器填：

```text
rtmp://127.0.0.1:29350/YOUR_RANDOM_STREAM_ID_in?user=obs-publisher&pass=YOUR_PUBLISH_PASSWORD
```

推流密钥留空。这里使用的是本机回环地址；转发器到服务器的链路经过 TLS 加密。示例标记必须换成与服务器一致的值，密码建议只使用 URL 安全字符。

建议初始输出：

| 设置 | 值 |
|---|---|
| 视频 | H.264，优先显卡硬件编码 |
| 分辨率 / 帧率 | 1920×1080 / 30fps |
| 码率 | CBR 4000kbps，根据网络调整 |
| 关键帧间隔 | 1 秒 |
| B 帧 | 0，浏览器 WebRTC 兼容所需 |
| 编码配置 | Baseline |
| 音频 | AAC、48kHz、立体声、128kbps |

点击“开始直播”后，对方打开：

```text
https://share.example.com/obs-live/YOUR_RANDOM_STREAM_ID/
```

页面可能需要点击播放或取消静音。停止直播后画面断开属于正常现象。

## 服务器配置

`server/` 内是模板，需要人工替换占位符：

- `mediamtx.example.yml` → `/opt/obs-share/config.yml`。
- `audio-forward.example.sh` → `/opt/obs-share/audio-forward.sh`，设置可执行权限。
- `obs-share.service` → systemd 单元；先创建低权限的 `obs-share` 用户。
- `nginx.example.conf` → 合并进已有 HTTPS 站点，不要覆盖现有站点。

TLS 证书复制或授权给 MediaMTX 服务用户读取，并配置证书续期后的更新与重启。限制配置、私钥和音频转发脚本的读取权限。

观看授权依赖不可猜测的随机流名称：请生成至少 128 位随机值替换 `YOUR_RANDOM_STREAM_ID`，只将链接发给观看者。模板提供发布密码认证；公网使用前必须替换示例密码。这不是有账号和权限管理的多人直播平台。

服务器视频使用 `-c:v copy`，仅将 AAC 音频转换为 Opus。服务不会录制；本地转发器日志不记录流内容和发布密码。OBS 自身日志可能包含完整推流地址，分享日志前需清理凭据。

## 可选：后台控制 OBS

`obs_control.py` 提供 OBS WebSocket v5 的本地认证和请求封装，启动转发器并不依赖它。若要使用：

```powershell
python -m pip install -r requirements.txt
```

在 OBS 中启用带密码的 WebSocket 服务，将密码填入本地 `config.json`。不要把密码或这个配置文件上传到 GitHub。

```python
from obs_control import OBS

obs = OBS()
try:
    print(obs.call('GetStreamStatus'))
finally:
    obs.close()
```

## 实测与限制

原部署使用 Windows 10、RTX 4060、OBS 32.2.2、MediaMTX 1.21.3。一次约 2 分 43 秒的测试色卡推流，没有 OBS 编码跳帧或重连。后台 Chromium 采样解码到 1080p30，RTP 丢包和解码丢帧均为 0；播放器另有呈现丢帧，不能据此宣称全程无丢帧。测试音在服务端转换后检测到了非零音量。

公开源码对原部署做了路径和参数整理；这些记录属于原部署结果，不代表所有环境都已经验证。游戏负载、真实手机网络、音画同步和持续运行仍需在自己的设备上实测，没有承诺优于腾讯会议。

当前采用服务器转发。P2P 在双方线路良好时可能延迟更低，但本项目没有实现自动 P2P 或路线切换。服务器出口带宽不足、客户端网络丢包、TCP 队头阻塞或显卡负载高都可能导致卡顿。

## 许可证

本仓库自有代码使用 MIT。OBS、MediaMTX、FFmpeg 保持各自许可证，本仓库不分发它们的源码和二进制。
