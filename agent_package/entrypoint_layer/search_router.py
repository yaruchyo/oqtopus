import asyncio
import json
from datetime import datetime, timedelta, timezone

import aiohttp
from flask import Blueprint, Response, current_app, request, stream_with_context
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from agent_package import db_connection, llm
from agent_package.domain_layer.route_class_domain import CATEGORIES, CategoryPrediction
from agent_package.system_layer.utils import fetch_agent_response, get_registered_agents

search_router = Blueprint("search_router", __name__)


@search_router.route("/search", methods=["POST"])
def search():
    data = request.json
    user_query = data.get("query")

    # --- Rate Limiting Logic ---
    should_set_guest_cookie = False

    if current_user.is_authenticated:
        # 1. Logged-in User Logic (5 requests/24h)
        user_email = current_user.email
        # Re-fetch user data to get latest quotas
        user_doc = db_connection.find_document("users", {"email": user_email})
        if not user_doc:
            # Should not happen if authenticated, but fallback
            pass

        requests_left = user_doc.get("requests_left", 5)
        last_reset_str = user_doc.get("last_reset_time")

        # Use UTC for consistency
        now_utc = datetime.now(timezone.utc)

        last_reset = None
        if last_reset_str:
            try:
                last_reset = datetime.fromisoformat(last_reset_str)
            except ValueError:
                pass

        # Reset cycle if > 24 hours or never started
        if last_reset is None or (now_utc - last_reset) > timedelta(hours=24):
            requests_left = 5
            last_reset = None  # Will be set to now on consumption

        if requests_left <= 0:
            return Response(
                json.dumps(
                    {
                        "type": "final",
                        "data": "Daily request limit reached (5/day). Please wait 24 hours.",
                    }
                )
                + "\n",
                mimetype="application/x-ndjson",
            )

        # Consume request
        requests_left -= 1
        if last_reset is None:
            last_reset = now_utc

        # Update DB
        db_connection.update_document(
            "users",
            {"email": user_email},
            {"requests_left": requests_left, "last_reset_time": last_reset.isoformat()},
        )

    else:
        # 2. Guest Logic (1 request/24h via IP)
        # We use the global limiter attached to app
        limiter = getattr(current_app, "limiter", None)
        if limiter:
            try:
                # 1 per day per IP
                # This raises HTTPException (429) if exceeded
                limiter.limit("1 per day")(lambda: None)()
            except HTTPException as e:
                # Return friendly JSON message instead of 429 HTML
                if e.code == 429:
                    return Response(
                        json.dumps(
                            {
                                "type": "final",
                                "data": "Guest limit reached (1/day). Please login or register to get 5 requests/day.",
                            }
                        )
                        + "\n",
                        mimetype="application/x-ndjson",
                    )
                raise e

        # should_set_guest_cookie logic is no longer needed for rate limiting,
        # but we might keep it if used for other things (it was only for limiting)
        should_set_guest_cookie = False
    # ---------------------------

    def generate():
        # Yield the updated quota immediately
        # For logged-in users, 'requests_left' is already decremented above.
        # For guests, if they reached here, they just consumed their 1 request, so 0 left.

        current_quota_display = 0
        max_quota_display = 1

        if current_user.is_authenticated:
            current_quota_display = requests_left  # Variable from outer scope
            max_quota_display = 5
        else:
            # Guest just used their one request
            current_quota_display = 0
            max_quota_display = 1

        yield json.dumps(
            {
                "type": "quota",
                "data": {"remaining": current_quota_display, "max": max_quota_display},
            }
        ) + "\n"

        prompt = f"""Classify this query: '{user_query}'"""
        prediction = llm.generate_llm_answer_pydentic(
            input_message=prompt, structure_output_class=CategoryPrediction
        )
        if isinstance(prediction, dict):
            predicted_category = prediction.get("category")
            output_str = prediction.get("output_structure", "{}")

        yield json.dumps(
            {"type": "category", "data": ", ".join(predicted_category)}
        ) + "\n"

        # 2. Fetch - Get ALL registered agents matching the category (including duplicates)
        # dynamic_structure_output_dict = json.loads(output_str)

        # Get all registered agents that match the predicted category
        matching_agents = []
        for agent in get_registered_agents():
            categories = agent.get("categories", [])
            if not categories and agent.get("category"):
                categories = [agent.get("category")]

            intersection = list(set(predicted_category) & set(categories))

            if intersection:
                matching_agents.append(agent)
                # yield json.dumps({"type": "category", "data": f"I found new agent to communicate to: {agent.get("url")}"}) + "\n"

        async def run_async_fetch():
            async with aiohttp.ClientSession() as session:
                # Pass full agent registration to fetch_agent_response
                tasks = [
                    fetch_agent_response(session, agent, user_query)
                    for agent in matching_agents
                ]
                return await asyncio.gather(*tasks) if tasks else []

        agent_responses = asyncio.run(run_async_fetch()) if matching_agents else []

        # Local Fallback
        result_llm = llm.generate_llm_answer(
            input_message=f"answer query: {user_query}"
        )

        agent_responses.append(
            {
                "name": "Orchestrator LLM Fallback Responses",
                "agent_url": None,
                "result": result_llm,
            }
        )

        yield json.dumps({"type": "agents", "data": agent_responses}) + "\n"

        # 3. Synthesize
        valid_responses = [r for r in agent_responses if "error" not in r]
        context_text = "\n".join(
            [
                f"Data from {r.get('agent_url')}: {json.dumps(r)}"
                for r in valid_responses
            ]
        )

        try:
            syn_prompt = (
                f"Query: {user_query}\nContext:\n{context_text}\nSynthesize answer."
            )
            final = llm.generate_llm_answer(syn_prompt)
        except Exception as e:
            final = "Synthesis failed."

        yield json.dumps({"type": "final", "data": final}) + "\n"

    resp = Response(stream_with_context(generate()), mimetype="application/x-ndjson")
    if should_set_guest_cookie:
        # Set session for 24 hours (requires session.permanent = True in app config/logic if not default)
        from flask import session

        session["guest_usage_time"] = datetime.now(timezone.utc).isoformat()
        session.permanent = True
    return resp
