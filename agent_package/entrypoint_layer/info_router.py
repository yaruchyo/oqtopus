from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, render_template, request, send_from_directory

from agent_package import db_connection
from agent_package.domain_layer.route_class_domain import CATEGORIES
from agent_package.system_layer.utils import get_domains, get_registered_agents

info_router = Blueprint("info_router", __name__)

from flask_login import current_user, login_required


@info_router.route("/", methods=["GET"])
def index():
    agents = get_registered_agents()

    # Create distinct active agents list (unique by URL)
    registered_agents = get_registered_agents()
    domains = get_domains()

    # Filter agents for display
    display_agents = []
    seen_urls = set()
    distinct_agents = []

    for agent in registered_agents:
        is_public = agent.get("is_public", True)  # Default to public if missing
        is_owned = (
            current_user.is_authenticated and agent.get("user_id") == current_user.id
        )

        if is_public or is_owned:
            # Add to full list if we kept it, but here we want distinct for the main view
            url = agent.get("url")
            if url not in seen_urls:
                seen_urls.add(url)
                distinct_agents.append(agent)

    # --- Calculate Requests Left for UI ---
    requests_left = 0
    max_requests = 1

    if current_user.is_authenticated:
        max_requests = 5
        user_doc = db_connection.find_document("users", {"email": current_user.email})
        if user_doc:
            requests_left = user_doc.get("requests_left", 5)
            last_reset_str = user_doc.get("last_reset_time")

            last_reset = None
            if last_reset_str:
                try:
                    last_reset = datetime.fromisoformat(last_reset_str)
                except ValueError:
                    pass

            now_utc = datetime.now(timezone.utc)
            if last_reset is None or (now_utc - last_reset) > timedelta(hours=24):
                requests_left = 5
    else:
        # Guest
        max_requests = 1
        last_guest_usage_str = request.cookies.get("guest_usage_time")
        if last_guest_usage_str:
            try:
                last_guest_usage = datetime.fromisoformat(last_guest_usage_str)
                if (datetime.now(timezone.utc) - last_guest_usage) < timedelta(
                    hours=24
                ):
                    requests_left = 0
                else:
                    requests_left = 1
            except ValueError:
                requests_left = 1
        else:
            requests_left = 1
    # --------------------------------------

    return render_template(
        "index.html",
        agents=distinct_agents,
        domains=domains,
        requests_left=requests_left,
        max_requests=max_requests,
    )


@info_router.route("/sitemap.xml")
def sitemap():
    return send_from_directory(current_app.static_folder, "sitemap.xml")


@info_router.route("/robots.txt")
def robots():
    return send_from_directory(current_app.static_folder, "robots.txt")


@info_router.route("/my-agents", methods=["GET"])
@login_required
def my_agents():
    all_agents = get_registered_agents()
    # Store both the agent data AND its original index in the global list
    # This ensures edit/delete actions target the correct agent in the backend
    user_agents_with_index = []

    for i, agent in enumerate(all_agents):
        if agent.get("user_id") == current_user.id:
            user_agents_with_index.append({"data": agent, "global_index": i})

    return render_template("my_agents.html", agents=user_agents_with_index)
