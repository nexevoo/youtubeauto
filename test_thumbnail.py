import os
import sys

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.thumbnail import generate_thumbnail

if __name__ == "__main__":
    # A true crime / mystery title for a very dramatic, dark aesthetic
    test_title = "The Chilling Unsolved Mystery of Room 1046"
    save_path = "test_thumbnail_best.jpg"
    
    print(f"Testing Pollinations AI thumbnail generation for title: '{test_title}'...")
    try:
        result_path = generate_thumbnail(test_title, save_path)
        if os.path.exists(result_path):
            print(f"\nSUCCESS! Thumbnail successfully generated and saved to: {os.path.abspath(result_path)}")
            print("You can open 'test_thumbnail_best.jpg' in your file explorer to see how it looks!")
        else:
            print("\nFAILED: The file was not created.")
    except Exception as e:
        print(f"\nERROR: {e}")
