import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

def rename_plant(old_name, new_name):
    ref_old_plant = db.reference('plants_v2/' + old_name)
    plant = ref_old_plant.get()
    plant['name'] = new_name
    ref_new_plant = db.reference('plants_v2/' + new_name)
    ref_new_plant.update(plant)

    ref_old_synonyms = db.reference('synonyms/' + old_name)
    synonyms = ref_old_synonyms.get()
    ref_new_synonyms = db.reference('synonyms/' + new_name)
    ref_new_synonyms.update(synonyms)

    ref_list = db.reference('translations')
    languages = ref_list.get()
    for language in languages.keys():
        # print(plant_name)
        ref_translation = db.reference('translations/' + language + '/' + old_name)
        translation = ref_translation.get()
        if translation:
            ref_new_translation = db.reference('translations/' + language + '/' + new_name)
            ref_new_translation.update(translation)



if __name__ == "__main__":
    cred = credentials.Certificate('D:\\Dev\\Keystore\\abherbs-backend-firebase-adminsdk-l5787-d877acd19f.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://abherbs-backend.firebaseio.com'
    })

    rename_plant('Glandularia bipinnatifida', 'Verbena bipinnatifida')
