import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from deep_translator import GoogleTranslator

import constants

# Initialize Firebase app with credentials from the provided script
cred = credentials.Certificate(constants.certificate_firebase)
firebase_admin.initialize_app(cred, {'databaseURL': constants.databaseURL})

# Define the new number to add (can be modified as needed)
new_number = "536"

# Get reference to 'lists_custom/by language'
ref = db.reference('lists_custom/by language')
languages = ref.get()

if languages:
    for language in languages.keys():
        try:
            # Translate "Flowers with video" to the target language
            translator = GoogleTranslator(source='en', target=language)
            translated_name = translator.translate("Flowers with video")
            normalized_translated_name = translated_name.lower().strip()

            # Check each list in the language section
            for list_name in languages[language].keys():
                if list_name.lower().strip() == normalized_translated_name:
                    # Get reference to the specific list's "list" attribute
                    list_ref = db.reference(f'lists_custom/by language/{language}/{list_name}/list')
                    # Update the list with the new number
                    list_ref.update({new_number: 1})
                    print(f"Added {new_number} to list '{list_name}' in language '{language}'")
                    break
            else:
                print(f"No list found for '{translated_name}' in language '{language}'")
        except Exception as e:
            print(f"Translation failed for language '{language}': {e}")
else:
    print("No languages found in 'lists_custom/by language'")

print("Script execution completed.")