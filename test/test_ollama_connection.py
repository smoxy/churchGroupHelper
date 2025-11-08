"""
Test script for Ollama Cloud API integration.

This script tests the connection to Ollama Cloud API and verifies
that the gpt-oss:20b model is accessible.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_ollama_connection():
    """Test connection to Ollama Cloud API."""
    
    # Check if API key is set
    api_key = os.getenv('OLLAMA_API_KEY')
    if not api_key:
        print("❌ OLLAMA_API_KEY not found in environment variables")
        print("   Please set it in your .env file")
        return False
    
    print(f"✓ OLLAMA_API_KEY found: {api_key[:10]}...{api_key[-4:]}")
    
    # Try importing ollama
    try:
        from ollama import Client
        print("✓ ollama package imported successfully")
    except ImportError:
        print("❌ Failed to import ollama package")
        print("   Run: pip install ollama")
        return False
    
    # Try connecting to Ollama Cloud
    try:
        print("\nConnecting to Ollama Cloud API...")
        client = Client(
            host="https://ollama.com",
            headers={'Authorization': 'Bearer ' + api_key}
        )
        print("✓ Client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return False
    
    # Try a simple test request
    try:
        print("\nTesting gpt-oss:20b model with a simple query...")
        messages = [
            {
                'role': 'user',
                'content': 'Say "Hello, ChurchGroupHelper!" in exactly those words.',
            },
        ]
        
        response = ""
        for part in client.chat('gpt-oss:20b', messages=messages, stream=True):
            response += part['message']['content']
            print(part['message']['content'], end='', flush=True)
        
        print("\n\n✓ Successfully received response from gpt-oss:20b")
        print(f"  Response: {response}")
        
        if "Hello" in response or "hello" in response:
            print("✓ Model responded appropriately")
        else:
            print("⚠ Model response seems unexpected")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to get response from model: {e}")
        return False

def test_summarization_prompt():
    """Test a more complex summarization-like prompt."""
    
    api_key = os.getenv('OLLAMA_API_KEY')
    if not api_key:
        print("❌ Cannot test without OLLAMA_API_KEY")
        return False
    
    try:
        from ollama import Client
        
        print("\n" + "="*60)
        print("Testing summarization-like prompt...")
        print("="*60 + "\n")
        
        client = Client(
            host="https://ollama.com",
            headers={'Authorization': 'Bearer ' + api_key}
        )
        
        # Simulate a simple conversation
        conversation = """
John (ID: 12345) at 14:30:
Hi everyone! Should we meet next week?

Maria (ID: 67890) at 14:31:
Yes, that sounds good!

John (ID: 12345) at 14:32:
Great! How about Tuesday?

Maria (ID: 67890) at 14:33:
Tuesday works for me
        """
        
        prompt = (
            "Summarize this conversation in English. Include important details "
            "and cite speakers using this format: "
            '<a href="tg://user?id=USER_ID">"quote"</a>\n\n'
            f"{conversation}"
        )
        
        messages = [{'role': 'user', 'content': prompt}]
        
        print("Generating summary...\n")
        summary = ""
        for part in client.chat('gpt-oss:20b', messages=messages, stream=True):
            content = part['message']['content']
            summary += content
            print(content, end='', flush=True)
        
        print("\n\n✓ Successfully generated summary")
        
        # Check if citations are present
        if '<a href="tg://user?id=' in summary:
            print("✓ Citations are properly formatted")
        else:
            print("⚠ Citations might not be in the expected format")
            print("  This is okay, you can adjust the prompt in bot.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to test summarization: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Ollama Cloud API - Connection Test")
    print("="*60 + "\n")
    
    # Test basic connection
    if not test_ollama_connection():
        print("\n❌ Basic connection test failed")
        sys.exit(1)
    
    print("\n✓ Basic connection test passed")
    
    # Test summarization
    if not test_summarization_prompt():
        print("\n⚠ Summarization test failed, but basic connection works")
        print("  You can still use the bot, but check the prompt format")
        sys.exit(0)
    
    print("\n" + "="*60)
    print("✓ All tests passed! The bot is ready to use.")
    print("="*60)
