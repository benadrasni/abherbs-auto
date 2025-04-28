import argparse
import firebase_admin
from firebase_admin import credentials, messaging, db
from deep_translator import GoogleTranslator

import constants

# Define the mapping from full language names to language codes
language_map = {
    'English': 'en',
    'Slovak': 'sk',
    'Czech': 'cs',
    'German': 'de',
    'French': 'fr',
    'Hungarian': 'hu',
    'Polish': 'pl',
    'Romanian': 'ro',
    'Russian': 'ru',
    'Hebrew': 'he',
    'Japanese': 'ja',
    'Danish': 'da',
    'Dutch': 'nl',
    'Swedish': 'sv',
    'Italian': 'it',
    'Finnish': 'fi',
    'Norwegian': 'no',
    'Ukrainian': 'uk',
    'Spanish (Spain)': 'es',
    'Portuguese (Brazil)': 'pt',
    'Chinese (Traditional)': 'zh-TW'
}


def get_translated_label(language_code, plant_name):
    """Fetch the translated label from Firebase Realtime Database."""
    try:
        ref = db.reference(f'translations/{language_code}/{plant_name}/label')
        label = ref.get()
        return label if label else plant_name  # Fallback to plant_name if translation is missing
    except Exception as e:
        print(f"Failed to fetch translation for {language_code}: {e}")
        return plant_name  # Fallback to plant_name on error


def main():
    # Define notification parameters
    plant_name = 'Silene latifolia'
    notification_name = 'Plant Video'
    notification_body = 'Click here to see the video.'

    # Initialize Firebase app
    cred = credentials.Certificate(constants.certificate_firebase)
    firebase_admin.initialize_app(cred, {'databaseURL': constants.databaseURL})

    # Iterate over each language
    for language, code in language_map.items():
        try:
            # Fetch the translated plant name
            translated_plant_name = get_translated_label(code, plant_name)

            # Construct the notification title with the translated plant name
            notification_title = f'New video available for {translated_plant_name}'

            # Translate title and body to the target language
            translator = GoogleTranslator(source='en', target=code)
            translated_title = translator.translate(notification_title)
            translated_body = translator.translate(notification_body)
        except Exception as e:
            print(f"Translation failed for {language}: {e}")
            continue

        # Construct the FCM message
        message = messaging.Message(
            notification=messaging.Notification(
                title=translated_title,
                body=translated_body,
            ),
            data={
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
                "action": "plant",
                "name": plant_name,  # Keep original plant_name for data payload
            },
            topic=f"notifications-{code}",
        )

        # Send the message
        try:
            response = messaging.send(message)
            print(f"Sent notification {notification_name}-{language} to topic notifications-{code}: {response}")
        except Exception as e:
            print(f"Failed to send notification for {language}: {e}")


if __name__ == "__main__":
    main()