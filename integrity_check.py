import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

import constants


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
        if 'by date' not in user_observations or 'list' not in user_observations['by date']:
            print(user)
            continue
        for observation_id in user_observations['by date']['list'].keys():
            observation = user_observations['by date']['list'][observation_id]
            if not observation['date']:
                print(observation_id)
            if observation['latitude'] == 0:
                print(observation_id)
            if observation['longitude'] == 0:
                print(observation_id)

def check_plants_en_translations():
    ref_translations = db.reference('translations/en')
    plants = ref_translations.get()
    for plant in plants.keys():
        translation = plants[plant]
        if 'description' not in translation:
            print(plant + ': missing description')
        if 'flower' not in translation:
            print(plant + ': missing flower')
        if 'fruit' not in translation:
            print(plant + ': missing fruit')
        if 'habitat' not in translation:
            print(plant + ': missing habitat')
        if 'inflorescence' not in translation:
            print(plant + ': missing inflorescence')
        if 'leaf' not in translation:
            print(plant + ': missing leaf')
        if 'stem' not in translation:
            print(plant + ': missing stem')



if __name__ == "__main__":
    cred = credentials.Certificate(constants.certificate_firebase)
    firebase_admin.initialize_app(cred, {'databaseURL': constants.databaseURL})

    #check_translations_taxonomy()
    #check_observations()
    check_plants_en_translations()


