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
    Get all messages for a conversation
    """
    try:
        logger.info(f"Getting messages for conversation: {conversation_id}")
        
        # Validate UUID format
        try:
            uuid.UUID(str(conversation_id))
        except ValueError:
            logger.error(f"Invalid UUID format: {conversation_id}")
            return Response(
                {'error': 'Invalid conversation ID format'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to get the conversation
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            logger.info(f"Found conversation: {conversation.id}")
        except Conversation.DoesNotExist:
            logger.info(f"Conversation {conversation_id} does not exist, creating and initializing...")
            
            # Create new conversation and initialize with agent greeting
            user = request.user if request.user.is_authenticated else None
            conversation = Conversation.objects.create(
                id=conversation_id,
                user=user,
                title="Speaker Kit Assistant"
            )
            
            # Store in session for anonymous users
            if not user:
                session_conversations = request.session.get('conversations', [])
                session_conversations.append(str(conversation.id))
                request.session['conversations'] = session_conversations
                request.session.modified = True
            
            # Try to get initial AI greeting from your agent
            ai_response = get_initial_agent_greeting(conversation)
            
            if ai_response and ai_response.get('success'):
                # Create initial AI message
                ai_message = Message.objects.create(
                    conversation=conversation,
                    message_type='ai',
                    content=ai_response['content']
                )
                
                # Store session ID for conversation continuity
                if ai_response.get('session_id'):
                    conversation.title = f"Speaker Kit - Session {ai_response['session_id'][:8]}"
                    conversation.save()
                    # Store session ID in Django session
                    request.session[f'aixplain_session_{conversation.id}'] = ai_response['session_id']
                    request.session.modified = True
                
                logger.info(f"Created conversation {conversation.id} with initial agent greeting")
            else:
                logger.info(f"Created conversation {conversation.id} without initial greeting (agent unavailable)")
        
        # Get messages for the conversation
        messages = conversation.messages.all().order_by('timestamp')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        
        return Response({
            'conversation_id': str(conversation.id),
            'title': conversation.title,
            'messages': serializer.data
        })
        
    except Exception as e:
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
        logger.info(f"Request data keys: {list(request.data.keys())}")
        
        # Validate UUID format
        try:
            uuid.UUID(str(conversation_id))
        except ValueError:
            logger.error(f"Invalid UUID format: {conversation_id}")
            return Response(
                {'error': 'Invalid conversation ID format'}, 
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
            
            # Store in session for anonymous users
            if not user:
                session_conversations = request.session.get('conversations', [])
                session_conversations.append(str(conversation.id))
                request.session['conversations'] = session_conversations
                request.session.modified = True
            
            # For new conversations, try to get the initial agent greeting
            ai_response = get_initial_agent_greeting(conversation)
            
            if ai_response and ai_response.get('success'):
                # Create initial AI message
                initial_ai_message = Message.objects.create(
                    conversation=conversation,
                    message_type='ai',
                    content=ai_response['content']
                )
                
                # Store session ID
                if ai_response.get('session_id'):
                    request.session[f'aixplain_session_{conversation.id}'] = ai_response['session_id']
                    request.session.modified = True
                
                logger.info(f"Created initial agent greeting: {initial_ai_message.id}")
        
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
        
        # Create user message
        logger.info("Creating user message...")
        user_message = Message.objects.create(
            conversation=conversation,
            message_type='user',
            content=content,
            image=image
        )
        logger.info(f"Created user message: {user_message.id}")
        
        # Get AIxplain session ID for this conversation
        aixplain_session_id = request.session.get(f'aixplain_session_{conversation.id}')
        logger.info(f"Using AIxplain session ID: {aixplain_session_id}")
        
        # Get agent response to user's message
        logger.info("Getting agent response...")
        ai_response_result = get_agent_response(
            conversation=conversation,
            user_content=content,
            image=image,
            session_id=aixplain_session_id
        )
        
        # Check if we got a successful response
        if ai_response_result['success']:
            ai_content = ai_response_result['content']
            logger.info(f"Agent response length: {len(ai_content)}")
            
            # Update session ID if provided
            if ai_response_result.get('session_id'):
                request.session[f'aixplain_session_{conversation.id}'] = ai_response_result['session_id']
                request.session.modified = True
            
            # Create AI message with actual response
            ai_message = Message.objects.create(
                conversation=conversation,
                message_type='ai',
                content=ai_content
            )
            logger.info(f"Created AI message: {ai_message.id}")
            
            # Serialize messages
            user_message_data = MessageSerializer(user_message, context={'request': request}).data
            ai_message_data = MessageSerializer(ai_message, context={'request': request}).data
            
            logger.info("=== SEND MESSAGE SUCCESS ===")
            return Response({
                'user_message': user_message_data,
                'ai_message': ai_message_data,
                'conversation_id': str(conversation.id)
            }, status=status.HTTP_201_CREATED)
        
        else:
            # Agent failed - create error message
            error_content = "Something went wrong. Please try again."
            logger.error(f"Agent failed: {ai_response_result.get('error', 'Unknown error')}")
            
            # Create AI error message
            ai_message = Message.objects.create(
                conversation=conversation,
                message_type='ai',
                content=error_content
            )
            logger.info(f"Created AI error message: {ai_message.id}")
            
            # Serialize messages
            user_message_data = MessageSerializer(user_message, context={'request': request}).data
            ai_message_data = MessageSerializer(ai_message, context={'request': request}).data
            
            logger.info("=== SEND MESSAGE WITH ERROR ===")
            return Response({
                'user_message': user_message_data,
                'ai_message': ai_message_data,
                'conversation_id': str(conversation.id),
                'agent_error': True
            }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"=== SEND MESSAGE ERROR ===")
        logger.error(f"Error in send_message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response(
            {'error': f'Internal server error: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def get_initial_agent_greeting(conversation):
    """
    Get the initial AI greeting by running your agent with a start message
    Returns the actual response or None if failed
    """
    try:
        logger.info("=== GETTING INITIAL AGENT GREETING ===")
        
        # Import here to avoid circular imports
        try:
            from .services.agent import AIxplainService
            logger.info("Agent service imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import agent service: {e}")
            return None
        
        # Initialize agent service
        ai_service = AIxplainService()
        
        # Send initial message to trigger the greeting
        initial_message = "Hello, I'd like to start building my speaker kit."
        
        logger.info("Calling agent for initial greeting...")
        ai_response = ai_service.run_agent_simple(initial_message)
        
        if ai_response['success']:
            logger.info(f"Initial agent greeting received: {ai_response['content'][:100]}...")
            return ai_response
        else:
            logger.error(f"Agent error for initial greeting: {ai_response.get('error', 'Unknown error')}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting initial agent greeting: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def get_agent_response(conversation, user_content, image=None, session_id=None):
    """
    Get AI response using your AIxplain agent
    Returns dict with success status and content/error
    """
    try:
        logger.info(f"=== AGENT RESPONSE START ===")
        logger.info(f"User content: '{user_content}'")
        logger.info(f"Session ID: {session_id}")
        
        # Import here to avoid circular imports
        try:
            from .services.agent import AIxplainService
            logger.info("Agent service imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import agent service: {e}")
            return {'success': False, 'error': 'Service import failed'}
        
        # Prepare user message
        user_message = user_content
        if image:
            user_message += " [I've uploaded an image]"
        
        logger.info(f"Final user message: '{user_message}'")
        
        # Initialize agent service
        ai_service = AIxplainService()
        
        # Generate agent response with session continuity
        logger.info("Calling agent service...")
        ai_response = ai_service.generate_response(
            system_prompt="",  # Your agent already has the system prompt built-in
            user_message=user_message,
            conversation_history=None,  # Agent maintains context via session ID
            image_path=None,  # Handle images separately if needed
            session_id=session_id
        )
        
        if ai_response['success']:
            logger.info(f"Agent response received: {ai_response['content'][:100]}...")
            return ai_response
        else:
            logger.error(f"Agent error: {ai_response.get('error', 'Unknown error')}")
            return ai_response
            
    except Exception as e:
        logger.error(f"=== AGENT RESPONSE ERROR ===")
        logger.error(f"Error getting agent response: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
        }

@api_view(['GET'])
def get_conversation_starters(request):
    """
    Get conversation starter questions for speaker kit
    """
    try:
        logger.info("Getting conversation starters...")
        
        # Since we auto-initialize conversations with your agent, we can return a simple message
        starters = "Your speaker kit agent is ready! Start a new conversation to begin building your speaker kit."
        
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
            'starters': "Your speaker kit agent is ready! Start a new conversation to begin.",
            'available_topics': ['speaker_kit']
        })
