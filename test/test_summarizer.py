"""
Test script for the LangChain-based summarizer.
Run this to verify the installation and basic functionality.
"""
import os
import sys
from datetime import datetime

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_imports():
    """Test that all required modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        from summarizer import create_summarizer
        print("✅ summarizer module imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import summarizer: {e}")
        return False
    
    try:
        from langchain_core.prompts import ChatPromptTemplate
        print("✅ langchain_core imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import langchain_core: {e}")
        print("   Run: pip install langchain langchain-core langchain-community")
        return False
    
    return True


def test_summarizer_creation():
    """Test that summarizer can be created."""
    print("\n🔍 Testing summarizer creation...")
    
    from summarizer import create_summarizer
    
    # Use a dummy API key for testing structure
    try:
        summarizer = create_summarizer("test_api_key")
        print("✅ Summarizer created successfully")
        print(f"   Model: gpt-oss:120b")
        print(f"   Chain type: {type(summarizer.chain).__name__}")
        return True
    except Exception as e:
        print(f"❌ Failed to create summarizer: {e}")
        return False


def test_conversation_formatting():
    """Test conversation formatting."""
    print("\n🔍 Testing conversation formatting...")
    
    from summarizer import create_summarizer
    
    summarizer = create_summarizer("test_api_key")
    
    # Sample messages
    messages = [
        {
            'user_id': 123456,
            'author_name': 'Mario',
            'timestamp': datetime.now(),
            'telegram_message_id': 100,
            'message_text': 'Ciao a tutti!',
            'is_audio': False
        },
        {
            'user_id': 789012,
            'author_name': 'Luigi',
            'timestamp': datetime.now(),
            'telegram_message_id': 101,
            'transcription': 'Ciao Mario, come stai?',
            'is_audio': True
        }
    ]
    
    try:
        conversation, chat_id_for_link = summarizer.format_conversation(
            messages=messages,
            chat_id=-1001234567890  # Sample supergroup ID
        )
        
        print("✅ Conversation formatted successfully")
        print(f"   Length: {len(conversation)} characters")
        print(f"   Chat ID for links: {chat_id_for_link}")
        print("\n   Preview:")
        print("   " + "\n   ".join(conversation.split("\n")[:5]))
        
        return True
    except Exception as e:
        print(f"❌ Failed to format conversation: {e}")
        return False


def test_markdown_cleaning():
    """Test Markdown artifact cleaning."""
    print("\n🔍 Testing Markdown cleaning...")
    
    from summarizer import create_summarizer
    
    summarizer = create_summarizer("test_api_key")
    
    test_cases = [
        ("**bold text**", "<b>bold text</b>"),
        ("*italic*", "<i>italic</i>"),
        ("## Header", "Header"),
        ("> quote", "quote"),
        ("[link](url)", "link"),
    ]
    
    all_passed = True
    for input_text, expected_output in test_cases:
        result = summarizer._clean_markdown_artifacts(input_text)
        if expected_output in result or result.strip() == expected_output.strip():
            print(f"   ✅ '{input_text}' → '{result}'")
        else:
            print(f"   ❌ '{input_text}' → '{result}' (expected: '{expected_output}')")
            all_passed = False
    
    return all_passed


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 LangChain Summarizer Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test imports
    results.append(("Imports", test_imports()))
    
    if results[0][1]:  # Only continue if imports succeeded
        results.append(("Summarizer Creation", test_summarizer_creation()))
        results.append(("Conversation Formatting", test_conversation_formatting()))
        results.append(("Markdown Cleaning", test_markdown_cleaning()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 All tests passed! The summarizer is ready to use.")
        print("\n⚠️  Note: To test actual summarization, you need:")
        print("   1. Valid OLLAMA_API_KEY in .env file")
        print("   2. Internet connection to Ollama Cloud")
        print("   3. Run the bot and use /summarize in a group")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
