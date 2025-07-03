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
        # try:
        #     user = self.request.user if self.request.user.is_authenticated else None
        #     if user:
        #         return Conversation.objects.filter(user=user)
        #     else:
        #         # For anonymous users, return conversations from session
        #         session_conversations = self.request.session.get('conversations', [])
        #         return Conversation.objects.filter(id__in=session_conversations)
        # except Exception as e:
        #     logger.error(f"Error in get_queryset: {str(e)}")
        #     return Conversation.objects.none()
        return Conversation.objects.all()
    
    def perform_create(self, serializer):
        try:
            user = self.request.user if self.request.user.is_authenticated else None
            conversation = serializer.save(user=user)
            # Store conversation ID in session for anonymous users
            if not user:
                session_conversations = self.request.session.get('conversations', [])
                conv_id = str(conversation.id)
                if conv_id not in session_conversations:
                    session_conversations.append(conv_id)
                    self.request.session['conversations'] = session_conversations
                    self.request.session.modified = True
        except Exception as e:
            logger.error(f"Error in perform_create: {str(e)}")
            raise

class ConversationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # try:
        #     user = self.request.user if self.request.user.is_authenticated else None
        #     if user:
        #         return Conversation.objects.filter(user=user)
        #     else:
        #         session_conversations = self.request.session.get('conversations', [])
        #         return Conversation.objects.filter(id__in=session_conversations)
        # except Exception as e:
        #     logger.error(f"Error in ConversationDetailView get_queryset: {str(e)}")
        #     return Conversation.objects.none()
        return Conversation.objects.all()

    def perform_destroy(self, instance):
        # Delete all messages related to the conversation
        instance.messages.all().delete()
        instance.delete()

@api_view(['GET'])
def get_conversation_messages(request, conversation_id):
    """
    Get all messages for a conversation - initializes with system prompt if new
    """
    try:
        logger.info(f"=== GET CONVERSATION MESSAGES START ===")
        try:
            uuid_obj = uuid.UUID(str(conversation_id))
        except ValueError as e:
            return Response({'error': 'Invalid conversation ID format'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = Conversation.objects.get(id=conversation_id)
            logger.info(f"Found existing conversation: {conversation.id}")
        except Conversation.DoesNotExist:
            logger.info(f"Conversation {conversation_id} does not exist, creating and initializing...")
            user = request.user if request.user.is_authenticated else None
            conversation = Conversation.objects.create(
                id=conversation_id,
                user=user,
                title="Speaker Kit Assistant"
            )
            # Initialize agent and store session_id in DB
            from .services.agent import AIxplainService
            ai_service = AIxplainService()
            ai_response = ai_service.initialize_conversation()
            session_id = ai_response.get('session_id')
            if session_id:
                conversation.aixplain_session_id = session_id
                conversation.save()
            # Save initial AI message
            Message.objects.create(
                conversation=conversation,
                message_type='ai',
                content=ai_response.get('content', '[No response from agent]')
            )

        # Return all messages
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
        return Response({'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def send_message(request, conversation_id):
    """
    Send a message to a conversation and get agent response
    """
    try:
        logger.info(f"=== SEND MESSAGE START ===")
        try:
            uuid_obj = uuid.UUID(str(conversation_id))
        except ValueError as e:
            return Response({'error': 'Invalid conversation ID format'}, status=status.HTTP_400_BAD_REQUEST)

        content = request.data.get('content', '').strip()
        image = request.FILES.get('image')
        if not content and not image:
            return Response({'error': 'Message content or image is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            user = request.user if request.user.is_authenticated else None
            conversation = Conversation.objects.create(
                id=conversation_id,
                user=user,
                title="Speaker Kit Assistant"
            )
            # Initialize agent and store session_id in DB
            from .services.agent import AIxplainService
            ai_service = AIxplainService()
            ai_response = ai_service.initialize_conversation()
            session_id = ai_response.get('session_id')
            if session_id:
                conversation.aixplain_session_id = session_id
                conversation.save()
            # Save initial AI message
            Message.objects.create(
                conversation=conversation,
                message_type='ai',
                content=ai_response.get('content', '[No response from agent]')
            )

        # Save user message
        user_message = Message.objects.create(
            conversation=conversation,
            message_type='user',
            content=content,
            image=image
        )

        # Always use session_id from DB
        session_id = conversation.aixplain_session_id
        logger.info(f"Using session_id for conversation {conversation.id}: {session_id}")  # <--- ADD HERE

        if not session_id:
            # Re-initialize if missing
            from .services.agent import AIxplainService
            ai_service = AIxplainService()
            ai_response = ai_service.initialize_conversation()
            session_id = ai_response.get('session_id')
            if session_id:
                conversation.aixplain_session_id = session_id
                conversation.save()

        # Get agent response
        from .services.agent import AIxplainService
        ai_service = AIxplainService()
        ai_response = ai_service.continue_conversation(content, session_id)
        logger.info(f"Agent returned session_id: {ai_response.get('session_id')}")  # <--- ADD HERE

        # Update session_id if changed
        new_session_id = ai_response.get('session_id')
        if new_session_id and new_session_id != conversation.aixplain_session_id:
            conversation.aixplain_session_id = new_session_id
            conversation.save()

        # Save AI message
        ai_message = Message.objects.create(
            conversation=conversation,
            message_type='ai',
            content=ai_response.get('content', '[No response from agent]')
        )

        # Serialize and return
        user_message_data = MessageSerializer(user_message, context={'request': request}).data
        ai_message_data = MessageSerializer(ai_message, context={'request': request}).data
        return Response({
            'user_message': user_message_data,
            'ai_message': ai_message_data,
            'conversation_id': str(conversation.id)
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Critical error in send_message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({'error': f'Critical server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def initialize_conversation_with_system_prompt(conversation, request):
    """
    Initialize a new conversation by sending a greeting to the agent (uses agent's built-in instructions)
    """
    try:
        logger.info("=== INITIALIZING CONVERSATION WITH AGENT SDK ===")
        from .services.agent import AIxplainService
        ai_service = AIxplainService()
        ai_response = ai_service.initialize_conversation()
        session_id = ai_response.get('session_id')
        if session_id:
            conversation.aixplain_session_id = session_id
            conversation.save()
        if ai_response and ai_response.get('success'):
            logger.info(f"Agent initialization successful")
            content = ai_response.get('content')
            if isinstance(content, str):
                logger.info(f"Agent response preview: {content[:200]}...")
            else:
                logger.info(f"Agent response preview: {content}")
            return ai_response
        else:
            error_msg = ai_response.get('error', 'Unknown error') if ai_response else 'No response'
            logger.error(f"Agent initialization failed: {error_msg}")
            return None
    except Exception as e:
        logger.error(f"Critical error initializing conversation: {str(e)}")
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
