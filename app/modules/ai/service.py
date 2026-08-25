"""Gemini AI Service integrating the Google GenAI SDK with role-based tools and history."""

import logging
from typing import Dict, Any, List, Optional
from flask import current_app, session
from flask_login import current_user
from decouple import config as decouple_config
from google import genai
from google.genai import types

from app.modules.ai.prompts import get_system_prompt_for_user
from app.modules.ai.tools import get_tools_for_user

logger = logging.getLogger(__name__)


def get_genai_client() -> Optional[genai.Client]:
    """Create and return a Gemini API client instance."""
    api_key = current_app.config.get('GEMINI_API_KEY') or decouple_config('GEMINI_API_KEY', default='')
    if not api_key:
        logger.error("GEMINI_API_KEY is not set.")
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"Error initializing GenAI Client: {e}", exc_info=True)
        return None


def get_user_session_history(user_id: int) -> List[Dict[str, str]]:
    """Retrieve serialized chat history from session for the current user."""
    history_key = f"ai_chat_history_{user_id}"
    return session.get(history_key, [])


def save_user_session_history(user_id: int, history: List[Dict[str, str]]) -> None:
    """Save serialized chat history to session for current user, limiting to latest 20 turns."""
    history_key = f"ai_chat_history_{user_id}"
    # Keep last 20 messages to prevent session bloat
    session[history_key] = history[-20:]
    session.modified = True


def clear_user_session_history(user_id: int) -> None:
    """Clear chat history for current user."""
    history_key = f"ai_chat_history_{user_id}"
    session.pop(history_key, None)
    session.modified = True


def generate_ai_response(user_message: str, user=None) -> Dict[str, Any]:
    """Process a user message and return the Gemini AI response with tools execution.
    
    Args:
        user_message: The prompt/message from the user.
        user: The logged-in user instance (defaults to current_user).
        
    Returns:
        Dictionary containing status, reply text, and timestamp.
    """
    if user is None:
        user = current_user

    if not user or not getattr(user, 'is_authenticated', False):
        return {
            "status": "error",
            "message": "Authentication required to interact with DocMed AI."
        }

    client = get_genai_client()
    if not client:
        return {
            "status": "error",
            "message": "Gemini API key is not configured or failed to initialize. Please check server settings."
        }

    model_name = current_app.config.get('GEMINI_MODEL') or decouple_config('GEMINI_MODEL', default='gemini-3.6-flash')
    system_instruction = get_system_prompt_for_user(user)
    tools = get_tools_for_user(user)

    # Convert session history into GenAI types.Content objects
    raw_history = get_user_session_history(user.uid)
    genai_history = []
    for item in raw_history:
        role = item.get("role", "user")
        text = item.get("text", "")
        if text:
            # Map role
            genai_role = "model" if role in ("model", "assistant") else "user"
            genai_history.append(
                types.Content(
                    role=genai_role,
                    parts=[types.Part.from_text(text=text)]
                )
            )

    try:
        config_obj = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools if tools else None,
            temperature=0.4
        )

        chat = client.chats.create(
            model=model_name,
            history=genai_history,
            config=config_obj
        )

        response = chat.send_message(user_message)
        response_text = response.text or "I processed your request, but have no additional text to display."

        # Update and persist session history
        raw_history.append({"role": "user", "text": user_message})
        raw_history.append({"role": "model", "text": response_text})
        save_user_session_history(user.uid, raw_history)

        return {
            "status": "success",
            "reply": response_text,
            "role": getattr(user, 'role', 'patient')
        }

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Gemini API chat error: {err_msg}", exc_info=True)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            friendly = "DocMed AI is currently experiencing high demand or rate limits on the free tier. Please wait a few seconds and try again."
        elif "API_KEY" in err_msg or "403" in err_msg:
            friendly = "AI service authentication error. Please verify the Gemini API key configuration."
        else:
            friendly = f"DocMed AI encountered an unexpected issue: {err_msg}"

        return {
            "status": "error",
            "message": friendly
        }
