import os
import re
import logging
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    Response,
    stream_with_context,
    redirect,
    url_for,
    flash,
    current_app,
)
from flask_login import login_required, current_user
from rotagent import KeyManager
from agent_package.domain_layer.route_class_domain import CategoryPrediction, CATEGORIES
from agent_package.system_layer.utils import (
    save_data,
    get_registered_agents,
    get_domains,
    add_agent,
    # add_domain, # Removed as domains are now derived from agents
    delete_agent as remove_agent,
)
from agent_package.system_layer.security import encrypt_private_key, is_safe_url
from agent_package import pk_storage, config
from flask import Blueprint

logger = logging.getLogger(__name__)

modify_router = Blueprint("modify_router", __name__)


@modify_router.route("/register-agent", methods=["GET", "POST"])
@login_required
def register_agent():
    if request.method == "POST":
        agent_url = request.form.get("url")
        # Handle multi-category: get list
        categories = request.form.getlist("categories")
        # Legacy/Primary category fallback
        category = categories[0] if categories else request.form.get("category")

        agent_name = request.form.get("name", "")
        orchestrator_id = request.form.get("orchestrator_id", "").strip()
        description = request.form.get("description", "")
        is_public = request.form.get("is_public") == "on"

        # Basic Validation
        if not agent_url or not categories:
            # Fallback if categories missing
            return render_template(
                "register_agent.html",
                categories=CATEGORIES,
                error="URL and at least one Category are required",
            )

        # HTTPS enforcement
        from urllib.parse import urlparse

        parsed_url = urlparse(agent_url)
        # Allow http only if purely local (localhost/127.0.0.1)
        is_local_host = parsed_url.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]
        if parsed_url.scheme != "https" and not is_local_host:
            return render_template(
                "register_agent.html",
                categories=CATEGORIES,
                error="Production agents must use HTTPS. (For local testing, use localhost or 127.0.0.1)",
            )

        # SSRF Protection - Validate Target IP
        # In DEBUG mode (development), we allow local network connections.
        # In Production, we strictly block private IPs.
        allow_private_nets = current_app.config.get("DEBUG", False)
        is_safe, security_error = is_safe_url(agent_url, allow_local=allow_private_nets)

        if not is_safe:
            return render_template(
                "register_agent.html",
                categories=CATEGORIES,
                error=f"Security Violation: {security_error}",
            )

        # Validate orchestrator_id: mandatory, lowercase letters, numbers, and underscores only
        if not orchestrator_id:
            return render_template(
                "register_agent.html",
                categories=CATEGORIES,
                error="Orchestrator ID is required",
            )

        if not re.match(r"^[a-z0-9_]+$", orchestrator_id):
            return render_template(
                "register_agent.html",
                categories=CATEGORIES,
                error="Orchestrator ID must contain only lowercase letters, numbers, and underscores (no spaces)",
            )

        # Check for duplicate URL + orchestrator_id combination
        existing_agents = get_registered_agents()
        if any(
            a.get("url") == agent_url and a.get("issuer_id") == orchestrator_id
            for a in existing_agents
        ):
            return render_template(
                "register_agent.html",
                categories=CATEGORIES,
                error=f'An agent with URL "{agent_url}" and Orchestrator ID "{orchestrator_id}" already exists',
            )

        # Check if URL is already publicly listed by another owner
        # Prevents users from claiming URLs they don't own
        public_agents_with_url = [
            a
            for a in existing_agents
            if a.get("url") == agent_url and a.get("is_public", False)
        ]
        if public_agents_with_url:
            # Check if current user owns any of these public agents
            user_owns_public_agent = any(
                a.get("user_id") == current_user.id for a in public_agents_with_url
            )
            if not user_owns_public_agent:
                return render_template(
                    "register_agent.html",
                    categories=CATEGORIES,
                    error=f"This URL is already publicly registered by another user. You cannot register an agent with this URL unless you are the owner.",
                )

        # --- USE LIBRARY FOR KEYS ---
        private_pem, public_pem = KeyManager.generate_rsa_keypair()

        # Encrypt the private key before storing
        try:
            encrypted_private_key = encrypt_private_key(private_pem, config.SECRET_KEY)
            logger.info(f"Private key encrypted successfully for agent: {agent_url}")
        except Exception as e:
            logger.error(f"Failed to encrypt private key: {e}")
            return render_template(
                "register_agent.html",
                categories=CATEGORIES,
                error="Failed to secure agent credentials. Please try again.",
            )

        mongo_db_registration = {
            "url": agent_url,
            "category": category,  # Primary category (string) for legacy support
            "categories": categories,  # Full list of categories
            "name": agent_name or agent_url,
            "description": description,
            "issuer_id": orchestrator_id,
            "user_id": current_user.id,  # Assign owner
            "is_public": is_public,  # Visibility
            "private_key": encrypted_private_key,  # Now encrypted!
            "private_key_encrypted": True,  # Flag to indicate encryption
            "created_at": datetime.now().isoformat(),
            "registration_time": datetime.now().isoformat(),
        }

        flask_registration = {
            "url": agent_url,
            "category": category,  # Primary category (string) for legacy support
            "categories": categories,  # Full list of categories
            "name": agent_name or agent_url,
            "description": description,
            "issuer_id": orchestrator_id,
            "user_id": current_user.id,
            "is_public": is_public,
            "created_at": datetime.now().isoformat(),
            "registration_time": datetime.now().isoformat(),
        }

        # Add agent using the new storage API
        add_agent(mongo_db_registration)

        # domains = get_domains()
        # if not any(d['url'] == agent_url for d in domains):
        #     add_domain({'url': agent_url, 'category': category})

        return render_template(
            "registration_result.html",
            registration=flask_registration,
            public_pem=public_pem,
            filename=f"{orchestrator_id}.pem",  # Correct filename for download
        )

    return render_template("register_agent.html", categories=CATEGORIES)


