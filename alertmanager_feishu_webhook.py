#!/usr/bin/env python3
# 这是一个 Flask 应用，用于接收 Alertmanager 的告警消息，并将其转发到飞书机器人。

import os
import logging
import time
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from tenacity import retry, stop_after_attempt, wait_fixed

# 飞书机器人 Webhook URL
FEISHU_WEBHOOK = os.getenv(
    "FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx")
FEISHU_SECRET = os.getenv("FEISHU_SECRET", "xxxx")

if not FEISHU_WEBHOOK:
    raise RuntimeError("FEISHU_WEBHOOK 未配置")

# 日志配置
# 设置日志级别，默认INFO，可通过LOG_LEVEL环境变量设置
log_level_str = os.getenv("LOG_LEVEL", "INFO")
log_level = getattr(logging, log_level_str.upper(), logging.INFO)
logging.basicConfig(level=log_level,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

feishu = Flask(__name__)

def gen_sign(timestamp, secret):
    # 拼接timestamp和secret
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"),
                         digestmod=hashlib.sha256).digest()
    # 对结果进行base64处理
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def utc2cst(iso: str) -> str:
    # UTC 时间转 CST 时间，返回格式化字符串
    if not iso:
        return ""
    # 去掉末尾 'Z' 并加上 +00:00，方便 fromisoformat
    utc = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    cst = utc.astimezone(timezone(timedelta(hours=8)))
    return cst.strftime("%Y-%m-%d %H:%M:%S")

def build_msg(alerts, is_firing: bool):
    """飞书消息卡片"""
    color = "red" if is_firing else "green"
    title = " 🚨告警🚨" if is_firing else " ✅恢复✅"

    elements = []
    # 获取运行环境信息，从环境变量获取，若不存在则默认为空字符串
    run_env = os.getenv("RUN_ENVIRONMENT", "")
    for a in alerts:
        labels = a.get("labels", {})
        annos = a.get("annotations", {})
        name = labels.get("alertname", "unknown")
        inst = labels.get("instance", "").split(":")[0]
        namespace = labels.get("namespace", "")
        pod = labels.get("pod", "")
        severity = labels.get("severity", "")
        summary = annos.get("summary", "")
        desc = annos.get("description", "")
        start = utc2cst(a.get("startsAt", ""))
        end = utc2cst(a.get("endsAt", "")) if not is_firing else ""

        # 使用 Markdown 格式
        content = (
            # f"**{title}**\n"
            f"- **告警名称**：<font color='{color}'>{name}</font>\n"
            f"- **告警主题**：<font color='{color}'>{summary}</font>\n"
            f"- **告警详情**：<font color='{color}'>{desc}</font>\n"
            f"- **故障实例**：<font color='{color}'>{inst}</font>\n"
            f"- **故障APP**：<font color='{color}'>{namespace}</font>\n"
            f"- **故障应用**：<font color='{color}'>{pod}</font>\n"
        )
        
        # 如果运行环境有设置，则显示运行环境信息
        if run_env:
            content += f"- **运行环境**：<font color='{color}'>{run_env}</font>\n" 
        
        # 添加故障等级（如果存在）
        if severity:
            content += f"- **故障等级**：<font color='{color}'>{severity}</font>\n" 
            
        content += f"- **故障时间**：<font color='{color}'>{start}</font>\n"
        
        if end:
            content += f"- **恢复时间**：<font color='{color}'>{end}</font>\n" 
        # content += f"{at_text}\n"

        elements.append({
            "tag": "markdown",
            "content": content
        })

    header_title = f"{title}"
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": header_title},
            "template": color
        },
        "elements": elements
    }
    return card


@retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
def send_feishu(payload):
    # 发送飞书消息，失败则重试3次，每次间隔10秒
    resp = requests.post(FEISHU_WEBHOOK, json=payload, timeout=5)
    resp.raise_for_status()
    return resp


@feishu.route("/webhook", methods=["POST"])
def webhook():
    # 接收 Alertmanager 的告警请求
    data = request.get_json(force=True)
    log.debug("收到告警: %s", data)
    alerts = data.get("alerts", [])

    firing = [a for a in alerts if a.get("status") == "firing"]
    resolved = [a for a in alerts if a.get("status") == "resolved"]

    # 使用UTC时间戳以确保时区一致性
    ts = int(datetime.now(timezone.utc).timestamp())
    sign = gen_sign(ts, FEISHU_SECRET)

    for group, flag in ((firing, True), (resolved, False)):
        if not group:
            continue
        card = build_msg(group, flag)
        payload = {
            "timestamp": str(ts),
            "sign": sign,
            "msg_type": "interactive",
            "card": card
        }
        try:
            resp = send_feishu(payload)
        except Exception as e:
            log.error("发送失败: %s", e)
    return jsonify({"status": "ok", "resp": resp.text}), 200


if __name__ == "__main__":
    port = os.getenv("PORT", "9527")
    print(f"启动服务（端口：{port}")
    feishu.run(host="0.0.0.0", port=port)

# 健康检查接口
@feishu.route("/health", methods=["GET"])
def health():
    return "ok", 200
