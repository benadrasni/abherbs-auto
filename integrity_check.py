import firebase_admin
from firebase_admin import credentials
from firebase_admin import db


def check_translations_taxonomy():
    ref_translation_taxonomy = db.reference('translations_taxonomy')
    translation_taxonomy = ref_translation_taxonomy.get()
    for language in translation_taxonomy.keys():
        translations_in_language = translation_taxonomy[language]
        for taxon in translations_in_language.keys():
            translations = translations_in_language[taxon]
            for name in translations:
                if not name:
                    print(language + ': ' + taxon)


def check_observations():
    ref_observations = db.reference('observations/by users')
    observations = ref_observations.get()
    for user in observations.keys():
        user_observations = observations[user]
        for observation_id in user_observations['by date']['list'].keys():
            observation = user_observations['by date']['list'][observation_id]
            if not observation['date']:
                print(observation_id)
            if observation['latitude'] == 0:
                print(observation_id)
            if observation['longitude'] == 0:
                print(observation_id)
                

if __name__ == "__main__":
    cred = credentials.Certificate('D:\\Dev\\Keystore\\abherbs-backend-firebase-adminsdk-l5787-d877acd19f.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://abherbs-backend.firebaseio.com'
    })

    #check_translations_taxonomy()
    check_observations()


