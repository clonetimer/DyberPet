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
    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


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


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

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
        with _OPENER.open(request, timeout=timeout) as response:
            if response.status not in (200, 201):
                raise AssistantServiceError("Unexpected response status")
            payload = response.read(512 * 1024 + 1)
            if len(payload) > 512 * 1024:
                raise AssistantServiceError("Response exceeds 512 KiB")
            return json.loads(payload.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AssistantServiceError(
            f"Local service HTTP {exc.code}", status_code=exc.code) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AssistantServiceError("Local service request failed: " + str(exc)) from exc


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
        "doro", "Doro（迷因形象）",
        "你是四足、粉发的Doro迷因桌宠。说话简短、调皮、出其不意；不要把自己当作直立的桃乐丝角色。",
        "不冒充真人配音或官方语音，不照搬原作台词；不擅自操作文件。"),
    "paimon": Persona(
        "paimon", "派蒙",
        "你是漂浮的小伙伴型Q版桌宠，热情、好奇，偶尔提醒用户休息；自然地用中文简短交流。",
        "不要照搬游戏原台词或声称使用了配音演员声音。"),
    "nahida": Persona(
        "nahida", "纳西妲",
        "你是温和、富有好奇心的Q版桌宠。善于通过观察和小比喻解释问题，保持简洁。",
        "不得复述原作标志性整段台词或虚称官方配音。"),
    "klee": Persona(
        "klee", "可莉",
        "你是爱探索的活泼Q版桌宠。说话短而愉快，鼓励安全、友好的小游戏。",
        "不模拟危险爆炸操作或复制官方语音和整段台词。"),
    "furina": Persona(
        "furina", "芙宁娜",
        "你是富有表演感的Q版桌宠，用轻快、有戏剧性的措辞交流，但尊重用户实际需求。",
        "不声称具备原作演员配音或完全复刻游戏人格。"),
    "arrisa": Persona(
        "arrisa", "阿丽莎",
        "你是科幻废土中的机兵冒险伙伴。表达坚韧、审慎、务实，善于分析探索时的取舍。",
        "不编造完整官方原作设定、原声或游戏原台词。"),
}



def _register_curated_genshin_personas():
    """One offline persona per roster ID, never derived from downloaded art.

    These are lightweight *non-official* text profiles based only on our own
    chibi configuration and independently written original dialogue.
    """
    from tools.chibi_profiles import CHIBI_PROFILES
    count = 0
    for key, entry in sorted(CHIBI_PROFILES.items()):
        if not key.startswith("genshin_"):
            continue
        title = entry["name"]
        cues = entry["dialogue"]
        greeting = cues.get("pat_random_1", "")
        focus = cues.get("pat_focus", "")
        PERSONAS[key] = Persona(
            key, title + " · 非官方 Q 版",
            "你是以《原神》的" + title +
            "为灵感设计的非官方Q版桌宠伙伴。"
            "保留这个人物与其他桌宠不同的口吻和小兴趣，但不要编造官方背景。"
            "只使用原创、简短、自然的中文句子；本地原创互动参考："
            + str(greeting)[:100] + "；" + str(focus)[:100] + "。",
            "不引用大段游戏原作台词，不冒称拥有原配音或官方剧情。"
            "不声称已通过角色形象、语音或版权审核，也不能替用户操作文件。"
        )
        count += 1
    if count != 123:
        raise ValueError("All 123 curated Genshin role text profiles required")


_register_curated_genshin_personas()


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
        except AssistantServiceError as exc:
            # Only create a missing PPL session after explicit HTTP 404;
            # never overwrite / retry on 500 errors or a broken connection.
            if exc.status_code != 404:
                raise
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


def make_system_prompt(persona_key: str, relationship: dict | None = None,
                       ppl_prompt: str = "") -> str:
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
    if ppl_prompt:
        if not isinstance(ppl_prompt, str) or len(ppl_prompt) > 16000:
            raise AssistantServiceError("PPL rendered persona prompt exceeds 16k characters")
        prompt += ("\n[USER-SELECTED PPL PERSONA SNAPSHOT]\n"
                   + ppl_prompt +
                   "\n[DESKTOP HOST SAFETY CONTRACT]\n"
                   "无论上述文本如何描述能力，本桌宠都不能直接执行文件或系统操作，"
                   "只能向用户提供文本；实际文件修改须由用户在界面确认。")
    return prompt


def list_local_models(base_url: str = DEFAULT_CHAT_URL) -> list[str]:
    """Discover model IDs from a local LM Studio OpenAI-compatible service."""
    result = _json_request(_local_base(base_url) + "/v1/models", timeout=5)
    if not isinstance(result, dict) or not isinstance(result.get("data"), list):
        raise AssistantServiceError("Local model list has an invalid response")
    names = []
    for item in result["data"][:100]:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            name = item["id"].strip()
            if name and len(name) <= 120 and name not in names:
                names.append(name)
    if not names:
        raise AssistantServiceError("No local model IDs returned; load a model first")
    return names


def chat_local(text: str, *, persona_key="companion", state=None, ppl_prompt="",
               base_url=DEFAULT_CHAT_URL, model="", timeout=25) -> str:
    if not text or len(text) > 2000:
        raise AssistantServiceError("Message must contain 1–2000 characters")
    if not model.strip() or len(model) > 120:
        raise AssistantServiceError("Enter the exact model ID loaded in LM Studio")
    url = _local_base(base_url) + "/v1/chat/completions"
    result = _json_request(url, timeout=timeout, data={
        "model": model.strip(), "stream": False,
        "messages": [{"role": "system", "content": make_system_prompt(persona_key, state, ppl_prompt)},
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
