import datetime, random, time, logging, json
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from src.helpers import print_h_bar
from src.langgraph.langgraph_agent import LangGraphAgent
from src.connection_manager import ConnectionManager
from src.langgraph.prompts import DETERMINATION_PROMPT, DIVISION_PROMPT, EXECUTION_PROMPT, EVALUATION_PROMPT, \
    OBSERVATION_PROMPT

# Initialize logger
logger = logging.getLogger("agent")

class AgentState(TypedDict):
    context: dict
    context_summary: str
    current_task: str | None
    action_plan: list
    action_log: list
    task_log: list
    process_flag: bool

class ZerePyAgent:
    def __init__(self, agent_config: dict):
        try:
            # Load agent configuration
            self._setup_agent_config(agent_config)

            # Build the graph
            self._build_graph()
        
        except Exception as e:
            logger.error("Could not load ZerePy Agent")
            raise e

    def _build_graph(self):
        # Construct graph
        graph_builder = StateGraph(AgentState)

        # Add nodes
        graph_builder.add_node("observation", self.observation_step)
        graph_builder.add_node("determination", self.determination_step)
        graph_builder.add_node("division", self.division_step)
        graph_builder.add_node("execution", self.execution_step)
        graph_builder.add_node("evaluation", self.evaluation_step)

        # Add edges
        graph_builder.add_edge(START, "observation")
        graph_builder.add_edge("observation", "determination")
        graph_builder.add_edge("determination", "division")
        graph_builder.add_edge("division", "execution")
        graph_builder.add_edge("execution", "evaluation")
        graph_builder.add_edge("evaluation", "observation")

        # Initialize the graph
        self.graph = graph_builder.compile()

    def _setup_agent_config(self, agent_config: dict):
        try:
            # GENERAL CONFIG
            general_config = agent_config["config"]
            self.name = general_config["name"]
            self.loop_delay = general_config["loop_delay"]
            self.time_based_multipliers = general_config.get("time_based_multipliers", None)

            # CONNECTIONS
            connections_config = agent_config["connections"]
            self.connection_manager = ConnectionManager(connections_config)
            self.connections = self.connection_manager.get_connections()

            # LLM CONFIG
            llm_config = agent_config["llms"]

            # CHARACTER LLM
            character_config = llm_config["character"]
            self.character_name = character_config["name"]
            self.bio = character_config.get("bio", [])
            self.traits = character_config.get("traits", [])
            self.examples = character_config.get("examples", [])
            self.example_accounts = character_config.get("example_accounts", [])
            self.model_provider = character_config["model_provider"]
            self.model = character_config["model"]

            # EXECUTOR + DRIVER LLM
            executor_config = llm_config["executor"]
            self.executor_model_provider = executor_config["model_provider"]
            self.executor_model = executor_config["model"]

            # SYSTEM PROMPT
            self.system_prompt = self._construct_system_prompt()

            # LLM PREFERENCES
            self.llm_prefs = {
                'provider': self.model_provider,
                'model': self.model,
                'system_prompt': self.system_prompt
            }

            # LANGCHAIN AGENTS
            # LangChain functionality can only be enabled if the model providers are OpenAI or Anthropic
            if self.model_provider in ["openai", "anthropic"] and self.executor_model_provider in ["openai", "anthropic"]:
                self.langchain_enabled = True
                self.driver_llm = LangGraphAgent(
                    model_provider=self.executor_model_provider,
                    model=self.executor_model,
                    bind_tools=False,
                    connection_manager=self.connection_manager
                )
                self.character_llm = LangGraphAgent(
                    model_provider=self.model_provider,
                    model=self.model,
                    bind_tools=False,
                    connection_manager=self.connection_manager
                )
                self.executor_agent = LangGraphAgent(
                    model_provider=self.executor_model_provider,
                    model=self.executor_model,
                    bind_tools=True,
                    connection_manager=self.connection_manager
                )
            else:
                self.langchain_enabled = False
                self.driver_llm = None
                self.character_llm = None
                self.executor_agent = None

            # TASK CONFIGS
            self.tasks = agent_config.get("tasks", [])
            self.task_weights = [task.get("weight", 0) for task in self.tasks]
            self.loop_task = False

        except KeyError as e:
            raise KeyError(f"Missing required field in agent configuration: {e}")
        except Exception as e:
            raise Exception(f"Error setting up agent configs: {e}")
        
    def perform_action(self, connection: str, action: str, **kwargs) -> None:
        return self.connection_manager.perform_action(connection, action, **kwargs)

    def _construct_system_prompt(self) -> str:
        """Construct the system prompt from agent configuration"""
        prompt_parts = []
        prompt_parts.extend(self.bio)

        if self.traits:
            prompt_parts.append("\nYour key traits are:")
            prompt_parts.extend(f"- {trait}" for trait in self.traits)

        if self.examples or self.example_accounts:
            prompt_parts.append("\nHere are some examples of your style (Please avoid repeating any of these):")
            if self.examples:
                prompt_parts.extend(f"- {example}" for example in self.examples)

            if self.example_accounts:
                for example_account in self.example_accounts:
                    tweets = self.connection_manager.perform_action(
                        connection_name="twitter",
                        action_name="get-latest-tweets-from-user",
                        params=[example_account]
                    )
                    if tweets:
                        prompt_parts.extend(f"- {tweet['text']}" for tweet in tweets)

        system_prompt = "\n".join(prompt_parts)
        return system_prompt
     
    def _replenish_inputs(self, context_dict: dict = {}):
        try:
            if "timeline_tweets" not in context_dict or context_dict["timeline_tweets"] is None or len(context_dict["timeline_tweets"]) == 0:
                if (self.connections.get("twitter")):
                        logger.info("\n👀 READING TIMELINE")
                        context_dict["timeline_tweets"] = self.connection_manager.perform_action(
                            connection_name="twitter",
                            action_name="read-timeline",
                            params=[]
                        )

            if "room_info" not in context_dict or context_dict["room_info"] is None:
                if (self.connections.get("echochambers")):
                    logger.info("\n👀 READING ECHOCHAMBERS ROOM INFO")
                    context_dict["room_info"] = self.connection_manager.perform_action(
                        connection_name="echochambers",
                        action_name="get-room-info",
                        params={}
                    )

            return context_dict
        except Exception as e:
            logger.error(f"Error replenishing inputs: {e}")


    def observation_step(self, state: AgentState):
        print("\n=== OBSERVATION STEP ===")
        print(f"Summarizing contextual information...")

        state["context"] = self._replenish_inputs(state["context"])
        query = state['current_task']

        try:
            observation_prompt = OBSERVATION_PROMPT.format(context=state['context'], task_log=state['task_log'])
            print(f"Observation Prompt: {observation_prompt}")
            context_summary = self.character_llm.invoke(observation_prompt).content
        except Exception as e:
            logger.error(f"Error generating context summary: {e}")
            context_summary = "There is currently no additional context available."

        print(f"\nCONTEXT SUMMARY:\n{context_summary}")
        return {"context_summary": context_summary}
    
    def determination_step(self, state: AgentState):
        print("\n=== DETERMINATION STEP ===")
        print("Determining next task...")

        task = state['current_task']

        if task is None or task.strip() == "":
            determination_prompt = DETERMINATION_PROMPT.format(context_summary=state['context_summary'], connection_action_list="\n\n".join(connection.__str__() for connection in self.connections.values()))
            task = self.character_llm.invoke(determination_prompt).content

        print(f"\nDETERMINED TASK: {task}")
        return {"current_task": task}

    def division_step(self, state: AgentState):
        print("\n=== DIVISION STEP ===")
        print(f"Creating action plan for task: {state['current_task']}")
        division_prompt = DIVISION_PROMPT.format(current_task=state['current_task'], connection_action_list="\n\n".join(connection.__str__() for connection in self.connections.values()), preferred_llm_config=str(self.llm_prefs))
        action_plan_text = self.driver_llm.invoke(division_prompt).content
        action_plan = action_plan_text.split("\n")

        print(f"\nGENERATED ACTION PLAN:\n{action_plan_text}")
        return {"action_plan": action_plan}

    def execution_step(self, state: AgentState) -> AgentState:
        print("\n=== EXECUTION STEP ===")
        print("Executing actions...")
        action_plan = state["action_plan"]

        if not action_plan:
            print("No actions to execute")
            return state

        for action in action_plan:
            print(f"\nExecuting action: {action}")
            execution_prompt = EXECUTION_PROMPT.format(action_log=state["action_log"],  preferred_llm_config=str(self.llm_prefs), action=action)
            response = self.executor_agent.invoke(execution_prompt)
            state = self.executor_agent.process_response(response, state)
        
        return state

    def evaluation_step(self, state: AgentState):
        #Convert action_logs to a summary of what the agent did, and then pass it to task_log
        print("\n=== EVALUATION STEP ===")
        print("Evaluating action logs...")
        action_log = state["action_log"]
        evaluation_prompt = EVALUATION_PROMPT.format(current_task=state['current_task'], action_log =  "\n".join(f"{action['action']}:\n" +f"Result: {action['result']}"for action in action_log))
        generated_task_log = self.driver_llm.invoke(evaluation_prompt).content
        print(f"Generated task log:\n{generated_task_log}")
        state["current_task"] = state["current_task"] if self.loop_task else None
        state["task_log"].append(generated_task_log)
        state["task_log"] = state["task_log"][-3:]  #trim to the last 3 task logs

        if (not state["process_flag"]): #only clear the action log if in a loop
            state["action_log"] = []  
            state["action_plan"] = [] 
            logger.info(f"\n⏳ Waiting {self.loop_delay} seconds before next loop...") # Delay before next loop
            time.sleep(self.loop_delay)
            
        print_h_bar()
        return state
    
    def process_task(self, task: str = None): # Process a single task
        if task is None:
            task = input("\n🔹 Enter the task to perform (e.g., 'Read the timeline, then write a tweet about it').\n\n➡️ YOUR TASK: ")

        state = {
            "context": {},
            "current_task": task,
            "context_summary": "",
            "action_plan": [],
            "action_log": [],
            "task_log": [],
            "process_flag": True
        }
        state.update(self.determination_step(state))
        state.update(self.division_step(state))
        state = self.execution_step(state)
        state.update(self.evaluation_step(state))
        
        #add final_response of the last action to the state
        state["final_response"] = state["action_log"][-1]["final_response"] if state["action_log"] else None
        
        return state

    def loop(self, task=None):
        # Check if LangChain enabled
        if not self.langchain_enabled:
            logger.info("Running an Autonomous agent requires an OpenAI or Anthropic LLM. Make sure you defined valid OpenAI or Anthropic LLMs for your 'character' and 'executor' LLMs.")
            return None

        task_to_perform = input("\n🔹 Enter the first task to perform (e.g., 'Read the timeline, then write a tweet about it').\n"
                                "🔹 Or simply press Enter to let the agent autonomously decide its own tasks and plans in a loop.\n\n➡️ YOUR TASK: "
                                )
        if task_to_perform:
            loop_task = input("\n🔄 Would you like to repeat this task in every loop? \n"
                  "Enter 'y' for yes, or 'n' to let the agent generate new tasks dynamically in each loop.\n\n➡️ YOUR CHOICE: ")
            self.loop_task = True if loop_task.lower() == "y" else False

        initial_state = {
            "context": {},
            "current_task": task_to_perform,
            "context_summary": "",
            "action_plan": [],
            "action_log": [],
            "task_log": [],
            "process_flag": False
        }
        logger.info(f"\n🚀 Starting autonomous agent loop ...")
        logger.info("Press Ctrl+C at any time to stop the loop.")
        print_h_bar()
        time.sleep(2)
        logger.info("Starting loop in 5 seconds...")
        for i in range(5, 0, -1):
            logger.info(f"{i}...")
            time.sleep(1)

        # Run the graph
        final_state = self.graph.invoke(initial_state)
        return final_state