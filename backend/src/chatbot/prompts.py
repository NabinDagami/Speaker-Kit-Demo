"""
Conversation prompts and question templates for the AI chat system.
This file contains the system prompt for AIxplain.
"""

# The exact system prompt that goes to AIxplain
SPEAKER_KIT_SYSTEM_PROMPT = """Instructions -> You are an assistant helping a professional speaker create their speaker kit. Your task is to collect the required information for the Cover Page of the kit. Ask each question one at a time, wait for the speaker's response, and be friendly, clear, and professional. Keep the tone supportive and confident. Here's what you need to collect:

Start the conversation like this:

"Hi there!  I'm here to help you build your speaker kit. Let's start with the cover page — this will make a bold first impression, so we want it to reflect your brand at its best. Ready? Let's go."

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
"""

# Fallback responses if AIxplain is not available
# SPEAKER_KIT_FALLBACK_RESPONSES = {
#     "initial": """Hi there! I'm here to help you build your speaker kit. Let's start with the cover page — this will make a bold first impression, so we want it to reflect your brand at its best. Ready? Let's go.

# What's your full name, exactly as you'd like it to appear on the cover?""",
    
#     "questions": [
#         "What's your full name, exactly as you'd like it to appear on the cover?",
#         """In one powerful sentence, what do you help people or companies do?
# (Think of it like a tagline – for example: 'I help teams build unstoppable confidence in high-stakes situations.')""",
#         """What are a few short words or labels that describe you professionally?
# (For example: 'Keynote Speaker | Author | Leadership Strategist')""",
#         "What's your website or a contact email you'd like included?",
#         "Please upload 1 great headshot — a clean, professional image of your face"
#     ],
    
#     "acknowledgments": [
#         "Perfect! Nice to meet you, {}.\n\n",
#         "That's a powerful tagline! I love it.\n\n",
#         "Excellent professional credentials!\n\n", 
#         "Great contact information!\n\n",
#         "Thank you for the headshot!\n\n"
#     ],
    
#     "completion": "Thanks! That's perfect for the cover page. When you're ready, we can move on to the next part of your speaker kit."
# }

def get_speaker_kit_system_prompt():
    """
    Get the exact system prompt for AIxplain
    """
    return SPEAKER_KIT_SYSTEM_PROMPT

# def get_fallback_speaker_kit_response(conversation, user_content, is_first_interaction):
#     """
#     Fallback response when AIxplain is not available
#     """
#     if is_first_interaction:
#         return SPEAKER_KIT_FALLBACK_RESPONSES["initial"]
    
#     # Count AI messages to determine which question to ask next
#     ai_messages = conversation.messages.filter(message_type='ai').count()
#     current_step = ai_messages - 1  # -1 because we're about to create a new AI message
    
#     questions = SPEAKER_KIT_FALLBACK_RESPONSES["questions"]
#     acknowledgments = SPEAKER_KIT_FALLBACK_RESPONSES["acknowledgments"]
    
#     if current_step < len(questions) - 1:
#         response = ""
#         if current_step >= 0:
#             if current_step == 0:
#                 response = acknowledgments[current_step].format(user_content)
#             else:
#                 response = acknowledgments[current_step]
#         response += questions[current_step + 1]
#         return response
#     else:
#         return SPEAKER_KIT_FALLBACK_RESPONSES["completion"]

# def get_initial_questions(topic: str = "speaker_kit") -> str:
#     """
#     Get initial questions to start a conversation.
#     """
#     return SPEAKER_KIT_FALLBACK_RESPONSES["initial"]
