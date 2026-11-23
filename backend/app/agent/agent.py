"""Qorgau assistant: a goal-based agent with explicit states (course week 1).

Cycle:  OBSERVE -> CLASSIFY_INPUT -> SELECT_TOOL -> ACT -> HANDLE_RESULT
        -> (retry/fallback -> ACT) -> EXPLAIN -> DONE | NEED_INPUT | FAILED

* Perception: the agent observes the user's text and/or an attached check result.
* Decision: a fixed rule table maps the input type and tool availability to an
  action; every decision is recorded in the trace with its reason.
* Action: tools are Python callables with a fixed allow-list (no shell, no
  arbitrary HTTP, no history deletion). Nothing in user text, web pages or
  files can add tools or change the rule table: such content is only ever
  parsed for URLs (data), never interpreted as instructions.
* Explanation: template blocks built from the real tool result (always), plus
  an optional LLM paraphrase of those same facts when a server key is set.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable

from ..deepfake.media import MediaError
from ..url_analysis.data_lists import SOCIAL_MEDIA_HOSTS
from ..url_analysis.normalize import UrlValidationError, parse_url
from .explain import LlmExplainer, template_blocks


class AgentState(str, Enum):
    OBSERVE = "observe"
    CLASSIFY_INPUT = "classify_input"
    SELECT_TOOL = "select_tool"
    ACT = "act"
    HANDLE_RESULT = "handle_result"
    EXPLAIN = "explain"
    DONE = "done"
    NEED_INPUT = "need_input"
    FAILED = "failed"


# Which states may follow which (enforced; protects against logic errors).
TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.OBSERVE: {AgentState.CLASSIFY_INPUT},
    AgentState.CLASSIFY_INPUT: {AgentState.SELECT_TOOL, AgentState.NEED_INPUT},
    AgentState.SELECT_TOOL: {AgentState.ACT, AgentState.EXPLAIN, AgentState.NEED_INPUT, AgentState.FAILED},
    AgentState.ACT: {AgentState.HANDLE_RESULT},
    AgentState.HANDLE_RESULT: {AgentState.ACT, AgentState.EXPLAIN, AgentState.NEED_INPUT, AgentState.FAILED},
    AgentState.EXPLAIN: {AgentState.DONE},
}

MEDIA_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm", ".m4v")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"'«»]+|\b(?:[a-z0-9\-а-яё]+\.)+(?:[a-z]{2,24}|рф|қаз)(?:/[^\s<>\"'«»]*)?",
                    re.IGNORECASE)
TRAILING = ".,;:!?)]}>'\"»"
MAX_URLS = 3
RESULT_KINDS = {"url", "media"}


@dataclass
class TraceStep:
    step: int
    state: str
    action: str
    detail: dict[str, Any] = field(default_factory=dict)
    ms: int = 0


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] | None = None
    error_code: str | None = None
    retryable: bool = False


@dataclass
class Tool:
    name: str
    description: str
    run: Callable[..., dict[str, Any]]
    availability: Callable[[], tuple[bool, str | None]]


def extract_urls(text: str) -> list[str]:
    found: list[str] = []
    for m in URL_RE.finditer(text or ""):
        if m.start() > 0 and text[m.start() - 1] in "@.-_":
            continue  # domain part of an e-mail address (user@mail.kz) or a fragment
        u = m.group(0).rstrip(TRAILING)
        if "@" in u.split("/")[0] and not u.lower().startswith(("http://", "https://")):
            continue  # looks like an e-mail address, not a link
        if u and u not in found:
            found.append(u)
    return found


def classify(text: str, attached: dict | None) -> tuple[str, dict[str, Any]]:
    """Return (input_type, details). Pure function: unit-tested."""
    if attached is not None:
        if isinstance(attached, dict) and attached.get("kind") in RESULT_KINDS and "category" in attached:
            return "check_result", {"result_kind": attached["kind"]}
        return "invalid_result", {}
    text = (text or "").strip()
    if not text:
        return "empty", {}
    urls = extract_urls(text)
    if not urls:
        return "text_without_url", {"length": len(text)}
    first = urls[0]
    try:
        p = parse_url(first)
    except UrlValidationError as exc:
        return "invalid_url", {"code": exc.code}
    host = p.host_no_www
    kind = "url"
    if any(host == h or host.endswith("." + h) for h in SOCIAL_MEDIA_HOSTS):
        kind = "social_media_url"
    elif p.path.lower().endswith(MEDIA_EXTENSIONS):
        kind = "media_url"
    return kind, {"urls": urls[:MAX_URLS], "url_count": len(urls), "host": p.host_unicode}


class QorgauAgent:
    def __init__(self, url_service, media_service, explainer: LlmExplainer | None = None):
        self.url_service = url_service
        self.media_service = media_service
        self.explainer = explainer
        self.tools: dict[str, Tool] = {
            "url_check": Tool(
                "url_check", "Phishing risk analysis of a link (rules + ML + safe redirect check)",
                run=lambda url, network=True: self.url_service.check(url, network=network),
                availability=lambda: (True, None)),
            "media_url_check": Tool(
                "media_url_check", "Deepfake analysis of a direct image/video link",
                run=lambda url: self.media_service.analyse_url(url),
                availability=lambda: (self.media_service.model_connected,
                                      None if self.media_service.model_connected else "model_not_connected")),
            "result_reader": Tool(
                "result_reader", "Reads a check result the user attached (no external calls)",
                run=lambda result: result, availability=lambda: (True, None)),
        }

    # ------------------------------------------------------------------
    def run(self, text: str = "", attached_result: dict | None = None, *, lang: str = "ru",
            allow_network: bool = True, use_llm: bool = False) -> dict[str, Any]:
        trace: list[TraceStep] = []
        state = AgentState.OBSERVE
        t_start = time.monotonic()
        notes: list[str] = []

        def go(new: AgentState, action: str, **detail: Any) -> None:
            nonlocal state
            if new is not state and new not in TRANSITIONS.get(state, set()):
                raise RuntimeError(f"illegal transition {state} -> {new}")
            state = new
            trace.append(TraceStep(len(trace) + 1, new.value, action, detail,
                                   int((time.monotonic() - t_start) * 1000)))

        trace.append(TraceStep(1, state.value, "observe_input", {
            "text_length": len(text or ""), "has_attached_result": attached_result is not None,
            "untrusted_content": True}))

        input_type, info = classify(text, attached_result)
        go(AgentState.CLASSIFY_INPUT, "classified", input_type=input_type,
           **{k: v for k, v in info.items() if k != "urls"}, urls_found=len(info.get("urls", [])))

        if input_type in ("empty", "text_without_url", "invalid_url", "invalid_result"):
            go(AgentState.NEED_INPUT, "ask_for_input", reason=input_type, **({"code": info["code"]} if "code" in info else {}))
            return self._finish(state, input_type, None, None, notes, trace, lang, use_llm,
                                actions=["paste_link", "check_media", "scan_qr"], reason=input_type)

        # ---------------- SELECT_TOOL ----------------
        if input_type == "check_result":
            tool_name, arg = "result_reader", {"result": attached_result}
        elif input_type == "media_url":
            ok, why = self.tools["media_url_check"].availability()
            if ok:
                tool_name, arg = "media_url_check", {"url": info["urls"][0]}
            else:
                notes.append("media_model_not_connected")
                tool_name, arg = "url_check", {"url": info["urls"][0], "network": allow_network}
                go(AgentState.SELECT_TOOL, "tool_unavailable_fallback", wanted="media_url_check", reason=why,
                   chosen="url_check")
        elif input_type == "social_media_url":
            notes.append("social_page_needs_upload")
            tool_name, arg = "url_check", {"url": info["urls"][0], "network": allow_network}
        else:
            tool_name, arg = "url_check", {"url": info["urls"][0], "network": allow_network}
        if info.get("url_count", 0) > 1:
            notes.append("multiple_urls_first_checked")
        if state is not AgentState.SELECT_TOOL:
            go(AgentState.SELECT_TOOL, "select_tool", tool=tool_name,
               reason={"check_result": "explain_attached_result", "media_url": "direct_media_link",
                       "social_media_url": "page_link_check_safety_only", "url": "link_check"}[input_type])

        # ---------------- ACT / HANDLE_RESULT loop ----------------
        result: ToolResult | None = None
        attempts = 0
        while True:
            attempts += 1
            go(AgentState.ACT, "call_tool", tool=tool_name, attempt=attempts,
               **({"network": arg.get("network")} if "network" in arg else {}))
            result = self._call(tool_name, arg)
            go(AgentState.HANDLE_RESULT, "tool_returned", ok=result.ok, error=result.error_code,
               category=(result.data or {}).get("category"))
            if result.ok:
                data = result.data or {}
                if tool_name == "url_check":
                    failed = [c for c in data.get("checks", []) if c["status"] == "failed"]
                    if failed:
                        notes.append("network_check_failed_partial")
                if data.get("category") == "insufficient":
                    notes.append("insufficient_data")
                break
            # error handling policy
            if tool_name == "media_url_check" and result.error_code in ("not_media_html", "social_page"):
                go(AgentState.NEED_INPUT, "ask_for_upload", reason=result.error_code)
                return self._finish(state, input_type, tool_name, result, notes, trace, lang, use_llm,
                                    actions=["upload_media", "check_link_safety"], reason=result.error_code)
            if tool_name == "url_check" and result.retryable and arg.get("network") and attempts == 1:
                notes.append("retried_without_network")
                arg = {**arg, "network": False}
                continue
            go(AgentState.FAILED, "give_up", error=result.error_code)
            return self._finish(state, input_type, tool_name, result, notes, trace, lang, use_llm,
                                actions=["try_again", "check_another"], reason=result.error_code)

        return self._finish(state, input_type, tool_name, result, notes, trace, lang, use_llm,
                            actions=["open_result", "save_result", "check_another"])

    # ------------------------------------------------------------------
    def _call(self, name: str, arg: dict[str, Any]) -> ToolResult:
        tool = self.tools[name]  # KeyError impossible: names come from the fixed table above
        try:
            return ToolResult(True, tool.run(**arg))
        except UrlValidationError as exc:
            return ToolResult(False, error_code=f"invalid_url:{exc.code}")
        except MediaError as exc:
            return ToolResult(False, error_code=exc.code, retryable=exc.code in ("timeout", "download_failed"))
        except TimeoutError:
            return ToolResult(False, error_code="timeout", retryable=True)
        except Exception as exc:  # tool crashed: never leak internals to the user
            return ToolResult(False, error_code=f"tool_error:{type(exc).__name__}", retryable=True)

    def _finish(self, state: AgentState, input_type: str, tool: str | None, result: ToolResult | None,
                notes: list[str], trace: list[TraceStep], lang: str, use_llm: bool,
                actions: list[str], reason: str | None = None) -> dict[str, Any]:
        final_state = state
        explanation: dict[str, Any] = {"source": "template", "blocks": [], "text": None}
        data = result.data if result and result.ok else None
        if state not in (AgentState.NEED_INPUT, AgentState.FAILED):
            blocks = template_blocks(data, notes)
            explanation["blocks"] = blocks
            llm_text = None
            if use_llm and self.explainer and self.explainer.enabled and data is not None:
                llm_text, llm_err = self.explainer.explain(data, lang)
                if llm_text:
                    explanation.update(source="llm+template", text=llm_text)
                else:
                    notes.append(f"llm_unavailable:{llm_err}")
            trace.append(TraceStep(len(trace) + 1, AgentState.EXPLAIN.value, "explain",
                                   {"blocks": len(blocks), "llm_used": bool(llm_text)}))
            trace.append(TraceStep(len(trace) + 1, AgentState.DONE.value, "done", {}))
            final_state = AgentState.DONE
        else:
            explanation["blocks"] = [{"type": "need_input" if state is AgentState.NEED_INPUT else "error",
                                      "reason": reason}]
        return {
            "state": final_state.value,
            "input_type": input_type,
            "tool_used": tool,
            "result": data,
            "error": None if not result or result.ok else result.error_code,
            "explanation": explanation,
            "actions": actions,
            "notes": notes,
            "trace": [asdict(t) for t in trace],
            "tools": [{"name": t.name, "available": t.availability()[0], "reason": t.availability()[1]}
                      for t in self.tools.values()],
        }
