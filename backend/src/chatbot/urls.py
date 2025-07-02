from django.urls import path
from . import views

urlpatterns = [
    # Conversation endpoints
    path('conversations/', views.ConversationListCreateView.as_view(), name='conversation-list-create'),
    path('conversations/<uuid:pk>/', views.ConversationDetailView.as_view(), name='conversation-detail'),
    
    # Message endpoints
    path('conversations/<uuid:conversation_id>/messages/', views.send_message, name='send-message'),
    path('conversations/<uuid:conversation_id>/messages/list/', views.get_conversation_messages, name='get-messages'),
    
    # Conversation starters
    path('conversation-starters/', views.get_conversation_starters, name='conversation-starters'),
]
