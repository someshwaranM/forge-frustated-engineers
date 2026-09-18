"""
Vigil — Phase 9: Multi-Turn AI Chat Agent (backend/agents/chat_agent.py)

Orchestrates multi-turn conversational compliance investigation with tool use:
- Reuses Bedrock-primary / Gemini-fallback architecture.
- Strictly uses Gemini 3.6 Flash ('gemini-3.6-flash') as specified.
- Maintains in-memory conversation history per session_id.
- Strictly read-only: no case creation, no notifications, no case_service mutation.
- Loop limits: max 8 tool calls per turn, max 5 model/tool iterations per turn.
- Constructs grounded_results directly from tool outputs, not model free-text parsing.
- Enforces re-verification: previous assistant answers are context, never evidence.
"""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
import google.generativeai as genai

from backend.agents.chat_tools import (
    ALL_TOOLS,
    BEDROCK_TOOL_CONFIG,
    TOOL_REGISTRY,
    execute_tool,
    extract_grounded_ids_from_tool_output,
)

logger = logging.getLogger(__name__)

# Ensure .env is loaded
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

MAX_TOOL_CALLS_PER_TURN = 8
MAX_ITERATIONS_PER_TURN = 5
CONTROLLED_LIMIT_EXCEEDED_MSG = "Investigation exceeded the maximum tool-call limit."

SYSTEM_INSTRUCTION = """You are Vigil AI, an expert investigative compliance analyst for Indian wealth management and mutual fund advisory.
Your role is to assist compliance officers in investigating Relationship Manager (RM) calls, identifying potential regulatory violations under SEBI and AMFI regulations, inspecting customer profiles and transactions, and reviewing RM violation histories.

CRITICAL DIRECTIVES:
1. STRICT READ-ONLY: You are strictly an investigative assistant. You cannot create compliance cases or send notifications.
2. GROUNDING REQUIREMENT: Ground every factual assertion, finding, and regulatory clause in the outputs returned by your tools.
3. NEVER GUESS REGULATIONS: Never answer from general background knowledge about SEBI or AMFI rules without calling `search_regulations` first.
4. RE-VERIFY IN FOLLOW-UPS: Previous assistant responses provide conversational context only, NEVER authoritative evidence. If the user asks a follow-up question regarding regulations, findings, or calls, ALWAYS call the appropriate tool again to re-verify current facts.
5. REPORT COUNTS & BOUNDS: When presenting search results (calls, transactions, regulations), mention the total matching count and bound (e.g. "Found 2 matching calls" or "Showing 10 of 42 calls").
6. STRUCTURED FINDINGS: Cite specific Call IDs (e.g., CALL_RM001_CUST001_20260310_1030), Finding IDs (e.g., FND-2026-A56EDE), and Regulation Chunk IDs / Citation Labels accurately from the tool data.
"""


