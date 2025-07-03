import logging
import traceback
from typing import Optional, Dict, Any

from chatbot.prompts import get_speaker_kit_system_prompt
from aixplain.factories import AgentFactory

logger = logging.getLogger(__name__)

# Create the agent ONCE at module level (singleton)
speaker_prompt = get_speaker_kit_system_prompt()
agent = AgentFactory.create(
    name="Speaker kit creator agent",
    description="An interactive speaker agent that help user create speaker kit.",
    llm_id="679a80334d6aa81bfab338b3",  # Grok 2
    instructions=speaker_prompt,
)

# print(f'****\nThis is the instruction for agent: {agent.instructions}\n****')

class AIxplainService:
    def __init__(self):
        self.agent = agent

    def initialize_conversation(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            logger.info("=== INITIALIZING CONVERSATION WITH AGENT SDK ===")
            response = self.agent.run(query="Hello", session_id=session_id)
            logger.info(f"Agent SDK response: {response}")

            # Try to extract the output safely
            output = getattr(response, "output", None)
            if output is None and hasattr(response, "data"):
                # Try to get output from data attribute
                data = getattr(response, "data", None)
                if data and hasattr(data, "output"):
                    output = getattr(data, "output", None)
            if output is None:
                # Fallback to string representation
                output = str(response)

            session_id_val = getattr(response, "session_id", None)
            if session_id_val is None and hasattr(response, "data"):
                data = getattr(response, "data", None)
                if data and hasattr(data, "session_id"):
                    session_id_val = getattr(data, "session_id", None)

            # Ensure output is a string and not None
            if not output or output == "None":
                output = "[No response from agent]"

            return {
                'success': True,
                'content': output,
                'session_id': session_id_val,
                'full_result': str(response)
            }
        except Exception as e:
            logger.error(f"Agent SDK error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e)
            }

    def continue_conversation(self, user_message: str, session_id: str) -> Dict[str, Any]:
        try:
            logger.info("=== CONTINUING CONVERSATION WITH AGENT SDK ===")
            response = self.agent.run(query=user_message, session_id=session_id)
            logger.info(f"Agent SDK response: {response}")

            # Try to extract the output safely
            output = getattr(response, "output", None)
            if output is None and hasattr(response, "data"):
                data = getattr(response, "data", None)
                if data and hasattr(data, "output"):
                    output = getattr(data, "output", None)
            if output is None:
                output = str(response)

            session_id_val = getattr(response, "session_id", None)
            if session_id_val is None and hasattr(response, "data"):
                data = getattr(response, "data", None)
                if data and hasattr(data, "session_id"):
                    session_id_val = getattr(data, "session_id", None)

            # Ensure output is a string and not None
            if not output or output == "None":
                output = "[No response from agent]"

            return {
                'success': True,
                'content': output,
                'session_id': session_id_val,
                'full_result': str(response)
            }
        except Exception as e:
            logger.error(f"Agent SDK error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e)
            }
