"""Gemini AI Service integrating the Google GenAI SDK with multi-model fallback,
key rotation, role-based tools, and session history.
"""

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


def get_available_api_keys() -> List[str]:
    """Retrieve all available Gemini API keys from configuration for rotation."""
    keys_str = current_app.config.get('GEMINI_API_KEYS') or decouple_config('GEMINI_API_KEYS', default='')
    single_key = current_app.config.get('GEMINI_API_KEY') or decouple_config('GEMINI_API_KEY', default='')

    keys = []
    if keys_str:
        keys.extend([k.strip() for k in keys_str.split(',') if k.strip()])
    if single_key and single_key.strip() not in keys:
        keys.append(single_key.strip())

    return keys


def get_candidate_models() -> List[str]:
    """Retrieve prioritized list of Gemini models for automatic fallback."""
    primary = current_app.config.get('GEMINI_MODEL') or decouple_config('GEMINI_MODEL', default='gemini-3.6-flash')
    fallback_str = current_app.config.get('GEMINI_FALLBACK_MODELS') or decouple_config(
        'GEMINI_FALLBACK_MODELS',
        default='gemini-3.6-flash,gemini-3.7-flash,gemini-flash-latest,gemini-2.5-flash-lite'
    )

    models = [primary.strip()]
    if fallback_str:
        for m in fallback_str.split(','):
            m_clean = m.strip()
            if m_clean and m_clean not in models:
                models.append(m_clean)

    return models


def get_user_session_history(user_id: int) -> List[Dict[str, str]]:
    """Retrieve serialized chat history from session for the current user."""
    history_key = f"ai_chat_history_{user_id}"
    return session.get(history_key, [])


def save_user_session_history(user_id: int, history: List[Dict[str, str]]) -> None:
    """Save serialized chat history to session for current user, limiting to latest 20 turns."""
    history_key = f"ai_chat_history_{user_id}"
    session[history_key] = history[-20:]
    session.modified = True


def clear_user_session_history(user_id: int) -> None:
    """Clear chat history for current user."""
    history_key = f"ai_chat_history_{user_id}"
    session.pop(history_key, None)
    session.modified = True


def generate_ai_response(user_message: str, user=None) -> Dict[str, Any]:
    """Process a user message and return the Gemini AI response with automatic
    multi-model fallback and key rotation to bypass rate limits.
    
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

    api_keys = get_available_api_keys()
    if not api_keys:
        return {
            "status": "error",
            "message": "Gemini API key is not configured. Please add GEMINI_API_KEY to .env file."
        }

    candidate_models = get_candidate_models()
    system_instruction = get_system_prompt_for_user(user)
    tools = get_tools_for_user(user)

    # Convert session history into GenAI types.Content objects
    raw_history = get_user_session_history(user.uid)
    genai_history = []
    for item in raw_history:
        role = item.get("role", "user")
        text = item.get("text", "")
        if text:
            genai_role = "model" if role in ("model", "assistant") else "user"
            genai_history.append(
                types.Content(
                    role=genai_role,
                    parts=[types.Part.from_text(text=text)]
                )
            )

    last_error = ""

    # Attempt execution across API keys and fallback models
    for key in api_keys:
        try:
            client = genai.Client(api_key=key)
        except Exception as client_err:
            logger.warning(f"Failed to create client for API key ending in ...{key[-4:]}: {client_err}")
            continue

        for model_name in candidate_models:
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
                    "model_used": model_name,
                    "role": getattr(user, 'role', 'patient')
                }

            except Exception as e:
                err_msg = str(e)
                last_error = err_msg
                logger.warning(f"Attempt with model '{model_name}' on key ...{key[-4:]} failed: {err_msg}")
                # Seamlessly continue to the next model or API key
                continue

    # If all candidate models and keys failed:
    if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
        friendly = "DocMed AI is currently experiencing high demand across all free-tier models. Please wait a few moments and try again, or add secondary API keys to .env."
    elif "API_KEY" in last_error or "403" in last_error:
        friendly = "AI service authentication error. Please verify the Gemini API key in your .env configuration."
    else:
        friendly = f"DocMed AI encountered an unexpected issue: {last_error or 'Service temporarily unavailable'}"

    return {
        "status": "error",
        "message": friendly
    }
