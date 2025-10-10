import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from utils import split_message, TELEGRAM_MAX_MESSAGE_LENGTH

def test_split_message():
    """Test the split_message function with various scenarios"""
    
    print("=" * 80)
    print("TEST 1: Short message (should not be split)")
    print("=" * 80)
    short_text = "Questo è un messaggio breve."
    chunks = split_message(short_text)
    print(f"Number of chunks: {len(chunks)}")
    print(f"Chunk 1: {chunks[0][:100]}...")
    assert len(chunks) == 1, "Short message should not be split"
    print("✓ PASSED\n")
    
    print("=" * 80)
    print("TEST 2: Long message with sentences (should split at sentence boundaries)")
    print("=" * 80)
    long_text = ". ".join([f"Questa è la frase numero {i}" for i in range(500)])
    chunks = split_message(long_text, max_length=500)
    print(f"Number of chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"Chunk {i} length: {len(chunk)}")
        print(f"Chunk {i} preview: {chunk[:100]}...")
        assert len(chunk) <= 500, f"Chunk {i} exceeds max length"
    print("✓ PASSED\n")
    
    print("=" * 80)
    print("TEST 3: Very long message without punctuation (should split by words)")
    print("=" * 80)
    long_text = " ".join([f"parola{i}" for i in range(1000)])
    chunks = split_message(long_text, max_length=1000)
    print(f"Number of chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"Chunk {i} length: {len(chunk)}")
        assert len(chunk) <= 1000, f"Chunk {i} exceeds max length"
    print("✓ PASSED\n")
    
    print("=" * 80)
    print("TEST 4: Message exactly at limit")
    print("=" * 80)
    exact_text = "a" * 4096
    chunks = split_message(exact_text)
    print(f"Number of chunks: {len(chunks)}")
    assert len(chunks) == 1, "Message at exact limit should not be split"
    print("✓ PASSED\n")
    
    print("=" * 80)
    print("TEST 5: Message one character over limit")
    print("=" * 80)
    over_text = "a" * 4097
    chunks = split_message(over_text)
    print(f"Number of chunks: {len(chunks)}")
    assert len(chunks) > 1, "Message over limit should be split"
    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i} length: {len(chunk)}")
        assert len(chunk) <= TELEGRAM_MAX_MESSAGE_LENGTH, f"Chunk {i} exceeds Telegram limit"
    print("✓ PASSED\n")
    
    print("=" * 80)
    print("TEST 6: Real-world transcription example")
    print("=" * 80)
    real_text = """Trascrizione:
Buongiorno a tutti, oggi parleremo della migrazione del nostro sistema. 
La prima cosa da considerare è la compatibilità con i sistemi esistenti. 
Dobbiamo assicurarci che tutti i moduli siano aggiornati. 
Il processo richiederà circa tre settimane. 
Inizieremo con il modulo di autenticazione. 
Poi passeremo al modulo di gestione utenti. 
Infine, aggiorneremo il modulo di reporting. 
Ci saranno alcuni downtime programmati. 
Vi terremo aggiornati via email. 
Grazie per la vostra attenzione."""
    
    # Simulate a very long transcription
    real_text_long = real_text * 50  # Make it ~5000 characters
    chunks = split_message(real_text_long)
    print(f"Number of chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i} length: {len(chunk)}")
        assert len(chunk) <= TELEGRAM_MAX_MESSAGE_LENGTH, f"Chunk {i} exceeds Telegram limit"
    print("✓ PASSED\n")
    
    print("=" * 80)
    print("ALL TESTS PASSED! ✓")
    print("=" * 80)

if __name__ == "__main__":
    test_split_message()
