from typing import List, Dict, Optional, Tuple, Union
from agent_package.domain_layer.pk_storage_base import PKStorageBase


class DBStorage(PKStorageBase):
    """MongoDB storage implementation."""

    AGENTS_COLLECTION = "orchestrator_agents"
    PK_STORAGE_COLLECTION = "pk_storage"  # Alternative single collection approach

    def __init__(self, mongodb_instance):
        """
        Initialize MongoDB storage.

        Args:
            mongodb_instance: An instance of the MongoDB class
        """
        self.db = mongodb_instance

    def load_data(self) -> Tuple[List[Dict], List[Dict]]:
        """Load agents and domains data from MongoDB."""
        agents = self.get_all_agents()
        domains = self.get_all_domains()
        return agents, domains

    def save_data(self, agents: List[Dict], domains: List[Dict]) -> None:
        """
        Save agents data to MongoDB.

        CRITICAL: This method previously wiped the entire collection.
        This is unsafe for production DB usage.
        It is disabled to prevent accidental data loss.
        Use add_agent, update_agent, or delete_agent instead.
        """
        raise NotImplementedError(
            "Mass save_data is disabled for safety. Use individual add/update methods."
        )
        # self.db.delete_documents(self.AGENTS_COLLECTION, {})
        # if agents:
        #     self.db.insert_many_documents(self.AGENTS_COLLECTION, agents)

    def get_agent_by_url(self, url: str) -> Optional[Dict]:
        """Get agent by URL from MongoDB."""
        result = self.db.find_document(self.AGENTS_COLLECTION, {"url": url})
        if result:
            # Remove MongoDB's _id field for consistency
            result.pop("_id", None)
        return result

    def add_agent(self, agent: Dict) -> None:
        """Add a new agent to MongoDB."""
        # NOTE: Duplicate check commented out to allow multiple agents with same URL
        # existing = self.get_agent_by_url(agent.get('url', ''))
        # if existing:
        #     # Update existing agent
        #     self.db.update_document(
        #         self.AGENTS_COLLECTION,
        #         {"url": agent.get('url')},
        #         agent
        #     )
        # else:
        #     self.db.insert_document(self.AGENTS_COLLECTION, agent)
        self.db.insert_document(self.AGENTS_COLLECTION, agent)

    def update_agent(self, url: str, agent_data: Dict) -> bool:
        """Update an existing agent in MongoDB."""
        result = self.db.update_document(
            self.AGENTS_COLLECTION, {"url": url}, agent_data
        )
        return result > 0

    def delete_agent(self, url: str, issuer_id: str) -> bool:
        """Delete a specific agent by URL and issuer_id from MongoDB."""
        result = self.db.delete_document(
            self.AGENTS_COLLECTION, {"url": url, "issuer_id": issuer_id}
        )
        return result > 0

    def get_all_agents(self) -> List[Dict]:
        """Get all registered agents from MongoDB."""
        agents = self.db.find_documents(self.AGENTS_COLLECTION, {})
        # Remove MongoDB's _id field for consistency
        for agent in agents:
            agent.pop("_id", None)
        return agents

    def add_domain(self, domain: Dict) -> None:
        """
        No-op: Domains are now derived from agents.
        Legacy method kept for interface compatibility.
        """
        pass

    def get_all_domains(self) -> List[Dict]:
        """
        Get unique domains derived from registered agents.
        Returns a list of dicts with 'url' and 'category'.
        """
        agents = self.get_all_agents()
        unique_domains = {}
        for agent in agents:
            url = agent.get("url")
            # First one wins for category, or you could implement other logic
            if url and url not in unique_domains:
                unique_domains[url] = {"url": url, "category": agent.get("category")}
        return list(unique_domains.values())
