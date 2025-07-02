from rest_framework import generics, status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.http import Http404
from .models import Conversation, Message
from .serializers import ConversationSerializer, ConversationListSerializer, MessageSerializer
from .prompts import get_speaker_kit_system_prompt
import uuid
import logging
import json
import traceback

# Set up logging
logger = logging.getLogger(__name__)

class ConversationListCreateView(generics.ListCreateAPIView):
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ConversationListSerializer
        return ConversationSerializer
    
    def get_queryset(self):
        try:
            user = self.request.user if self.request.user.is_authenticated else None
            if user:
                return Conversation.objects.filter(user=user)
            else:
                # For anonymous users, return conversations from session
                session_conversations = self.request.session.get('conversations', [])
                return Conversation.objects.filter(id__in=session_conversations)
        except Exception as e:
            logger.error(f"Error in get_queryset: {str(e)}")
            return Conversation.objects.none()
    
    def perform_create(self, serializer):
        try:
            user = self.request.user if self.request.user.is_authenticated else None
            conversation = serializer.save(user=user)
            
            # Store conversation ID in session for anonymous users
            if not user:
                session_conversations = self.request.session.get('conversations', [])
                session_conversations.append(str(conversation.id))
                self.request.session['conversations'] = session_conversations
                self.request.session.modified = True
        except Exception as e:
            logger.error(f"Error in perform_create: {str(e)}")
            raise

class ConversationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        try:
            user = self.request.user if self.request.user.is_authenticated else None
            if user:
                return Conversation.objects.filter(user=user)
            else:
                session_conversations = self.request.session.get('conversations', [])
                return Conversation.objects.filter(id__in=session_conversations)
        except Exception as e:
            logger.error(f"Error in ConversationDetailView get_queryset: {str(e)}")
            return Conversation.objects.none()

