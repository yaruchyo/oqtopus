"""
Utility functions for the orchestrator.

This module provides utility functions for managing registered agents
and fetching responses from them using secure communication.
"""

import logging
from rotagent import KeyManager, OrchestratorClient
from agent_package import pk_storage, config
from agent_package.system_layer.security import decrypt_private_key

logger = logging.getLogger(__name__)


def load_data():
    """Load agents and domains data from storage."""
    return pk_storage.load_data()


def save_data():
    """Save current agents and domains data to storage."""
    agents = pk_storage.get_all_agents()
    domains = pk_storage.get_all_domains()
    pk_storage.save_data(agents, domains)


def get_registered_agents():
    """Get all registered agents."""
    return pk_storage.get_all_agents()


def get_agent_by_url(url):
    """Get agent by URL."""
    return pk_storage.get_agent_by_url(url)


def add_agent(agent):
    """Add a new agent."""
    pk_storage.add_agent(agent)


def update_agent(url, agent_data):
    """Update an existing agent."""
    return pk_storage.update_agent(url, agent_data)


def delete_agent(url, issuer_id):
    """Delete a specific agent by URL and issuer_id."""
    return pk_storage.delete_agent(url, issuer_id)


def get_domains():
    """Get all domains."""
    return pk_storage.get_all_domains()


def add_domain(domain):
    """Add a new domain."""
    pk_storage.add_domain(domain)


def _get_decrypted_private_key(agent_registration: dict) -> str:
    """
    Get the decrypted private key from an agent registration.

    Handles both encrypted (new) and unencrypted (legacy) private keys.

    Args:
        agent_registration: Agent registration dict containing private_key

    Returns:
        Decrypted private key PEM string
    """
    private_key = agent_registration.get("private_key")
    is_encrypted = agent_registration.get("private_key_encrypted", False)

    if not private_key:
        return None

    if is_encrypted:
        try:
            return decrypt_private_key(private_key, config.SECRET_KEY)
        except Exception as e:
            logger.error(
                f"Failed to decrypt private key for agent {agent_registration.get('url')}: {e}"
            )
            return None
    else:
        # Legacy unencrypted key - return as-is
        return private_key


async def fetch_agent_response(
    session, agent_registration, query, output_structure=None
):
    """
    Fetch response from an agent using secure communication.

    Args:
        session: aiohttp client session
        agent_registration: Full agent registration dict containing url, issuer_id, private_key
        query: Query to send to agent
        output_structure: Expected output structure (optional)

    Returns:
        Agent response or error dict
    """
    url = agent_registration.get("url")
    issuer_id = agent_registration.get("issuer_id")
    agent_name = agent_registration.get("name")

    # Decrypt the private key
    private_key = _get_decrypted_private_key(agent_registration)

    if not url or not issuer_id or not private_key:
        return {
            "error": "Invalid registration or failed to decrypt credentials",
            "agent_url": url or "Unknown",
        }

    # --- USE LIBRARY FOR REQUEST ---
    payload = {"query": query}
    if output_structure:
        payload["output_structure"] = output_structure
    agent_response = await OrchestratorClient.send_secure_request(
        session, url, payload, issuer_id, private_key
    )
    agent_response["name"] = agent_name
    return agent_response
