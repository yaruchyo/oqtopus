import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Union


class PKStorageBase(ABC):
    """Abstract base class for private key storage."""

    @abstractmethod
    def load_data(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Load agents and domains data.

        Returns:
            Tuple containing (agents list, domains list)
        """
        pass

    @abstractmethod
    def save_data(self, agents: List[Dict], domains: List[Dict]) -> None:
        """
        Save agents and domains data.

        Args:
            agents: List of agent dictionaries
            domains: List of domain dictionaries (with 'url' and 'category' keys)
        """
        pass

    @abstractmethod
    def get_agent_by_url(self, url: str) -> Optional[Dict]:
        """
        Get agent by URL.

        Args:
            url: Agent URL

        Returns:
            Agent dictionary or None if not found
        """
        pass

    @abstractmethod
    def add_agent(self, agent: Dict) -> None:
        """
        Add a new agent.

        Args:
            agent: Agent dictionary containing url, issuer_id, private_key
        """
        pass

    @abstractmethod
    def update_agent(self, url: str, agent_data: Dict) -> bool:
        """
        Update an existing agent.

        Args:
            url: Agent URL to update
            agent_data: New agent data

        Returns:
            True if updated, False if not found
        """
        pass

    @abstractmethod
    def delete_agent(self, url: str, issuer_id: str) -> bool:
        """
        Delete a specific agent by URL and issuer_id.

        Args:
            url: Agent URL to delete
            issuer_id: Orchestrator ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def get_all_agents(self) -> List[Dict]:
        """
        Get all registered agents.

        Returns:
            List of agent dictionaries
        """
        pass

    @abstractmethod
    def add_domain(self, domain: Dict) -> None:
        """
        Add a new domain.

        Args:
            domain: Domain dictionary with 'url' and 'category' keys
        """
        pass

    @abstractmethod
    def get_all_domains(self) -> List[Dict]:
        """
        Get all domains.

        Returns:
            List of domain dictionaries
        """
        pass