@api_view(['GET'])
def get_conversation_messages(request, conversation_id):
    """
    Get all messages for a conversation - initializes with system prompt if new
    """
    try:
        logger.info(f"=== GET CONVERSATION MESSAGES START ===")
        logger.info(f"Conversation ID: {conversation_id}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        # Validate UUID format
        try:
            uuid_obj = uuid.UUID(str(conversation_id))
            logger.info(f"Valid UUID: {uuid_obj}")
        except ValueError as e:
            logger.error(f"Invalid UUID format: {conversation_id} - {str(e)}")
            return Response(
                {'error': 'Invalid conversation ID format', 'details': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to get the conversation
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            logger.info(f"Found existing conversation: {conversation.id}")
            
            # Check if conversation has any messages
            message_count = conversation.messages.count()
            logger.info(f"Conversation has {message_count} messages")
            
        except Conversation.DoesNotExist:
            logger.info(f"Conversation {conversation_id} does not exist, creating and initializing...")
            
            # Create new conversation
            user = request.user if request.user.is_authenticated else None
            conversation = Conversation.objects.create(
                id=conversation_id,
                user=user,
                title="Speaker Kit Assistant"
            )
            logger.info(f"Created new conversation: {conversation.id}")
            
            # Store in session for anonymous users
            if not user:
                session_conversations = request.session.get('conversations', [])
                session_conversations.append(str(conversation.id))
                request.session['conversations'] = session_conversations
                request.session.modified = True
                logger.info(f"Stored conversation in session")
            
            # Initialize with system prompt from prompts.py
            logger.info("Initializing conversation with system prompt from prompts.py")
            ai_response = initialize_conversation_with_system_prompt(conversation, request)
            
            if ai_response and ai_response.get('success'):
                # Create initial AI message with the agent's response
                ai_message = Message.objects.create(
                    conversation=conversation,
                    message_type='ai',
                    content=ai_response['content']
                )
                logger.info(f"Created initial AI message: {ai_message.id}")
                
                # Store session ID for conversation continuity
                if ai_response.get('session_id'):
                    session_key = f'aixplain_session_{conversation.id}'
                    request.session[session_key] = ai_response['session_id']
                    request.session.modified = True
                    logger.info(f"Stored AIxplain session ID: {ai_response['session_id']}")
                
                logger.info(f"System prompt initialization successful")
            else:
                logger.warning(f"System prompt initialization failed or returned no response")
                # Create a fallback message
                fallback_message = Message.objects.create(
                    conversation=conversation,
                    message_type='ai',
                    content="Hi there! I'm here to help you build your speaker kit. Let's start with the cover page — this will make a bold first impression, so we want it to reflect your brand at its best. Ready? Let's go.\n\nWhat's your full name, exactly as you'd like it to appear on the cover?"
                )
                logger.info(f"Created fallback AI message: {fallback_message.id}")
        
        # Get messages for the conversation
        messages = conversation.messages.all().order_by('timestamp')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        
        response_data = {
            'conversation_id': str(conversation.id),
            'title': conversation.title,
            'messages': serializer.data
        }
        
        logger.info(f"=== GET CONVERSATION MESSAGES SUCCESS ===")
        logger.info(f"Returning {len(serializer.data)} messages")
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"=== GET CONVERSATION MESSAGES ERROR ===")
        logger.error(f"Error in get_conversation_messages: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response(
            {'error': f'Internal server error: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def send_message(request, conversation_id):
    """
    Send a message to a conversation and get agent response
    """
    try:
        logger.info(f"=== SEND MESSAGE START ===")
        logger.info(f"Conversation ID: {conversation_id}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request content type: {request.content_type}")
        logger.info(f"Request data keys: {list(request.data.keys())}")
        logger.info(f"Request FILES keys: {list(request.FILES.keys())}")
        
        # Validate UUID format
        try:
            uuid_obj = uuid.UUID(str(conversation_id))
            logger.info(f"Valid UUID: {uuid_obj}")
        except ValueError as e:
            logger.error(f"Invalid UUID format: {conversation_id} - {str(e)}")
            return Response(
                {'error': 'Invalid conversation ID format', 'details': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get message content and image
        content = request.data.get('content', '').strip()
        image = request.FILES.get('image')
        
        logger.info(f"Message content: '{content}'")
        logger.info(f"Image provided: {image is not None}")
        
        if not content and not image:
            logger.error("No content or image provided")
            return Response(
                {'error': 'Message content or image is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create conversation
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            logger.info(f"Found existing conversation: {conversation.id}")
        except Conversation.DoesNotExist:
            logger.info(f"Creating new conversation: {conversation_id}")
            # Create new conversation if it doesn't exist
            user = request.user if request.user.is_authenticated else None
            conversation = Conversation.objects.create(
                id=conversation_id,
                user=user,
                title="Speaker Kit Assistant"
            )
            logger.info(f"Created new conversation: {conversation.id}")
            
            # Store in session for anonymous users
            if not user:
                session_conversations = request.session.get('conversations', [])
                session_conversations.append(str(conversation.id))
                request.session['conversations'] = session_conversations
                request.session.modified = True
                logger.info(f"Stored conversation in session")
            
            # For new conversations, initialize with system prompt
            logger.info("Initializing new conversation with system prompt")
            ai_response = initialize_conversation_with_system_prompt(conversation, request)
            
            if ai_response and ai_response.get('success'):
                # Create initial AI message
                initial_ai_message = Message.objects.create(
                    conversation=conversation,
                    message_type='ai',
                    content=ai_response['content']
                )
                logger.info(f"Created initial system prompt message: {initial_ai_message.id}")
                
                # Store session ID
                if ai_response.get('session_id'):
                    session_key = f'aixplain_session_{conversation.id}'
                    request.session[session_key] = ai_response['session_id']
                    request.session.modified = True
                    logger.info(f"Stored AIxplain session ID: {ai_response['session_id']}")
            else:
                logger.warning("System prompt initialization failed, continuing without it")
        
        # Create user message
        logger.info("Creating user message...")
        try:
            user_message = Message.objects.create(
                conversation=conversation,
                message_type='user',
                content=content,
                image=image
            )
            logger.info(f"Created user message: {user_message.id}")
        except Exception as e:
            logger.error(f"Error creating user message: {str(e)}")
            return Response(
                {'error': f'Failed to create user message: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Get AIxplain session ID for this conversation
        session_key = f'aixplain_session_{conversation.id}'
        aixplain_session_id = request.session.get(session_key)
        logger.info(f"Using AIxplain session ID: {aixplain_session_id}")

        # --- FIX: Re-initialize session if missing ---
        if not aixplain_session_id:
            logger.warning("Session ID missing, attempting to re-initialize with system prompt")
            ai_response = initialize_conversation_with_system_prompt(conversation, request)
            if ai_response and ai_response.get('session_id'):
                request.session[session_key] = ai_response['session_id']
                request.session.modified = True
                aixplain_session_id = ai_response['session_id']
                logger.info(f"Re-initialized and stored AIxplain session ID: {aixplain_session_id}")
            else:
                logger.error("Failed to re-initialize session with system prompt")
        # --- END FIX ---

        
        # Get agent response to user's message
        logger.info("Getting agent response...")
        ai_response_result = continue_conversation_with_agent(
            conversation=conversation,
            user_content=content,
            image=image,
            session_id=aixplain_session_id
        )
        
        # Check if we got a successful response
        if ai_response_result and ai_response_result.get('success'):
            ai_content = ai_response_result['content']
            logger.info(f"Agent response length: {len(ai_content)}")
            
            # Update session ID if provided
            if ai_response_result.get('session_id'):
                request.session[session_key] = ai_response_result['session_id']
                request.session.modified = True
                logger.info(f"Updated AIxplain session ID: {ai_response_result['session_id']}")
            
            # Create AI message with actual response
            try:
                ai_message = Message.objects.create(
                    conversation=conversation,
                    message_type='ai',
                    content=ai_content
                )
                logger.info(f"Created AI message: {ai_message.id}")
            except Exception as e:
                logger.error(f"Error creating AI message: {str(e)}")
                return Response(
                    {'error': f'Failed to create AI message: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Serialize messages
            try:
                user_message_data = MessageSerializer(user_message, context={'request': request}).data
                ai_message_data = MessageSerializer(ai_message, context={'request': request}).data
                
                response_data = {
                    'user_message': user_message_data,
                    'ai_message': ai_message_data,
                    'conversation_id': str(conversation.id)
                }
                
                logger.info("=== SEND MESSAGE SUCCESS ===")
                return Response(response_data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error serializing messages: {str(e)}")
                return Response(
                    {'error': f'Failed to serialize messages: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        else:
            # Agent failed - create error message
            error_content = "Something went wrong. Please try again."
            error_details = ai_response_result.get('error', 'Unknown error') if ai_response_result else 'No response from agent'
            logger.error(f"Agent failed: {error_details}")
            
            # Create AI error message
            try:
                ai_message = Message.objects.create(
                    conversation=conversation,
                    message_type='ai',
                    content=error_content
                )
                logger.info(f"Created AI error message: {ai_message.id}")
            except Exception as e:
                logger.error(f"Error creating AI error message: {str(e)}")
                return Response(
                    {'error': f'Failed to create error message: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Serialize messages
            try:
                user_message_data = MessageSerializer(user_message, context={'request': request}).data
                ai_message_data = MessageSerializer(ai_message, context={'request': request}).data
                
                response_data = {
                    'user_message': user_message_data,
                    'ai_message': ai_message_data,
                    'conversation_id': str(conversation.id),
                    'agent_error': True,
                    'agent_error_details': error_details
                }
                
                logger.info("=== SEND MESSAGE WITH ERROR ===")
                return Response(response_data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error serializing error messages: {str(e)}")
                return Response(
                    {'error': f'Failed to serialize error messages: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
    except Exception as e:
        logger.error(f"=== SEND MESSAGE CRITICAL ERROR ===")
        logger.error(f"Critical error in send_message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response(
            {'error': f'Critical server error: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def initialize_conversation_with_system_prompt(conversation, request):
    """
    Initialize a new conversation by sending the system prompt from prompts.py to AIxplain
    """
    try:
        logger.info("=== INITIALIZING CONVERSATION WITH SYSTEM PROMPT ===")
        
        # Import here to avoid circular imports
        try:
            from .services.agent import AIxplainService
            logger.info("Agent service imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import agent service: {e}")
            return None
        
        # Get the system prompt from prompts.py
        try:
            system_prompt = get_speaker_kit_system_prompt()
            logger.info(f"System prompt length: {len(system_prompt)}")
            logger.info(f"System prompt preview: {system_prompt[:200]}...")
        except Exception as e:
            logger.error(f"Failed to get system prompt: {str(e)}")
            return None
        
        # Initialize agent service
        try:
            ai_service = AIxplainService()
            logger.info("AIxplain service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AIxplain service: {str(e)}")
            return None
        
        # Send system prompt to AIxplain to initialize the conversation
        logger.info("Sending system prompt to AIxplain...")
        try:
            ai_response = ai_service.initialize_with_system_prompt(system_prompt)
            
            if ai_response and ai_response.get('success'):
                logger.info(f"System prompt initialization successful")
                logger.info(f"Agent response preview: {ai_response['content'][:200]}...")
                return ai_response
            else:
                error_msg = ai_response.get('error', 'Unknown error') if ai_response else 'No response'
                logger.error(f"System prompt initialization failed: {error_msg}")
                return None
                
        except Exception as e:
            logger.error(f"Exception during system prompt initialization: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
            
    except Exception as e:
        logger.error(f"Critical error initializing conversation with system prompt: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def continue_conversation_with_agent(conversation, user_content, image=None, session_id=None):
    """
    Continue the conversation by sending user message to AIxplain
    """
    try:
        logger.info(f"=== CONTINUING CONVERSATION WITH AGENT ===")
        logger.info(f"User content: '{user_content}'")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Image provided: {image is not None}")
        
        # Import here to avoid circular imports
        try:
            from .services.agent import AIxplainService
            logger.info("Agent service imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import agent service: {e}")
            return {'success': False, 'error': 'Service import failed'}
        
        # Check if we have a session ID
        if not session_id:
            logger.error("No session ID provided - cannot continue conversation")
            return {'success': False, 'error': 'No session ID - conversation not properly initialized'}
        
        # Prepare user message
        user_message = user_content
        if image:
            user_message += " [I've uploaded an image]"
        
        logger.info(f"Final user message: '{user_message}'")
        
        # Initialize agent service
        try:
            ai_service = AIxplainService()
            logger.info("AIxplain service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AIxplain service: {str(e)}")
            return {'success': False, 'error': f'Service initialization failed: {str(e)}'}
        
        # Continue conversation with user message
        logger.info("Continuing conversation with agent...")
        try:
            ai_response = ai_service.continue_conversation(
                user_message=user_message,
                session_id=session_id
            )
            
            if ai_response and ai_response.get('success'):
                logger.info(f"Agent response received successfully")
                logger.info(f"Response preview: {ai_response['content'][:100]}...")
                return ai_response
            else:
                error_msg = ai_response.get('error', 'Unknown error') if ai_response else 'No response'
                logger.error(f"Agent error: {error_msg}")
                return ai_response or {'success': False, 'error': 'No response from agent'}
                
        except Exception as e:
            logger.error(f"Exception during conversation continuation: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': f'Agent communication failed: {str(e)}'}
            
    except Exception as e:
        logger.error(f"=== CONTINUE CONVERSATION CRITICAL ERROR ===")
        logger.error(f"Critical error continuing conversation: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': f'Critical error: {str(e)}'
        }

@api_view(['GET'])
def get_conversation_starters(request):
    """
    Get conversation starter information for speaker kit
    """
    try:
        logger.info("Getting conversation starters...")
        
        # Since we auto-initialize conversations with system prompt, return appropriate message
        starters = "Your Speaker Kit Assistant is ready! Start a new conversation and the assistant will automatically begin with the cover page questions."
        
        return Response({
            'topic': 'speaker_kit',
            'starters': starters,
            'available_topics': ['speaker_kit']
        })
        
    except Exception as e:
        logger.error(f"Error in get_conversation_starters: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({
            'topic': 'speaker_kit',
            'starters': "Your Speaker Kit Assistant is ready! Start a new conversation to begin.",
            'available_topics': ['speaker_kit']
        })