@modify_router.route("/edit-agent/<int:index>", methods=["GET", "POST"])
@login_required
def edit_agent(index):
    agents = get_registered_agents()

    if index < 0 or index >= len(agents):
        flash("Agent not found", "error")
        return redirect(url_for("info_router.my_agents"))

    agent = agents[index]

    # Ownership Check (CRITICAL)
    if agent.get("user_id") != current_user.id:
        flash("You do not have permission to edit this agent.", "error")
        return redirect(url_for("info_router.my_agents"))

    if request.method == "POST":
        agent_name = request.form.get("name", "")
        agent_url = request.form.get("url", "")
        # Multi-category
        categories = request.form.getlist("categories")

        description = request.form.get("description", "")
        is_public = request.form.get("is_public") == "on"

        if not agent_url or not categories:
            flash("URL and Categories are required", "error")
            return render_template(
                "edit_agent.html", agent=agent, index=index, categories=CATEGORIES
            )

        # SSRF Protection for Edits
        allow_private_nets = current_app.config.get("DEBUG", False)
        is_safe, security_error = is_safe_url(agent_url, allow_local=allow_private_nets)

        if not is_safe:
            flash(f"Security Violation: {security_error}", "error")
            return render_template(
                "edit_agent.html", agent=agent, index=index, categories=CATEGORIES
            )

        # Get old URL to update domains list
        old_url = agent["url"]

        # Create updated agent data (preserve private key and other fields)
        # We modify the 'agent' dict directly or copy?
        # pk_storage.update_agent usually takes the whole dict.
        updated_agent = agent.copy()
        updated_agent["name"] = agent_name or agent_url
        updated_agent["url"] = agent_url
        updated_agent["categories"] = categories
        updated_agent["category"] = categories[0]
        updated_agent["description"] = description
        updated_agent["is_public"] = is_public

        # Update agent in storage
        pk_storage.update_agent(old_url, updated_agent)

        # Update domains list - remove old, add new (CRITICAL RESTORATION)
        # domains = get_domains()
        # Update domain entry
        # Note: If URL changed, we find by old_url.
        # for i, domain in enumerate(domains):
        #     if domain['url'] == old_url:
        #         domains[i] = {'url': agent_url, 'category': categories[0]}
        #         break

        # Save updated domains
        # pk_storage.save_data(get_registered_agents(), domains)

        flash("Agent updated successfully.", "success")
        return redirect(url_for("info_router.my_agents"))

    return render_template(
        "edit_agent.html", agent=agent, index=index, categories=CATEGORIES
    )


@modify_router.route("/delete-agent/<int:index>", methods=["POST"])
@login_required
def delete_agent(index):
    agents = get_registered_agents()

    if index >= 0 and index < len(agents):
        agent = agents[index]

        # Ownership Check
        if agent.get("user_id") != current_user.id:
            flash("You do not have permission to delete this agent.", "error")
            return redirect(url_for("info_router.my_agents"))

        agent_url = agent["url"]
        agent_issuer_id = agent.get("issuer_id", "")

        # Remove specific agent from storage (by URL + issuer_id)
        remove_agent(agent_url, agent_issuer_id)

        # Only remove domain if no other agents use this URL
        # remaining_agents = get_registered_agents()
        # if not any(a.get('url') == agent_url for a in remaining_agents):
        #     domains = [d for d in get_domains() if d['url'] != agent_url]
        #     pk_storage.save_data(remaining_agents, domains)

        flash("Agent deleted successfully.", "success")

    return redirect(url_for("info_router.my_agents"))
