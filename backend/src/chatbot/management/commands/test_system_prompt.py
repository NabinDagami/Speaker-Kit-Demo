from django.core.management.base import BaseCommand
from chatbot.services.agent import AIxplainService
from chatbot.prompts import get_speaker_kit_system_prompt
import json

class Command(BaseCommand):
    help = 'Test system prompt initialization with AIxplain'

    def handle(self, *args, **options):
        try:
            # Get the system prompt
            system_prompt = get_speaker_kit_system_prompt()
            
            self.stdout.write("=" * 60)
            self.stdout.write("Testing System Prompt Initialization")
            self.stdout.write("=" * 60)
            
            self.stdout.write(f"📝 System prompt length: {len(system_prompt)} characters")
            self.stdout.write(f"📝 System prompt preview:")
            self.stdout.write(f"{system_prompt[:300]}...")
            self.stdout.write("")
            
            # Initialize the service
            ai_service = AIxplainService()
            
            self.stdout.write("🚀 Sending system prompt to AIxplain...")
            self.stdout.write("")
            
            # Test system prompt initialization
            response = ai_service.initialize_with_system_prompt(system_prompt)
            
            self.stdout.write(f"✅ Success: {response['success']}")
            
            if response['success']:
                self.stdout.write(
                    self.style.SUCCESS('🎉 System Prompt Initialization Successful!')
                )
                self.stdout.write("")
                self.stdout.write("🤖 Agent Response:")
                self.stdout.write("-" * 40)
                self.stdout.write(f"{response['content']}")
                self.stdout.write("-" * 40)
                self.stdout.write("")
                self.stdout.write(f"📋 Session ID: {response.get('session_id', 'None')}")
                self.stdout.write(f"🆔 Request ID: {response.get('request_id', 'None')}")
                
                # Test continuing the conversation
                if response.get('session_id'):
                    self.stdout.write("")
                    self.stdout.write("🔄 Testing conversation continuation...")
                    
                    continue_response = ai_service.continue_conversation(
                        user_message="My name is John Doe",
                        session_id=response['session_id']
                    )
                    
                    if continue_response['success']:
                        self.stdout.write(
                            self.style.SUCCESS('✅ Conversation continuation successful!')
                        )
                        self.stdout.write("")
                        self.stdout.write("🤖 Agent Follow-up Response:")
                        self.stdout.write("-" * 40)
                        self.stdout.write(f"{continue_response['content']}")
                        self.stdout.write("-" * 40)
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'❌ Conversation continuation failed: {continue_response["error"]}')
                        )
                
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ System Prompt Initialization Failed: {response["error"]}')
                )
            
            self.stdout.write("=" * 60)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'💥 Test failed: {str(e)}')
            )
