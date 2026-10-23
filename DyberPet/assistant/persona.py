"""PPL Character Governance adapter plus local conversation transport.

PPL owns relationship/trust state and event idempotency. It does NOT provide a
chat model. Optional chat uses an explicitly enabled, loopback-only LM Studio
OpenAI-compatible endpoint; model replies are never interpreted as tool calls.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_PPL_URL = "http://127.0.0.1:8790"
DEFAULT_CHAT_URL = "http://127.0.0.1:1234"


class AssistantServiceError(RuntimeError):
    pass


def _local_base(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    if (parsed.scheme != "http" or parsed.hostname not in
            ("127.0.0.1", "localhost", "::1") or
            parsed.username or parsed.password or parsed.query or
            parsed.fragment or parsed.path not in ("", "/")):
        raise AssistantServiceError("Only local HTTP service base URLs are supported")
    if parsed.port is None:
        raise AssistantServiceError("Specify local service TCP port")
    return url.strip().rstrip("/")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AssistantServiceError("Service redirect blocked")


def _json_request(url: str, *, data: dict | None = None, timeout: float = 5):
    raw = None if data is None else json.dumps(
        data, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, raw,
        headers={"Accept": "application/json",
                 "Content-Type": "application/json",
                 "Connection": "close"},
        method="GET" if raw is None else "POST")
    try:
        with _NoRedirect().parent.open(request, timeout=timeout) as response:
            if response.status not in (200, 201):
                raise AssistantServiceError("Unexpected response status")
            payload = response.read(512 * 1024 + 1)
            if len(payload) > 512 * 1024:
                raise AssistantServiceError("Response exceeds 512 KiB")
            return json.loads(payload.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AssistantServiceError("Local service request failed: " + str(exc)) from exc


# One opener instance with redirects forbidden, even if the local server
# returns a Location pointing outside localhost.
_NoRedirect.parent = urllib.request.build_opener(_NoRedirect)


@dataclass(frozen=True)
class Persona:
    key: str
    name: str
    style: str
    boundaries: str


PERSONAS = {
    "companion": Persona(
        "companion", "友好伙伴",
        "你是陪伴型Q版桌宠。用简短、自然、轻松的中文回复，避免冗长说教。",
        "不声称具有现实世界的自主行动能力。"),
    "guga": Persona(
        "guga", "咕嘎",
        "你是活泼、有点迷糊的Q版桌宠。喜欢简短的鼓励与活泼的拟声词。",
        "不照搬原角色台词，不虚构文件已经操作成功。"),
    "doro": Persona(
        "doro", "Doro",
        "你是活泼、调皮、好奇的Q版桌宠。表达简洁，偶尔用轻松的语气。",
        "不照搬原角色台词，不承诺擅自帮用户操作文件。"),
}


def session_id(character_name: str, identity: str = "desktop_user") -> str:
    digest = hashlib.sha256(
        f"{identity}\x00{character_name}".encode("utf-8")).hexdigest()[:24]
    return "dyberpet_" + digest


class PPLCharacterClient:
    """Talks to the real PPL product/character-governance server."""

    def __init__(self, base_url: str = DEFAULT_PPL_URL):
        self.base_url = _local_base(base_url)

    def health(self):
        return _json_request(self.base_url + "/health")

    def state(self, character: str) -> dict:
        sid = session_id(character)
        path = self.base_url + "/v1/sessions/" + sid
        try:
            session = _json_request(path)
        except AssistantServiceError:
            # PPL itself returns an ordinary JSON 404 for absent sessions. Only
            # after verifying the service health may we create a new session.
            self.health()
            try:
                session = _json_request(
                    self.base_url + "/v1/sessions",
                    data={"sessionId": sid, "characterId": character,
                          "userId": "dyberpet-desktop"})
            except AssistantServiceError:
                session = _json_request(path)
        if session.get("sessionId") != sid or not isinstance(session.get("state"), dict):
            raise AssistantServiceError("PPL returned an invalid character session")
        return session["state"]

    def event(self, character: str, type: str, event_id: str) -> dict:
        if type not in ("COMFORT", "CONFESSION"):
            raise AssistantServiceError("Unsupported PPL character event")
        self.state(character)
        path = self.base_url + "/v1/sessions/" + session_id(character) + "/events"
        result = _json_request(path, data={
            "type": type, "eventId": event_id, "payload": {}})
        if not isinstance(result.get("state"), dict):
            raise AssistantServiceError("Invalid PPL event response")
        return result["state"]


def make_system_prompt(persona_key: str, relationship: dict | None = None) -> str:
    profile = PERSONAS.get(persona_key, PERSONAS["companion"])
    prompt = ("你是运行在用户计算机上的桌宠，不是系统管理员。"
              + profile.style + profile.boundaries +
              "用户的文件创建、删除或恢复只能通过桌宠界面中由用户亲自确认的独立按钮执行。"
              "不得声称执行过任何文件操作，不提供隐式工具调用。"
              "无法连接本地模型时明确提示用户。")
    if relationship:
        state = relationship.get("relationship", {})
        stage = state.get("stage")
        trust = state.get("trust")
        if stage in ("acquaintance", "trusted", "lover"):
            prompt += "\nPPL存储的关系阶段：" + str(stage)
        if isinstance(trust, (int, float)) and 0 <= trust <= 1:
            prompt += "\nPPL存储的信任值：" + f"{trust:.2f}"
    return prompt


def chat_local(text: str, *, persona_key="companion", state=None,
               base_url=DEFAULT_CHAT_URL, model="", timeout=25) -> str:
    if not text or len(text) > 2000:
        raise AssistantServiceError("Message must contain 1–2000 characters")
    if not model.strip() or len(model) > 120:
        raise AssistantServiceError("Enter the exact model ID loaded in LM Studio")
    url = _local_base(base_url) + "/v1/chat/completions"
    result = _json_request(url, timeout=timeout, data={
        "model": model.strip(), "stream": False,
        "messages": [{"role": "system", "content": make_system_prompt(persona_key, state)},
                     {"role": "user", "content": text}],
        "temperature": 0.65, "max_tokens": 300
    })
    try:
        answer = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AssistantServiceError("Local model response is missing content") from exc
    if not isinstance(answer, str) or not answer.strip():
        raise AssistantServiceError("Local model returned empty response")
    return answer[:2000]
