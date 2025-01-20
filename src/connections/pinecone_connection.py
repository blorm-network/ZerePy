import os
from venv import logger
from pinecone import Pinecone
from typing import Any, Dict, List
from dotenv import load_dotenv
from pathlib import Path
from src.connections.base_connection import Action, ActionParameter, BaseConnection

class PineconeConnection(BaseConnection):
    def __init__(self, config):
        logger.info("Initializing Pinecone connection....")
        super().__init__(config)

        load_dotenv()  # Try current directory
        load_dotenv(Path('../.env'))  # Try parent directory
        load_dotenv(Path('../../.env'))  # Try two levels up
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.client = Pinecone(api_key=self.api_key)

    @property
    def is_llm_provider(self) -> bool:
        return False

    def register_actions(self) -> None:
        """Register available Pinecone actions"""
        self.actions = {
            "upload-embeddings": Action(
                name="upload-embeddings",
                parameters=[
                    ActionParameter("index_name", True, str, "Index name for the Pinecone connection."),
                    ActionParameter("embeddings", True, list, "List of all embeddings that need to be uploaded."),
                    ActionParameter("chunk_texts", True, list, "List of all the chunks of text that need to be uploaded to Pinecone.")
                ],
                description="Upload embeddings on Pinecone"
            ),
            "query-embeddings": Action(
                name="query-embeddings",
                parameters=[
                    ActionParameter("index_name", True, str, "Index name for the Pinecone connection."),
                    ActionParameter("query_vector", True, list, "Vector that needs to be queried in pinecone."),
                    ActionParameter("top_k", False, int, "Top K results to be pulled from the pinecone db.")
                ],
                description="Query embeddings on Pinecone"
            )
        }

    def upload_embeddings(self, index_name, embeddings, chunk_texts):
        index_name = index_name.replace('/', '-').lower()
        vectors = [(f"chunk-{i}", embedding, {"text": chunk_texts[i]}) for i, embedding in enumerate(embeddings)]
        self.client.Index(index_name).upsert(vectors)

    def query_embeddings(self, index_name, query_vector, top_k=3):
        index = self.client.Index(index_name)
        results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
        return [result['metadata']['text'] for result in results['matches']]
    
    def configure(self) -> bool:
        """Sets up Pinecone API"""
        if not self.api_key:
            logger.error("Pinecone API key not found in environment variables.")
            return False
        
        try:
            # Assuming Pinecone has a client setup method
            if (self.client is not None):
                logger.info("Pinecone client configured successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Pinecone client: {e}")
            return False

    def is_configured(self) -> bool:
        """Checks if the Pinecone connection is configured"""
        return self.client is not None

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Pinecone configuration from JSON"""
        return config
    
    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)