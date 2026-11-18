"""Bounded user-facing diagnostics for local assistant service failures.

Transport categories never display response bodies or exception causes. Generic
errors retain application-authored protocol details with credential redaction.
"""
from __future__ import annotations

import re

from .persona import AssistantServiceError


_HINTS = {
    "invalid_endpoint": (
        "本地服务地址无效。请填写 http://127.0.0.1:端口（也支持 localhost 或 [::1]），"
        "地址只需主机和端口，不要附加 /v1、认证信息、查询参数或片段。"),
    "connection": (
        "无法连接本地服务。请启动当前功能对应的本地 API 服务，"
        "核对监听端口与这里的地址，然后重试。"),
    "timeout": (
        "本地服务响应超时。请等待服务准备完成，检查服务日志与资源占用，再重试。"),
    "redirect": (
        "本地服务返回了重定向，助手已停止请求。请填写本地 API 的直接地址并核对端口。"),
    "response": (
        "本地服务返回的响应无效或超过限制。请确认地址指向当前功能所需的本地 API，"
        "并查看服务日志后重试。"),
    "no_models": (
        "服务未列出模型 ID。请在本地服务中检查模型是否已添加并可供服务使用，然后刷新；"
        "也可手动填写正确的模型 ID。列表本身不代表模型已加载或支持聊天。"),
}


def _safe_detail(error: AssistantServiceError) -> str:
    detail = str(error)[:2000]
    detail = re.sub(r"(?i)\b(?:https?|file)://\S+", "[地址已隐藏]", detail)
    detail = re.sub(
        r"(?i)\b(?:authorization\s*[:=]\s*)?(?:bearer|basic)\s+\S+",
        "[认证信息已隐藏]", detail)
    detail = re.sub(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|token|secret|password|passwd)"
        r"[\"']?\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|\S+)",
        "[凭据已隐藏]", detail)
    detail = "".join(char if char.isprintable() else " " for char in detail)
    return " ".join(detail.split())[:320]


def service_error_hint(error: AssistantServiceError) -> str:
    """Return an actionable Chinese message without service response contents."""
    code = getattr(error, "code", "service")
    status = getattr(error, "status_code", None)
    if isinstance(status, int) and 100 <= status <= 599:
        if 300 <= status < 400:
            return f"HTTP {status}：" + _HINTS["redirect"]
        if status in (401, 403):
            return (f"本地服务返回 HTTP {status}（认证或权限失败）。"
                    "请核对服务的认证要求与访问权限；当前助手尚未提供 API 密钥配置。")
        if status == 404:
            return ("本地服务返回 HTTP 404。请核对端口与服务版本，"
                    "确认提供与当前功能兼容的 API。")
        if status == 429:
            return "本地服务返回 HTTP 429，请稍后重试，并检查服务的并发或请求限制。"
        return f"本地服务返回 HTTP {status}。请查看服务日志，确认 API 状态后重试。"
    if code in _HINTS:
        return _HINTS[code]
    detail = _safe_detail(error)
    hint = "请求未完成，请检查本地服务设置并重试。"
    return (hint + ("原因：" + detail if detail else ""))[:400]
