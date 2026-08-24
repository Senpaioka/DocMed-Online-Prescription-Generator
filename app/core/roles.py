from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user


class UserRole:
    PATIENT = 'patient'
    DOCTOR = 'doctor'
    ADMIN = 'admin'

    CHOICES = [
        (PATIENT, 'Patient'),
        (DOCTOR, 'Doctor'),
        (ADMIN, 'Admin')
    ]

    ALL = [PATIENT, DOCTOR, ADMIN]


def role_required(*allowed_roles):
    """
    Decorator to restrict route access to users with specified role(s).
    Admins always bypass role requirements unless explicitly restricted.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('accounts.login_page', next=request.url))

            user_role = getattr(current_user, 'role', UserRole.PATIENT)
            is_admin = getattr(current_user, 'is_admin', False) or user_role == UserRole.ADMIN

            # Admin or role match
            if is_admin or user_role in allowed_roles:
                return func(*args, **kwargs)

            flash(f'Access denied. This page is restricted to: {", ".join(allowed_roles)}.', 'error')
            if current_user.is_authenticated:
                return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid))
            return redirect(url_for('home.home_page'))

        return wrapper
    return decorator


def doctor_required(func):
    """Allows verified doctors and admins only."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('accounts.login_page', next=request.url))

        user_role = getattr(current_user, 'role', UserRole.PATIENT)
        is_admin = getattr(current_user, 'is_admin', False) or user_role == UserRole.ADMIN

        # Admins always bypass
        if is_admin:
            return func(*args, **kwargs)

        if user_role == UserRole.DOCTOR:
            # Check if doctor is verified by admin
            if getattr(current_user, 'verified_doctor', False):
                return func(*args, **kwargs)
            else:
                flash('Your doctor account is pending admin verification. Clinical services will be unlocked once approved.', 'error')
                return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid))

        flash('Access denied. This service is restricted to verified doctors.', 'error')
        return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid))

    return wrapper


def admin_required(func):
    """Allows admins only."""
    return role_required(UserRole.ADMIN)(func)


def patient_required(func):
    """Allows patients and admins."""
    return role_required(UserRole.PATIENT, UserRole.ADMIN)(func)
