import base64
import logging
import os

from flask import g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from agent_package import IS_PRODUCTION, config, create_app, db_connection
from agent_package.entrypoint_layer.auth_router import auth_router
from agent_package.entrypoint_layer.contact_form_router import contact_form_router
from agent_package.entrypoint_layer.info_router import info_router
from agent_package.entrypoint_layer.modify_router import modify_router
from agent_package.entrypoint_layer.search_router import search_router
from agent_package.system_layer.utils_auth import load_user_from_db

logger = logging.getLogger(__name__)

# Create app
app = create_app()


@app.before_request
def generate_nonce():
    """Generate a unique nonce for CSP."""
    g.nonce = base64.b64encode(os.urandom(16)).decode("utf-8")


@app.context_processor
def inject_globals():
    """Inject global variables into template context."""
    return dict(csp_nonce=getattr(g, "nonce", ""), is_production=IS_PRODUCTION)


# Initialize CSRF protection
csrf = CSRFProtect(app)
logger.info("CSRF protection enabled")


# Security Headers Middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    # Enable XSS filter in browsers
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Referrer policy - don't leak full URL to external sites
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions Policy - restrict browser features
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # Content Security Policy
    # Content Security Policy
    # Use nonce for scripts (must match nonce in templates)
    nonce = getattr(g, "nonce", "")
    csp_nonce = f"'nonce-{nonce}'" if nonce else ""

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' {csp_nonce} https://www.googletagmanager.com 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://www.googletagmanager.com; "
        "connect-src 'self' https://www.google-analytics.com https://www.googletagmanager.com https://region1.google-analytics.com; "
        "frame-ancestors 'self'; "
    )

    # Strict Transport Security (HTTPS enforcement) - only in production
    if not app.debug:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    return response


logger.info("Security headers middleware enabled")

# Initialize rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[config.RATELIMIT_DEFAULT],
    storage_uri=config.RATELIMIT_STORAGE_URL,
    strategy=config.RATELIMIT_STRATEGY,
)
logger.info("Rate limiting enabled")

# Make limiter available to blueprints
app.limiter = limiter

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = "auth_router.login"


@login_manager.user_loader
def load_user(user_id):
    if db_connection:
        return load_user_from_db(config.PK_STORAGE_TYPE, user_id, db_connection)
    return None


login_manager.init_app(app)

# Register blueprints
app.register_blueprint(search_router, url_prefix="/")
app.register_blueprint(modify_router, url_prefix="/")
app.register_blueprint(info_router, url_prefix="/")
app.register_blueprint(auth_router, url_prefix="/")
app.register_blueprint(contact_form_router, url_prefix="/")

# Exempt API endpoints from CSRF (they use JSON, not HTML forms)
# Note: search_router is no longer exempt as the frontend now sends X-CSRFToken
# csrf.exempt(search_router)

if __name__ == "__main__":
    app.run(port=5000)
