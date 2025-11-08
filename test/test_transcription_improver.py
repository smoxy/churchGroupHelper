"""Test script for transcription improvement functionality."""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from transcription_improver import create_improver


def test_improver():
    """Test the transcription improver with sample text."""
    
    # Check for API key
    api_key = os.getenv('OLLAMA_API_KEY')
    if not api_key:
        print("❌ ERROR: OLLAMA_API_KEY not found in environment")
        print("   Please set it in your .env file")
        return False
    
    print("✓ OLLAMA_API_KEY found")
    
    # Get model name
    model_name = os.getenv('TRANSCRIPTION_IMPROVER_MODEL', 'gpt-oss:20b')
    print(f"✓ Using model: {model_name}")
    
    # Create improver
    print("\n📝 Initializing TranscriptionImprover...")
    try:
        improver = create_improver(api_key, model_name)
        print("✓ TranscriptionImprover initialized successfully")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize improver: {e}")
        return False
    
    # Test with sample text (simulating a bad transcription)
    sample_text = """
    questo è un test di trascrizione
    che ha molti problemi
    
    
    
    non ha punteggiatura
    e va a capo continuamente
    
    senza senso logico
    il testo dovrebbe essere migliorato dal modello
    per renderlo più leggibile
    magari ci sono anche termini in english o in français
    che devono rimanere così come sono
    """
    
    print("\n📥 Original transcription (Italian with some foreign terms):")
    print("-" * 60)
    print(sample_text)
    print("-" * 60)
    print(f"Length: {len(sample_text)} characters")
    print(f"Language: it (Italian)")
    
    # Improve the transcription
    print("\n🔄 Improving transcription...")
    try:
        improved = improver.improve(sample_text, language="it")
        print("✓ Transcription improved successfully")
    except Exception as e:
        print(f"❌ ERROR: Failed to improve transcription: {e}")
        return False
    
    print("\n📤 Improved transcription:")
    print("-" * 60)
    print(improved)
    print("-" * 60)
    print(f"Length: {len(improved)} characters")
    
    # Compare
    print("\n📊 Comparison:")
    print(f"   Original length: {len(sample_text)} chars")
    print(f"   Improved length: {len(improved)} chars")
    print(f"   Difference: {len(improved) - len(sample_text):+d} chars")
    
    # Check if improvement was successful
    if not improved or improved == sample_text:
        print("\n⚠️  WARNING: Improvement didn't change the text significantly")
        return False
    
    print("\n✅ Test completed successfully!")
    print("\n💡 Tips:")
    print(f"   - Current model: {model_name}")
    print("   - Try different models by setting TRANSCRIPTION_IMPROVER_MODEL in .env")
    print("   - Available models: gpt-oss:20b, gpt-oss:120b, kimi-k2:1t, deepseek-v3.1:671b")
    print("   - Larger models = better quality but slower")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Transcription Improvement Test")
    print("=" * 60)
    print()
    
    success = test_improver()
    
    print()
    print("=" * 60)
    
    sys.exit(0 if success else 1)
