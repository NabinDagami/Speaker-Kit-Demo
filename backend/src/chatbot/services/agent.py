import requests
import json
from django.conf import settings
from typing import Optional, Dict, Any, List
import logging
import traceback
import time

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
    
    def generate_response(self, system_prompt: str, user_message: str, conversation_history: List[Dict] = None, image_path: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate AI response using your AIxplain agent with the correct async pattern
        """
        try:
            logger.info("=== AIXPLAIN AGENT REQUEST START ===")
            logger.info(f"Agent ID: {self.agent_id}")
            logger.info(f"User message: {user_message}")
            logger.info(f"Session ID: {session_id}")
            
            # Check if API key and agent ID are configured
            if not self.api_key:
                logger.error("AIxplain API key not configured")
                return {
                    'success': False,
                    'error': 'AIxplain API key not configured'
                }
            
            if not self.agent_id:
                logger.error("AIxplain Agent ID not configured")
                return {
                    'success': False,
                    'error': 'AIxplain Agent ID not configured'
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
                logger.debug(f"Response data: {response_data}")
                return {
                    'success': False,
                    'error': 'No request ID received from agent'
                }
            
            logger.info(f"Received request ID: {request_id}")
            logger.info(f"Received session ID: {new_session_id}")
            
            # Step 2: Poll for the result
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
                                'session_id': new_session_id or session_id,
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
                
        except requests.exceptions.Timeout:
            error_msg = "Agent request timeout"
            logger.error(f"Agent timeout: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(f"Agent connection error: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"Request exception: {str(e)}"
            logger.error(f"Agent request error: {error_msg}")
            return {
                'success': False,
                'error': error_msg
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
            logger.info("=== AIXPLAIN AGENT REQUEST END ===")
    
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
        Simple method to run your agent with just a message
        """
        return self.generate_response(
            system_prompt="",  # Not used since agent has built-in prompt
            user_message=message,
            conversation_history=None,
            image_path=None,
            session_id=session_id
        )
