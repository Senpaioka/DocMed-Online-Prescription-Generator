import click
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db

load_dotenv()

flask_app = create_app()


@flask_app.cli.command("createsuperuser")
@click.option("--username", prompt=True, help="Superuser username")
@click.option("--email", prompt=True, help="Superuser email")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Superuser password")
@click.option("--gender", prompt=True, type=click.Choice(["Male", "Female", "Other"], case_sensitive=False), default="Male", help="Gender")
def createsuperuser(username, email, password, gender):
    """Create a new superuser/admin account."""
    from app.modules.account.models import RegistrationModel

    with flask_app.app_context():
        # Check if username or email already exists
        existing_user = RegistrationModel.query.filter(
            (RegistrationModel.username == username) | (RegistrationModel.email == email)
        ).first()

        if existing_user:
            if existing_user.username == username:
                click.echo(click.style(f"Error: User with username '{username}' already exists.", fg="red"))
            else:
                click.echo(click.style(f"Error: User with email '{email}' already exists.", fg="red"))
            return

        superuser = RegistrationModel(
            username=username,
            email=email,
            password=generate_password_hash(password),
            gender=gender,
            role="admin",
            is_admin=True,
            is_active=True,
            is_verified=True,
            verified_doctor=True,
        )

        db.session.add(superuser)
        db.session.commit()
        click.echo(click.style(f"Success: Superuser '{username}' created successfully!", fg="green"))


if __name__ == '__main__':
    flask_app.run()


