import os
import re
import json
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


class AiAssistant:
    def __init__(self, api_endpoint, api_key):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def call_with_prompt(self, prompt, temperature=0.3, max_tokens=500):
        url = f"{self.api_endpoint}?key={self.api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=15)
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            return f"Error: {e}"


class PromptChainProcessor:
    CATEGORIES = """
- Account Opening
- Billing Issue
- Account Access
- Transaction Inquiry
- Card Services
- Account Statement
- Loan Inquiry
- General Information
"""
    
    def __init__(self, ai_assistant):
        self.ai = ai_assistant
    
    def interpret_intent(self, user_input):
        prompt = f"Interpret customer intent briefly.\n\nCustomer: {user_input}\n\nProvide concise interpretation."
        return self.ai.call_with_prompt(prompt, temperature=0.2, max_tokens=150)
    
    def select_category(self, interpreted_message):
        prompt = f"Select the single most appropriate category.\n\nCategories:\n{self.CATEGORIES}\n\nRequest: {interpreted_message}\n\nReturn ONLY the category name."
        return self.ai.call_with_prompt(prompt, temperature=0.1, max_tokens=50)
    
    def extract_details(self, user_input, category, context_data):
        collected = json.dumps(context_data) if context_data else "None"
        prompt = f"""Banking request handler.

Category: {category}
Customer: {user_input}
Collected: {collected}

Return JSON: {{"status": "needs_info" or "ready", "extracted_data": {{}}, "response_to_user": "..."}}"""
        
        return self.ai.call_with_prompt(prompt, temperature=0.2, max_tokens=300)
    
    def generate_final_response(self, category, context_data):
        collected = json.dumps(context_data)
        prompt = f"Generate brief professional banking response.\n\nCategory: {category}\nInfo: {collected}\n\nConfirm action and offer help."
        return self.ai.call_with_prompt(prompt, temperature=0.3, max_tokens=200)


def run_prompt_chain(customer_query, session_state):
    user_input = customer_query.strip()
    if not user_input:
        return "Please enter a message."
    
    # First message - get category
    if 'category' not in session_state:
        interpreted = session_state.processor.interpret_intent(user_input)
        category = session_state.processor.select_category(interpreted)
        session_state.category = category
        session_state.context_data = {}
    
    # Extract details
    extraction_result = session_state.processor.extract_details(
        user_input, 
        session_state.category, 
        session_state.context_data
    )
    
    # Parse JSON response
    match = re.search(r'\{.*\}', extraction_result, re.DOTALL)
    if match:
        try:
            response_data = json.loads(match.group())
            
            # Update context
            if response_data.get('extracted_data'):
                session_state.context_data.update(response_data['extracted_data'])
            
            # Generate response
            if response_data.get('status') == 'ready':
                return session_state.processor.generate_final_response(
                    session_state.category, 
                    session_state.context_data
                )
            else:
                return response_data.get('response_to_user', 'Could you provide more details?')
        except:
            return extraction_result
    
    return extraction_result


# Streamlit App
st.title("🏦 Bank AI Assistant")

# Initialize
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Welcome. I'm your secure AI banking assistant. How can I help you today?"}
    ]
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        st.error("GEMINI_API_KEY not found in environment")
        st.stop()
    
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    st.session_state.ai_assistant = AiAssistant(api_url, gemini_api_key)
    st.session_state.processor = PromptChainProcessor(st.session_state.ai_assistant)

# Display chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("How can I help you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Typing..."):
            response = run_prompt_chain(prompt, st.session_state)
            st.markdown(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()