class ChatSessionState:
    """Maintains in-memory state and conversation history for a chat session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = time.time()
        self.updated_at = time.time()
        # Message history format: list of dicts: {"role": "user"|"assistant", "content": str}
        self.messages: List[Dict[str, Any]] = []
        # Gemini chat session instance
        self.gemini_chat: Optional[Any] = None


class ChatAgent:
    """
    Multi-turn conversation engine supporting tool calling, hard limits,
    dual-provider fallback (Bedrock -> Gemini 3.6 Flash), and output-grounded citations.
    """

    def __init__(self):
        self._sessions: Dict[str, ChatSessionState] = {}
        self.gemini_model_id = os.getenv("GEMINI_MODEL_ID", "gemini-3.6-flash")
        if self.gemini_model_id.startswith("models/"):
            self.gemini_model_id = self.gemini_model_id[len("models/"):]
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

    def get_or_create_session(self, session_id: str) -> ChatSessionState:
        """Retrieve existing session or instantiate a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ChatSessionState(session_id)
        session = self._sessions[session_id]
        session.updated_at = time.time()
        return session

    def reset_session(self, session_id: str) -> None:
        """Clear session history."""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def chat(
        self,
        session_id: str,
        user_message: str,
        force_provider: Optional[str] = None,
        max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
        max_iterations: int = MAX_ITERATIONS_PER_TURN,
    ) -> Dict[str, Any]:
        """
        Execute a single user turn in a multi-turn conversation.

        Returns:
            Dict with:
                - response_text: str
                - grounded_results: List[Dict[str, str]]
                - tool_calls_made: List[str]
                - provider_used: str ('bedrock' or 'gemini')
        """
        session = self.get_or_create_session(session_id)

        # 1. Try AWS Bedrock Converse API if not forced to Gemini
        if force_provider != "gemini":
            try:
                bedrock_resp = self._chat_bedrock(
                    session=session,
                    user_message=user_message,
                    max_tool_calls=max_tool_calls,
                    max_iterations=max_iterations,
                )
                return bedrock_resp
            except Exception as exc:
                logger.info(f"Bedrock primary chat unavailable or unconfigured ({exc}). Falling back to Gemini 3.6 Flash...")

        # 2. Fall back to Gemini 3.6 Flash
        gemini_resp = self._chat_gemini(
            session=session,
            user_message=user_message,
            max_tool_calls=max_tool_calls,
            max_iterations=max_iterations,
        )
        return gemini_resp

    # -----------------------------------------------------------------------
    # AWS Bedrock Multi-Turn Tool Loop
    # -----------------------------------------------------------------------

    def _chat_bedrock(
        self,
        session: ChatSessionState,
        user_message: str,
        max_tool_calls: int,
        max_iterations: int,
    ) -> Dict[str, Any]:
        """Execute multi-turn tool-calling loop using AWS Bedrock Converse API."""
        aws_access_key = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip().strip("'\"")
        aws_secret_key = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip().strip("'\"")
        aws_region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-west-2").strip().strip("'\"")
        aws_session_token = (os.getenv("AWS_SESSION_TOKEN") or "").strip().strip("'\"")
        model_id = (os.getenv("AWS_BEDROCK_MODEL_ID") or "").strip().strip("'\"")

        if not aws_access_key or "<REPLACE_ME>" in (aws_access_key, aws_secret_key, aws_region, model_id):
            raise ValueError("AWS Bedrock credentials/model_id are unconfigured or placeholder")

        client_kwargs = {
            "service_name": "bedrock-runtime",
            "region_name": aws_region,
            "aws_access_key_id": aws_access_key,
            "aws_secret_access_key": aws_secret_key,
        }
        if aws_session_token:
            client_kwargs["aws_session_token"] = aws_session_token
        client = boto3.client(**client_kwargs)

        # Build Converse message history
        # Convert internal session history to Bedrock Converse format
        converse_messages = []
        for msg in session.messages:
            converse_messages.append({
                "role": msg["role"],
                "content": [{"text": msg["content"]}],
            })

        # Append current user message
        converse_messages.append({
            "role": "user",
            "content": [{"text": user_message}],
        })

        system_prompts = [{"text": SYSTEM_INSTRUCTION}]
        tool_config = BEDROCK_TOOL_CONFIG

        tool_calls_made: List[str] = []
        tool_outputs_collected: List[Tuple[str, Any]] = []
        total_tool_calls = 0
        iterations = 0
        final_text = ""

        while iterations < max_iterations:
            iterations += 1

            response = client.converse(
                modelId=model_id,
                messages=converse_messages,
                system=system_prompts,
                toolConfig=tool_config,
                inferenceConfig={"temperature": 0.0, "maxTokens": 2048},
            )

            output_msg = response.get("output", {}).get("message", {})
            content_blocks = output_msg.get("content", [])
            converse_messages.append(output_msg)

            # Check for tool use requests
            tool_requests = [
                b["toolUse"] for b in content_blocks if "toolUse" in b
            ]

            if not tool_requests:
                # Model finished responding with text
                text_blocks = [b["text"] for b in content_blocks if "text" in b]
                final_text = "\n".join(text_blocks).strip()
                break

            # Handle tool calls
            tool_result_blocks = []
            for req in tool_requests:
                if total_tool_calls >= max_tool_calls:
                    logger.warning(f"Session {session.session_id} exceeded max tool calls limit ({max_tool_calls})")
                    final_text = CONTROLLED_LIMIT_EXCEEDED_MSG
                    break

                fn_name = req.get("name")
                fn_args = req.get("input", {})
                tool_use_id = req.get("toolUseId")

                tool_calls_made.append(fn_name)
                total_tool_calls += 1

                tool_result = execute_tool(fn_name, fn_args)
                tool_outputs_collected.append((fn_name, tool_result))

                tool_result_blocks.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": tool_result}],
                        "status": "success",
                    }
                })

            if final_text == CONTROLLED_LIMIT_EXCEEDED_MSG:
                break

            # Send tool outputs back as user role in Converse API
            converse_messages.append({
                "role": "user",
                "content": tool_result_blocks,
            })

        if iterations >= max_iterations and not final_text:
            final_text = CONTROLLED_LIMIT_EXCEEDED_MSG

        grounded_results = self._extract_grounded_results(tool_outputs_collected)

        # Update in-memory session messages
        session.messages.append({"role": "user", "content": user_message})
        session.messages.append({"role": "assistant", "content": final_text})

        return {
            "response_text": final_text,
            "grounded_results": grounded_results,
            "tool_calls_made": tool_calls_made,
            "provider_used": "bedrock",
        }

    # -----------------------------------------------------------------------
    # Google Gemini 3.6 Flash Multi-Turn Tool Loop
    # -----------------------------------------------------------------------

    def _chat_gemini(
        self,
        session: ChatSessionState,
        user_message: str,
        max_tool_calls: int,
        max_iterations: int,
    ) -> Dict[str, Any]:
        """Execute multi-turn tool-calling loop using Google Gemini 3.6 Flash."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or .env")

        genai.configure(api_key=self.gemini_api_key)

        # Initialize Gemini ChatSession if not already created
        if session.gemini_chat is None:
            model = genai.GenerativeModel(
                model_name=self.gemini_model_id,
                system_instruction=SYSTEM_INSTRUCTION,
                tools=ALL_TOOLS,
                generation_config={
                    "temperature": 0.0,
                },
            )
            session.gemini_chat = model.start_chat(enable_automatic_function_calling=False)

        chat = session.gemini_chat

        tool_calls_made: List[str] = []
        tool_outputs_collected: List[Tuple[str, Any]] = []
        total_tool_calls = 0
        iterations = 0
        final_text = ""

        # First message for this user turn
        current_input: Any = user_message

        while iterations < max_iterations:
            iterations += 1

            # Call Gemini with retry/backoff on rate limits
            response = self._invoke_gemini_with_retry(chat, current_input)

            parts = response.parts
            fn_calls = [p.function_call for p in parts if p.function_call]

            if not fn_calls:
                # No function calls, turn complete
                final_text = response.text.strip() if hasattr(response, "text") and response.text else ""
                break

            # Process function calls
            function_response_parts = []
            limit_hit = False

            for call in fn_calls:
                if total_tool_calls >= max_tool_calls:
                    logger.warning(f"Session {session.session_id} exceeded max tool calls limit ({max_tool_calls})")
                    final_text = CONTROLLED_LIMIT_EXCEEDED_MSG
                    limit_hit = True
                    break

                fn_name = call.name
                fn_args = dict(call.args) if call.args else {}

                tool_calls_made.append(fn_name)
                total_tool_calls += 1

                tool_result = execute_tool(fn_name, fn_args)
                tool_outputs_collected.append((fn_name, tool_result))

                function_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fn_name,
                            response={"result": tool_result},
                        )
                    )
                )

            if limit_hit:
                break

            current_input = genai.protos.Content(parts=function_response_parts)

        if iterations >= max_iterations and not final_text:
            final_text = CONTROLLED_LIMIT_EXCEEDED_MSG

        grounded_results = self._extract_grounded_results(tool_outputs_collected)

        # Update session messages
        session.messages.append({"role": "user", "content": user_message})
        session.messages.append({"role": "assistant", "content": final_text})

        return {
            "response_text": final_text,
            "grounded_results": grounded_results,
            "tool_calls_made": tool_calls_made,
            "provider_used": "gemini",
        }

    def _invoke_gemini_with_retry(self, chat: Any, content: Any, max_retries: int = 6) -> Any:
        """Call Gemini ChatSession with automated exponential backoff on 429 quota errors."""
        for attempt in range(max_retries):
            try:
                return chat.send_message(content)
            except Exception as exc:
                err_str = str(exc)
                if ("429" in err_str or "quota" in err_str.lower() or "exhausted" in err_str.lower()) and attempt < max_retries - 1:
                    delay = 20.0
                    sec_match = re.search(r"seconds:\s*(\d+)", err_str)
                    delay_match = re.search(r"retry in ([\d\.]+)s", err_str, re.IGNORECASE)
                    if sec_match:
                        delay = float(sec_match.group(1)) + 3.0
                    elif delay_match:
                        delay = float(delay_match.group(1)) + 3.0
                    logger.warning(f"Gemini rate limit (429). Sleeping for {delay:.1f}s before retry (attempt {attempt+1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    raise

    # -----------------------------------------------------------------------
    # Grounded Results Builder
    # -----------------------------------------------------------------------

    def _extract_grounded_results(self, tool_outputs: List[Tuple[str, Any]]) -> List[Dict[str, str]]:
        """
        Builds grounded_results strictly from successful tool outputs during the turn.
        Deduplicates by (type, id).
        """
        grounded: List[Dict[str, str]] = []
        seen_keys: Set[Tuple[str, str]] = set()

        for tool_name, output in tool_outputs:
            items = extract_grounded_ids_from_tool_output(tool_name, output)
            for it in items:
                key = (it["type"], it["id"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    grounded.append(it)

        return grounded


# Singleton instance
_chat_agent_instance: Optional[ChatAgent] = None


def get_chat_agent() -> ChatAgent:
    """Access singleton ChatAgent instance."""
    global _chat_agent_instance
    if _chat_agent_instance is None:
        _chat_agent_instance = ChatAgent()
    return _chat_agent_instance
