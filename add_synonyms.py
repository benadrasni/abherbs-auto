import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from os import path
import urllib.request, json
from bs4 import BeautifulSoup
import urllib.parse

import constants

def getIPNI(plant):
    ipni_id = ''

    wikidata = plant['wikilinks']['data'][plant['wikilinks']['data'].rindex('/')+1:]
    with urllib.request.urlopen('https://www.wikidata.org/wiki/Special:EntityData/' + wikidata + '.json') as url_data:
        data = json.loads(url_data.read().decode())

        claims = data['entities'][wikidata]['claims']
        if 'P961' in claims.keys():
            ipni_id = claims['P961'][0]['mainsnak']['datavalue']['value']
            if ipni_id == '30005905-2':
                ipni_id = '721172-1'
            elif ipni_id == '837329-1':
                ipni_id = '5849-2'
            elif ipni_id == '30073474-2':
                ipni_id = '721244-1'

    plant_v2 = {}
    if ipni_id:
        plant_v2['ipniId'] = ipni_id

    ref_plant = db.reference('plants_v2/' + plant['name'])
    ref_plant.update(plant_v2)

    ref_plant_kew = db.reference('plants_v2/' + plant['name'] + '/kewId')
    ref_plant_kew.set({})

    return ipni_id


def add_author(plant, ipni_id):
    try:
        with urllib.request.urlopen('http://plantsoftheworldonline.org/taxon/urn:lsid:ipni.org:names:' + ipni_id) as url_ipni:
            bs = BeautifulSoup(url_ipni.read().decode('utf8'), features='lxml')
            ul = bs.find('h1', {'class': 'c-summary__heading'}).find('small')
            author = ul.text.strip()

            if author:
                print(plant['name'] + ' ' + author)
                plant_v2 = {'author': author}
                ref_plant = db.reference('plants_v2/' + plant['name'])
                ref_plant.update(plant_v2)
    except:
        print(plant['name'])


def add_plant_synonyms(plant, ipni_id):
    synonyms = []
    try:
        with urllib.request.urlopen('http://plantsoftheworldonline.org/taxon/urn:lsid:ipni.org:names:' + ipni_id) as url_ipni:
            bs = BeautifulSoup(url_ipni.read().decode('utf8'), features='lxml')
            ul = bs.find('section', {'id': 'synonyms'}).find('ul', {'class': 'c-synonym-list'})
            if ul:
                lis = ul.findAll('li')
                for li in lis:
                    name = li.find('em').text.strip()
                    author = li.findAll('em')[-1].next_sibling.strip()
                    suffix = li.text.replace(name, '').replace(author, '').strip()
                    synonym = {
                        'href': li.find('a')['href'],
                        'name': name,
                        'suffix': suffix,
                        'author': author
                    }
                    synonyms.append(synonym)
        if synonyms:
            ref_synonyms = db.reference('synonyms/' + plant['name'])
            ref_synonyms.update({'ipni': synonyms})
    except:
        print(plant['name'])


if __name__ == "__main__":
    cred = credentials.Certificate('D:\\Dev\\Keystore\\abherbs-backend-firebase-adminsdk-l5787-d877acd19f.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://abherbs-backend.firebaseio.com'
    })

    ref_plant = db.reference('plants_v2/Codiaeum variegatum')
    plant = ref_plant.get()
    add_plant_synonyms(plant, '85073-3')

    # ref_list = db.reference('plants_to_update/list')
    # plants = ref_list.get()
    # for plant_name in plants:
    #     # print(plant_name)
    #     ref_plant = db.reference('plants_v2/' + plant_name)
    #     plant = ref_plant.get()
    #     if 'ipniId' in plant.keys():
    #         #add_plant_synonyms(plant, plant['ipniId'])
    #         add_author(plant, plant['ipniId'])