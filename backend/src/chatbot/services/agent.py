import requests
import json
from django.conf import settings
from typing import Optional, Dict, Any, List
import logging
import traceback
import time
import threading

logger = logging.getLogger(__name__)

class AIxplainService:
    def __init__(self):
        self.api_key = getattr(settings, 'AIXPLAIN_API_KEY', '')
        self.base_url = getattr(settings, 'AIXPLAIN_BASE_URL', 'https://platform-api.aixplain.com/sdk')
        self.agent_id = getattr(settings, 'AIXPLAIN_AGENT_ID', '')
        
        # Log configuration
        logger.info(f"AIxplain API Key configured: {bool(self.api_key)}")
        logger.info(f"AIxplain Base URL: {self.base_url}")
        logger.info(f"AIxplain Agent ID: {self.agent_id}")
        
        self.headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def generate_response_async(self, system_prompt: str, user_message: str, conversation_history: List[Dict] = None, image_path: Optional[str] = None, session_id: Optional[str] = None, callback=None) -> Dict[str, Any]:
        """
        Generate AI response asynchronously - returns immediately with request info, then calls callback when done
        """
        try:
            logger.info("=== AIXPLAIN AGENT ASYNC REQUEST START ===")
            logger.info(f"Agent ID: {self.agent_id}")
            logger.info(f"User message: {user_message}")
            logger.info(f"Session ID: {session_id}")
            
            # Check if API key and agent ID are configured
            if not self.api_key or not self.agent_id:
                return {
                    'success': False,
                    'error': 'AIxplain API key or Agent ID not configured'
                }
            
            # Step 1: Submit the query to the agent
            post_url = f"{self.base_url}/agents/{self.agent_id}/run"
            
            # Prepare the payload
            payload = {
                'query': user_message
            }
            
            # Add session ID if provided (for conversation continuity)
            if session_id:
                payload['sessionId'] = session_id
            
            logger.info(f"Submitting query to: {post_url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            # POST request to execute the agent
            response = requests.post(
                post_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            logger.info(f"Submit response status: {response.status_code}")
            
            # Accept both 200 and 201 status codes as success
            if response.status_code not in [200, 201]:
                error_msg = f'Agent submission failed with status {response.status_code}'
                try:
                    error_detail = response.json()
                    error_msg += f': {error_detail}'
                    logger.error(f"Submit error detail: {error_detail}")
                except:
                    error_msg += f': {response.text}'
                    logger.error(f"Submit error text: {response.text}")
                
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Get the request ID and session ID
            response_data = response.json()
            request_id = response_data.get("requestId")
            new_session_id = response_data.get("sessionId")
            
            logger.info(f"Response data: {response_data}")
            
            if not request_id:
                logger.error("No request ID received from agent")
                return {
                    'success': False,
                    'error': 'No request ID received from agent'
                }
            
            logger.info(f"Received request ID: {request_id}")
            logger.info(f"Received session ID: {new_session_id}")
            
            # If callback provided, start polling in background
            if callback:
                def poll_for_result():
                    result = self._poll_for_result(request_id, new_session_id or session_id)
                    callback(result)
                
                # Start background thread for polling
                thread = threading.Thread(target=poll_for_result)
                thread.daemon = True
                thread.start()
            
            # Return immediately with request info
            return {
                'success': True,
                'request_id': request_id,
                'session_id': new_session_id or session_id,
                'status': 'submitted'
            }
                
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Agent unexpected error: {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg
            }
        finally:
            logger.info("=== AIXPLAIN AGENT ASYNC REQUEST END ===")
    
    def generate_response_sync(self, system_prompt: str, user_message: str, conversation_history: List[Dict] = None, image_path: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate AI response synchronously - waits for complete response
        """
        try:
            logger.info("=== AIXPLAIN AGENT SYNC REQUEST START ===")
            logger.info(f"Agent ID: {self.agent_id}")
            logger.info(f"User message: {user_message}")
            logger.info(f"Session ID: {session_id}")
            
            # Check if API key and agent ID are configured
            if not self.api_key or not self.agent_id:
                return {
                    'success': False,
                    'error': 'AIxplain API key or Agent ID not configured'
                }
            
            # Step 1: Submit the query to the agent
            post_url = f"{self.base_url}/agents/{self.agent_id}/run"
            
            # Prepare the payload
            payload = {
                'query': user_message
            }
            
            # Add session ID if provided (for conversation continuity)
            if session_id:
                payload['sessionId'] = session_id
            
            logger.info(f"Submitting query to: {post_url}")
            
            # POST request to execute the agent
            response = requests.post(
                post_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            logger.info(f"Submit response status: {response.status_code}")
            
            # Accept both 200 and 201 status codes as success
            if response.status_code not in [200, 201]:
                error_msg = f'Agent submission failed with status {response.status_code}'
                try:
                    error_detail = response.json()
                    error_msg += f': {error_detail}'
                except:
                    error_msg += f': {response.text}'
                
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Get the request ID and session ID
            response_data = response.json()
            request_id = response_data.get("requestId")
            new_session_id = response_data.get("sessionId")
            
            if not request_id:
                return {
                    'success': False,
                    'error': 'No request ID received from agent'
                }
            
            logger.info(f"Received request ID: {request_id}")
            logger.info(f"Received session ID: {new_session_id}")
            
            # Poll for result synchronously
            return self._poll_for_result(request_id, new_session_id or session_id)
                
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Agent unexpected error: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        finally:
            logger.info("=== AIXPLAIN AGENT SYNC REQUEST END ===")
    
    def _poll_for_result(self, request_id: str, session_id: str) -> Dict[str, Any]:
        """
        Poll for the result of an agent request
        """
        get_url = f"{self.base_url}/agents/{request_id}/result"
        max_attempts = 24  # 24 attempts * 5 seconds = 2 minutes max
        attempt = 0
        
        logger.info(f"Polling for result at: {get_url}")
        
        while attempt < max_attempts:
            attempt += 1
            logger.debug(f"Polling attempt {attempt}/{max_attempts}")
            
            try:
                get_response = requests.get(get_url, headers=self.headers, timeout=10)
                
                if get_response.status_code != 200:
                    logger.warning(f"Polling attempt {attempt} failed with status {get_response.status_code}")
                    time.sleep(5)
                    continue
                
                result = get_response.json()
                logger.debug(f"Polling result: {result}")
                
                if result.get("completed"):
                    logger.info(f"Agent completed after {attempt} attempts")
                    
                    # Extract the response content
                    content = self._extract_content_from_result(result)
                    
                    if content:
                        return {
                            'success': True,
                            'content': content,
                            'session_id': session_id,
                            'request_id': request_id,
                            'full_result': result
                        }
                    else:
                        logger.warning("No content found in completed result")
                        logger.debug(f"Full result: {json.dumps(result, indent=2)}")
                        return {
                            'success': False,
                            'error': 'Empty response from agent'
                        }
                else:
                    logger.debug(f"Agent not completed yet, waiting...")
                    time.sleep(5)
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Polling attempt {attempt} failed: {str(e)}")
                time.sleep(5)
                continue
        
        # If we get here, we've exceeded max attempts
        logger.error(f"Agent did not complete within {max_attempts * 5} seconds")
        return {
            'success': False,
            'error': 'Agent response timeout'
        }
    
    def _extract_content_from_result(self, result: Dict) -> Optional[str]:
        """
        Extract content from the agent result response
        """
        try:
            # Try different possible locations for the content
            content = (
                result.get('output', '') or
                result.get('response', '') or
                result.get('message', '') or
                result.get('content', '') or
                result.get('text', '') or
                result.get('data', {}).get('output', '') or
                result.get('data', {}).get('response', '') or
                result.get('result', {}).get('output', '') or
                result.get('result', {}).get('response', '')
            )
            
            # If content is a dict, try to extract text from it
            if isinstance(content, dict):
                content = (
                    content.get('text', '') or
                    content.get('message', '') or
                    content.get('content', '') or
                    str(content)
                )
            
            return content.strip() if content else None
            
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            return None
    
    def run_agent_simple(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Simple method to run your agent with just a message (synchronous)
        """
        return self.generate_response_sync(
            system_prompt="",  # Not used since agent has built-in prompt
            user_message=message,
            conversation_history=None,
            image_path=None,
            session_id=session_id
        )
    
    def initialize_speaker_kit_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Initialize a new speaker kit session with the system prompt
        """
        system_message = """You are an assistant helping a professional speaker create their speaker kit. Your task is to collect the required information for the Cover Page of the kit. Ask each question one at a time, wait for the speaker's response, and be friendly, clear, and professional. Keep the tone supportive and confident. Here's what you need to collect:

Start the conversation like this:

"Hi there! I'm here to help you build your speaker kit. Let's start with the cover page — this will make a bold first impression, so we want it to reflect your brand at its best. Ready? Let's go."

Then ask the following questions one at a time:

"What's your full name, exactly as you'd like it to appear on the cover?"

"In one powerful sentence, what do you help people or companies do?
(Think of it like a tagline – for example: 'I help teams build unstoppable confidence in high-stakes situations.')"

"What are a few short words or labels that describe you professionally?
(For example: 'Keynote Speaker | Author | Leadership Strategist')"

"What's your website or a contact email you'd like included?"

"Please upload 1 great headshot — a clean, professional image of your face"

Instructions -> After collecting all this information, acknowledge the speaker's effort and let them know you're ready to move on to the next section when they are:

"Thanks! That's perfect for the cover page. When you're ready, we can move on to the next part of your speaker kit."

Please start the conversation now."""
        
        return self.run_agent_simple(system_message, session_id)
    
    def initialize_with_system_prompt(self, system_prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Initialize a new conversation by sending the system prompt to AIxplain
        This will make AIxplain respond with the first greeting and question
        """
        try:
            logger.info("=== INITIALIZING WITH SYSTEM PROMPT ===")
            logger.info(f"System prompt length: {len(system_prompt)}")
            logger.info(f"Session ID: {session_id}")
            
            # Check if API key and agent ID are configured
            if not self.api_key or not self.agent_id:
                return {
                    'success': False,
                    'error': 'AIxplain API key or Agent ID not configured'
                }
            
            # Step 1: Submit the system prompt to the agent
            post_url = f"{self.base_url}/agents/{self.agent_id}/run"
            
            # Send the system prompt as the initial query
            payload = {
                # 'systemPrompt': system_prompt,  # Only if AIxplain supports this field!
                'query': (
                    """

                    Instructions -> You are an assistant helping a professional speaker create their speaker kit. Your task is to collect the required information for the Cover Page of the kit. Ask each question one at a time, wait for the speaker’s response, and be friendly, clear, and professional. Keep the tone supportive and confident. Here's what you need to collect:
                    Start the conversation like this:
                    “Hi there!  I’m here to help you build your speaker kit. Let’s start with the cover page — this will make a bold first impression, so we want it to reflect your brand at its best. Ready? Let’s go.”
                    Then ask the following questions one at a time:
                    1. “What’s your full name, exactly as you'd like it to appear on the cover?”


                    2. “In one powerful sentence, what do you help people or companies do?
                    (Think of it like a tagline – for example: ‘I help teams build unstoppable confidence in high-stakes situations.’)”


                    3. “What are a few short words or labels that describe you professionally?
                    (For example: ‘Keynote Speaker | Author | Leadership Strategist’)”


                    4. “What’s your website or a contact email you’d like included?”


                    “Please upload 1 great headshot — a clean, professional image of your face”
                    Instructions -> After collecting all this information, acknowledge the speaker's effort and let them know you're ready to move on to the next section when they are:
                    “Thanks! That’s perfect for the cover page. When you're ready, we can move on to the next part of your speaker kit.”


                    """
                )       # Or an empty string if you want the agent to start
            }
            
            # Add session ID if provided
            if session_id:
                payload['sessionId'] = session_id
            
            logger.info(f"Submitting system prompt to: {post_url}")
            logger.debug(f"Payload keys: {list(payload.keys())}")
            
            # POST request to execute the agent with system prompt
            response = requests.post(
                post_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            logger.info(f"Submit response status: {response.status_code}")
            
            # Accept both 200 and 201 status codes as success
            if response.status_code not in [200, 201]:
                error_msg = f'Agent submission failed with status {response.status_code}'
                try:
                    error_detail = response.json()
                    error_msg += f': {error_detail}'
                    logger.error(f"Submit error detail: {error_detail}")
                except:
                    error_msg += f': {response.text}'
                    logger.error(f"Submit error text: {response.text}")
                
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Get the request ID and session ID
            response_data = response.json()
            request_id = response_data.get("requestId")
            new_session_id = response_data.get("sessionId")
            
            logger.info(f"Response data: {response_data}")
            
            if not request_id:
                logger.error("No request ID received from agent")
                return {
                    'success': False,
                    'error': 'No request ID received from agent'
                }
            
            logger.info(f"Received request ID: {request_id}")
            logger.info(f"Received session ID: {new_session_id}")
            
            # Step 2: Poll for the result
            result = self._poll_for_result(request_id, new_session_id or session_id)
            
            if result['success']:
                logger.info("=== SYSTEM PROMPT INITIALIZATION SUCCESS ===")
                logger.info(f"Agent response: {result['content'][:200]}...")
            else:
                logger.error(f"=== SYSTEM PROMPT INITIALIZATION FAILED ===")
                logger.error(f"Error: {result.get('error')}")
            
            return result
                
        except Exception as e:
            error_msg = f"Unexpected error during initialization: {str(e)}"
            logger.error(f"Initialization error: {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def continue_conversation(self, user_message: str, session_id: str) -> Dict[str, Any]:
        """
        Continue an existing conversation with a user message
        """
        try:
            logger.info("=== CONTINUING CONVERSATION ===")
            logger.info(f"User message: {user_message}")
            logger.info(f"Session ID: {session_id}")
            
            # Check if API key and agent ID are configured
            if not self.api_key or not self.agent_id:
                return {
                    'success': False,
                    'error': 'AIxplain API key or Agent ID not configured'
                }
            
            # Step 1: Submit the user message to continue the conversation
            post_url = f"{self.base_url}/agents/{self.agent_id}/run"
            
            payload = {
                'query': user_message,
                'sessionId': session_id  # This maintains conversation context
            }
            
            logger.info(f"Submitting user message to: {post_url}")
            
            # POST request to continue the conversation
            response = requests.post(
                post_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            logger.info(f"Submit response status: {response.status_code}")
            
            # Accept both 200 and 201 status codes as success
            if response.status_code not in [200, 201]:
                error_msg = f'Agent submission failed with status {response.status_code}'
                try:
                    error_detail = response.json()
                    error_msg += f': {error_detail}'
                except:
                    error_msg += f': {response.text}'
                
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Get the request ID
            response_data = response.json()
            request_id = response_data.get("requestId")
            
            if not request_id:
                return {
                    'success': False,
                    'error': 'No request ID received from agent'
                }
            
            logger.info(f"Received request ID: {request_id}")
            
            # Step 2: Poll for the result
            result = self._poll_for_result(request_id, session_id)
            
            if result['success']:
                logger.info("=== CONVERSATION CONTINUE SUCCESS ===")
                logger.info(f"Agent response: {result['content'][:200]}...")
            else:
                logger.error(f"=== CONVERSATION CONTINUE FAILED ===")
                logger.error(f"Error: {result.get('error')}")
            
            return result
                
        except Exception as e:
            error_msg = f"Unexpected error continuing conversation: {str(e)}"
            logger.error(f"Continue conversation error: {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg
            }
