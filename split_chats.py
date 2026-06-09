import json
import os
import re

import sys

# Your chats folder path (resolves dynamically or accepts argv)
script_dir = os.path.dirname(os.path.abspath(__file__))
default_base = os.environ.get("CHRONICLE_BASE_DIR") or os.path.expanduser("~/.chronicle")
if os.path.exists(os.path.join(script_dir, ".git")):
    default_base = script_dir

default_chats_dir = os.path.join(default_base, "chats")

if len(sys.argv) > 1:
    CHATS_DIR = sys.argv[1]
else:
    CHATS_DIR = default_chats_dir

# The name of your big export file (Change this if yours is named differently, like 'chats.json')
SOURCE_FILE_NAME = "conversations.json"
SOURCE_FILE_PATH = os.path.join(CHATS_DIR, SOURCE_FILE_NAME)

def sanitize_filename(name: str) -> str:
    """Removes characters that are not allowed in macOS/Windows file names."""
    if not name:
        return "Untitled_Chat"
    # Replace invalid path characters with an underscore
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", name)
    # Truncate to 100 characters so file names don't get too ridiculously long
    return safe_name.strip()[:100]

def split_chats():
    os.makedirs(CHATS_DIR, exist_ok=True)
    if not os.path.exists(SOURCE_FILE_PATH):
        print(f"Error: Could not find the source file at {SOURCE_FILE_PATH}")
        return

    print(f"Loading {SOURCE_FILE_NAME}... this might take a few seconds.")
    
    with open(SOURCE_FILE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ChatGPT exports are usually a list of conversation objects
    if isinstance(data, list):
        conversations = data
    else:
        print("Format not recognized as a standard list of chats. It might be structured differently.")
        return

    print(f"Found {len(conversations)} chats. Splitting them now...")

    success_count = 0
    for i, chat in enumerate(conversations):
        # Check multiple common keys that different providers use for the topic
        title = chat.get('title')
        if not title:
            title = chat.get('name')
        if not title:
            title = chat.get('chat_title')
            
        # If we still can't find a title, debug the first one to see what keys exist
        if not title:
            if i == 0:
                print(f"\n[Debug] Couldn't find a topic name. Here are the keys in your JSON: {list(chat.keys())}\n")
            title = f"Untitled_Chat_{i}"
            
        safe_title = sanitize_filename(title)
        
        file_name = f"{safe_title}.json"
        file_path = os.path.join(CHATS_DIR, file_name)
        
        # Handle duplicate titles by appending a number
        counter = 1
        while os.path.exists(file_path):
            file_name = f"{safe_title}_{counter}.json"
            file_path = os.path.join(CHATS_DIR, file_name)
            counter += 1

        # Write the individual chat to its own file
        with open(file_path, 'w', encoding='utf-8') as out_f:
            json.dump(chat, out_f, indent=2)
            
        success_count += 1

    print(f"\nSuccess! Separated {success_count} chats into individual files inside your '{CHATS_DIR}' folder.")

if __name__ == "__main__":
    split_chats()