from flask import render_template, request, jsonify
from app.extensions import db


def register_error_handlers(app):
    """Register custom error handlers for the Flask application."""

    @app.errorhandler(400)
    def bad_request(e):
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({
                "status": "error",
                "code": 400,
                "name": "Bad Request",
                "description": getattr(e, "description", "The browser (or proxy) sent a request that this server could not understand.")
            }), 400
        return render_template(
            "errors/error.html",
            error_code=400,
            error_title="Bad Request",
            error_message="The request could not be understood by the server. Please check the parameters or try again."
        ), 400

    @app.errorhandler(403)
    def forbidden(e):
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({
                "status": "error",
                "code": 403,
                "name": "Forbidden",
                "description": getattr(e, "description", "You do not have permission to access the requested resource.")
            }), 403
        return render_template(
            "errors/403.html",
            error_code=403,
            error_title="Access Forbidden",
            error_message="You don't have authorization or permission to view this medical resource."
        ), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({
                "status": "error",
                "code": 404,
                "name": "Not Found",
                "description": "The requested resource could not be found on the server."
            }), 404
        return render_template(
            "errors/404.html",
            error_code=404,
            error_title="Page Not Found",
            error_message="The page or medical record you are looking for might have been removed, had its name changed, or is temporarily unavailable."
        ), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        # Rollback any pending database transactions to prevent hanging locks
        try:
            db.session.rollback()
        except Exception:
            pass

        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({
                "status": "error",
                "code": 500,
                "name": "Internal Server Error",
                "description": "An unexpected error occurred on our servers. Our technical team has been alerted."
            }), 500
        return render_template(
            "errors/500.html",
            error_code=500,
            error_title="Server Error",
            error_message="Something went wrong on our end. Our technical team has been notified. Please try again shortly."
        ), 500

    @app.errorhandler(Exception)
    def handle_unexpected_exception(e):
        # Let HTTPExceptions be handled by their specific errorhandlers
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e

        # Rollback DB session on uncaught exceptions
        try:
            db.session.rollback()
        except Exception:
            pass

        app.logger.exception(f"Unhandled Exception: {e}")

        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({
                "status": "error",
                "code": 500,
                "name": "Internal Server Error",
                "description": "An unexpected system exception occurred."
            }), 500

        return render_template(
            "errors/500.html",
            error_code=500,
            error_title="System Exception",
            error_message="A critical server exception occurred while processing your request. Please try again later."
        ), 500
