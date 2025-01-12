from fastapi import FastAPI
from src.agent import ZerePyAgent
from venv import logger
import uvicorn
import asyncio

class API:
    def __init__(self, agent: ZerePyAgent):
        self.app = FastAPI()
        self._setup_routes()
        self.agent = agent

    async def initialize(self):
        try:
            repo_data: str = await self.agent.connection_manager.perform_action("github", "get-repo", [])
            chunk_text = self.agent.chunk_text(repo_data)
            logger.info(len(chunk_text))
            embeddings = self.agent.generate_embeddings(chunk_text)
            logger.info("All embeddings have been created")
            self.agent.upload_embeddings(self.agent.connection_manager.connections["github"].repo, embeddings, chunk_text)
        except Exception as e:
            logger.error(f"Error initializing API: {e}")
            raise

    def _setup_routes(self):
        @self.app.get("/query/{query}")
        async def query_chatbot(query: str):
            logger.info(self.agent.connection_manager.list_connections())
            
            async def getQueryVector(query): 
                return self.agent.generate_embeddings([query])
            
            logger.info(query)
            res = await getQueryVector(query)
            res = res[0]

            index_name = self.agent.connection_manager.connections["github"].repo.replace('/', '-').lower()
            
            pinecone_results = self.agent.query_embeddings(index_name, res)
            logger.info(pinecone_results)

            openai_response = self.agent.prompt_llm(query, pinecone_results)

            return {"response": openai_response}

    async def run(self, host="0.0.0.0", port=8000):
        await self.initialize()
        config = uvicorn.Config(self.app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()

if __name__ == "__main__":
    api = API()
    asyncio.run(api.run())