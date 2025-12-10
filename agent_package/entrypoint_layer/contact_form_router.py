import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, jsonify, render_template, request
from pydantic import ValidationError

from agent_package import config
from agent_package.domain_layer.conntact_form_domain import ContactFormEmail

logger = logging.getLogger(__name__)

contact_form_router = Blueprint("contact_form_router", __name__)


@contact_form_router.route("/contact")
def contact_page():
    """Render the contact form page."""
    return render_template("contact.html")


@contact_form_router.route("/api/send-contact-email", methods=["POST"])
def send_contact_email():
    """Handle contact form submission and send email."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Use Pydantic model to validate the data
        try:
            contact_data = ContactFormEmail(**data)
        except ValidationError as e:
            # Extract user-friendly error messages from Pydantic
            errors = []
            for error in e.errors():
                field = error.get("loc", ["unknown"])[0]
                msg = error.get("msg", "Invalid value")
                errors.append(f"{field}: {msg}")
            return jsonify({"error": "; ".join(errors)}), 400

        # Email configuration
        port = config.SMTP_PORT
        smtp_server = config.SMTP_SERVER
        sender_email = config.SENDER_EMAIL
        receiver_email = config.RECIPIENT_EMAIL
        password = config.SENDER_APP_PASSWORD

        # Check if email config is available
        if not sender_email or not password:
            logger.error("SMTP credentials not configured")
            return (
                jsonify(
                    {"error": "Email service not configured. Please try again later."}
                ),
                503,
            )

        # Create proper email with headers
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = f"[Oqtopus Contact] {contact_data.subject}"
        msg["Reply-To"] = contact_data.email

        email_body = f"""
You have received a new message via the Oqtopus contact form:

From: {contact_data.name}
Email: {contact_data.email}
Subject: {contact_data.subject}

Message:
{contact_data.message}
        """

        msg.attach(MIMEText(email_body, "plain"))

        # Send email
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP(smtp_server, port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(sender_email, password)
                server.sendmail(sender_email, receiver_email, msg.as_string())

            logger.info(f"Contact email sent from {contact_data.email}")
            return jsonify({"message": "Email sent successfully!"})

        except smtplib.SMTPAuthenticationError:
            logger.error(
                f"SMTP Authentication Error for {sender_email} on {smtp_server}:{port}"
            )
            return (
                jsonify(
                    {
                        "error": "Email service authentication failed. Please try again later."
                    }
                ),
                500,
            )

        except smtplib.SMTPConnectError:
            logger.error(f"SMTP Connection Error to {smtp_server}:{port}")
            return (
                jsonify(
                    {
                        "error": "Failed to connect to email server. Please try again later."
                    }
                ),
                500,
            )

    except Exception as e:
        logger.error(f"An unexpected error occurred while sending email: {e}")
        return (
            jsonify({"error": "An unexpected error occurred. Please try again later."}),
            500,
        )
