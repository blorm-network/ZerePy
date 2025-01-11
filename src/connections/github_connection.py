import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import aiohttp
from dotenv import load_dotenv
from pathlib import Path
from src.connections.base_connection import BaseConnection, Action


logger = logging.getLogger("github_connection")
MAX_TOKENS = 300

class GitHubConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        # Try loading from different locations
        load_dotenv()  # Try current directory
        load_dotenv(Path('../.env'))  # Try parent directory
        load_dotenv(Path('../../.env'))  # Try two levels up
        
        self.token = os.getenv('GITHUB_TOKEN')
        if not self.token:
            raise ValueError("GitHub token not found in environment variables")
            
        self.repo = config.get('repository')
        if not self.repo:
            raise ValueError("GitHub repository not specified in config")
            
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'
        self.session = None
        self.stats_cache = {}
        self.last_update = None
    
    @property
    def is_llm_provider(self) -> bool:
        return False

    async def setup(self):
        """Initialize aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
        

    async def get_repo(self) -> str:
        """Get current repository statistics and process repository content"""
        await self.setup()

        def is_allowed_filetype(filename):
            allowed_extensions = ['.py', '.txt', '.js', '.tsx', '.ts', '.md', '.cjs', '.html', '.json', '.ipynb', '.h', '.sh', '.yaml']
            return any(filename.endswith(ext) for ext in allowed_extensions)
        
        try:
            # Only update cache every hour
            current_time = datetime.now()
            if (self.last_update and 
                current_time - self.last_update < timedelta(hours=1) and 
                self.stats_cache):
                logger.info("Returning cached GitHub stats")
                return self.stats_cache['content']

            logger.info(f"Fetching fresh stats for repository: {self.repo}")

            # Get repository info
            logger.info("Fetching repository info...")
            async with self.session.get(f'{self.base_url}/repos/{self.repo}') as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch repository info: {response.status}")
                    logger.error(f"Response: {await response.text()}")
                    return ""
                repo_data = await response.json()
                logger.debug(f"Repository info received: {repo_data}")

            # Process repository content
            repo_content = [f'<source type="github_repository" url="https://github.com/{self.repo}">']
            repo_content.append(f'<stats stars="{repo_data["stargazers_count"]}" forks="{repo_data["forks_count"]}" watchers="{repo_data["subscribers_count"]}" />')

            async def process_directory(url, repo_content):
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    files = await response.json()

                    for file in files:
                        if file["type"] == "file" and is_allowed_filetype(file["name"]):
                            logger.info(f"Processing {file['path']}...")
                            async with self.session.get(file["download_url"]) as file_response:
                                file_content = await file_response.text()
                                repo_content.append(f'<file name="{file["path"]}">')
                                repo_content.append(file_content)
                                repo_content.append('</file>')

                        elif file["type"] == "dir":
                            await process_directory(file["url"], repo_content)

            async def process_pulls(repo_content):
                async with self.session.get(f'{self.base_url}/repos/{self.repo}/pulls') as response:
                    response.raise_for_status()
                    pulls = await response.json()
                    repo_content.append('<pull_requests>')
                    for pr in pulls:
                        repo_content.append(f'<pr title="{pr["title"]}" url="{pr["html_url"]}" created_at="{pr["created_at"]}">')
                        repo_content.append(f'  <body>{pr["body"]}</body>')
                        repo_content.append('</pr>')
                    repo_content.append('</pull_requests>')

            async def process_commits(repo_content):
                async with self.session.get(f'{self.base_url}/repos/{self.repo}/commits') as response:
                    response.raise_for_status()
                    commits = await response.json()
                    repo_content.append('<commits>')
                    for commit in commits:
                        repo_content.append(f'<commit message="{commit["commit"]["message"]}" url="{commit["html_url"]}" date="{commit["commit"]["committer"]["date"]}">')
                        repo_content.append(f'  <author>{commit["commit"]["committer"]["name"]}</author>')
                        repo_content.append('</commit>')
                    repo_content.append('</commits>')

            contents_url = f'{self.base_url}/repos/{self.repo}/contents'
            await process_directory(contents_url, repo_content)
            await process_pulls(repo_content)
            await process_commits(repo_content)
            
            repo_content.append('</source>')
            logger.info("All files processed.")

            # Update stats cache
            self.stats_cache = {
                'stars': repo_data.get('stargazers_count', 0),
                'new_stars': 0,  # This would need to be calculated as before
                'forks': repo_data.get('forks_count', 0),
                'open_issues': repo_data.get('open_issues_count', 0),
                'recent_commits': 0,  # This would need to be calculated as before
                'open_prs': 0,
                'watchers': repo_data.get('subscribers_count', 0),
                'content': "\n".join(repo_content)
            }
            self.last_update = current_time

            repo_content = " ".join(str(element) for element in repo_content)
            return repo_content

        except Exception as e:
            logger.error(f"Error fetching GitHub stats: {e}")
            logger.exception("Full traceback:")
            return ""
        
    def configure(self) -> bool:
        """Sets up GitHub API authentication"""
        load_dotenv()  # Load environment variables from .env file
        self.token = os.getenv('GITHUB_TOKEN')
        if not self.token:
            logger.error("GitHub token not found in environment variables.")
            return False

        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        logger.info("GitHub client configured successfully.")
        return True
        
    def register_actions(self) -> None:
        """Register available Github actions"""
        self.actions = {
            "get-repo": Action(
                name="get-repo",
                parameters=[],
                description="Gets all the current repo information including stats, code, and readme files."
            )
        }

    def is_configured(self) -> bool:
        """Checks if the GitHub connection is configured by verifying the presence of the API key"""
        return self.token is not None

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Github configuration from JSON"""
        required_fields = ["repository"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
        
        return config
        
    async def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Github action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace("-", "_")
        method = getattr(self, method_name)
        return await method(**kwargs)