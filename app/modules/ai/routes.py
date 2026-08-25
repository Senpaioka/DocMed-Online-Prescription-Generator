"""Flask Blueprint routes for DocMed AI Chatbot."""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.modules.ai.service import (
    generate_ai_response,
    get_user_session_history,
    clear_user_session_history
)

ai_bp = Blueprint(
    'ai',
    __name__,
    template_folder='templates',
    static_folder='static'
)


@ai_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """Handle chat messages from authenticated users."""
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()

    if not message:
        # Fallback to form data
        message = request.form.get('message', '').strip()

    if not message:
        return jsonify({
            'status': 'error',
            'message': 'Message cannot be empty.'
        }), 400

    result = generate_ai_response(message, user=current_user)
    if result.get('status') == 'error':
        return jsonify(result), 200

    return jsonify(result)


@ai_bp.route('/history', methods=['GET'])
@login_required
def history():
    """Retrieve message history for the current user session."""
    user_history = get_user_session_history(current_user.uid)
    return jsonify({
        'status': 'success',
        'history': user_history,
        'user_role': getattr(current_user, 'role', 'patient'),
        'user_name': current_user.username
    })


@ai_bp.route('/clear', methods=['POST'])
@login_required
def clear_chat():
    """Reset the chat history for the current user session."""
    clear_user_session_history(current_user.uid)
    return jsonify({
        'status': 'success',
        'message': 'Conversation cleared successfully.'
    })


@ai_bp.route('/quick-prompts', methods=['GET'])
@login_required
def quick_prompts():
    """Return role-tailored prompt suggestion chips."""
    role = getattr(current_user, 'role', 'patient')

    if getattr(current_user, 'is_admin_role', False) or getattr(current_user, 'is_admin', False) or role == 'admin':
        prompts = [
            {"label": "📊 System Overview", "prompt": "Give me a summary of total platform users, doctors, and appointments."},
            {"label": "🩺 Doctor Verifications", "prompt": "How many doctors are currently pending verification?"},
            {"label": "🔗 Admin Quick Links", "prompt": "Provide quick navigation links for administrative pages."}
        ]
    elif getattr(current_user, 'is_doctor', False) or role == 'doctor':
        prompts = [
            {"label": "📋 Check Appointments", "prompt": "Show my upcoming patient appointments."},
            {"label": "🔍 Search Prescriptions", "prompt": "Search my past prescriptions."},
            {"label": "💊 Drug Reference", "prompt": "Search medicine details and dosages for Omeprazole."},
            {"label": "📄 New Prescription", "prompt": "Where can I create a new digital prescription for a patient?"}
        ]
    else:
        # Patient
        prompts = [
            {"label": "🩺 Find Doctors", "prompt": "Help me find verified doctors in the platform."},
            {"label": "📅 My Appointments", "prompt": "What are my upcoming appointments and payment statuses?"},
            {"label": "📑 My Prescriptions", "prompt": "Show my past prescription history."},
            {"label": "ℹ️ How to Book", "prompt": "How do I book an appointment with a doctor?"}
        ]

    return jsonify({
        'status': 'success',
        'role': role,
        'prompts': prompts
    })
