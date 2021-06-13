import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from os import path
import urllib.request, json
from bs4 import BeautifulSoup
import urllib.parse

import constants


def add_plant(id, order, family, plant, wikidata, flowering_from, flowering_to, height_from, height_to, color, habitat, petal):
    ipni_id = add_plant_v2(order, family, plant, wikidata, id, flowering_from, flowering_to, height_from, height_to)
    add_plant_header(order, family, plant, id, ipni_id, color, habitat, petal)
    synonyms = add_plant_synonyms(plant, ipni_id)
    add_plant_translations(plant, wikidata, synonyms)
    return


def add_plant_header(order, family, plant, id, ipni_id, color, habitat, petal):
    target = path.join(constants.storagedir, order, family, plant.replace(' ', '_'))
    names = plant.split(' ')
    name = names[0][0].lower() + names[len(names) - 1][0].lower() + constants.extension
    if (not path.exists(path.join(target, name))):
        name = names[0][0].lower() + names[len(names) - 1][0].lower() + '1' + constants.extension
    url = '/'.join([order, family, plant.replace(' ', '_'), name])

    tdwg = {}
    filepath = 'tdwg.csv'
    code = 0
    with open(filepath, encoding='utf-8') as fp:
        for line in fp:
            line_items = line.split(',')
            if line_items[1].strip() == 'L2':
                code = str(line_items[2].strip())
            elif line_items[1].strip() == 'L3':
                tdwg[line_items[3].strip()[:20]] = int(code)
            # elif line_items[1].strip() == 'L4':
            #     tdwg[line_items[3].strip()] = int(code)

    distribution_regions = []
    with urllib.request.urlopen('http://plantsoftheworldonline.org/taxon/urn:lsid:ipni.org:names:' + ipni_id) as url_ipni:
        bs = BeautifulSoup(url_ipni.read().decode('utf8'), features='lxml')
        div = bs.find('div', {'id': 'distribution-listing'})
        ps = div.findAll('p')
        for p in ps:
            distribution_regions.extend([tdwg[x.strip()] for x in p.text.split(',')])
    distribution_regions = list(dict.fromkeys(distribution_regions))
    distribution_regions.sort()

    refHeader = db.reference('plants_headers/' + str(id))
    refHeader.update({
        'family': family,
        'filterColor': [int(x) for x in color.split(',')],
        'filterDistribution': distribution_regions,
        'filterHabitat': [int(x) for x in habitat.split(',')],
        'filterPetal': [int(x) for x in petal.split(',')],
        'name': plant,
        'url': url
    })
    return


def add_plant_v2(order, family, plant, wikidata, id, flowering_from, flowering_to, height_from, height_to):
    origin = path.join(constants.plantsdir, family, plant, 'sources.txt')
    target = path.join(constants.storagedir, order, family, plant.replace(' ', '_'))

    photo_urls = []
    names = plant.split(' ')
    name = names[0][0].lower() + names[len(names) - 1][0].lower()
    photo_count = 1
    while path.exists(path.join(target, name + str(photo_count) + constants.extension)):
        photo_urls.append(
            '/'.join([order, family, plant.replace(' ', '_'), name + str(photo_count) + constants.extension]))
        photo_count += 1

    source_urls = []
    sources = open(origin, 'r')
    for line in sources:
        source_urls.append(urllib.parse.unquote(line.strip()))

    wikilinks = {}
    wikilinks['data'] = 'https://www.wikidata.org/wiki/' + wikidata

    freebase_id = ''
    gbif_id = ''
    usda_id = ''
    ipni_id = ''

    with urllib.request.urlopen('https://www.wikidata.org/wiki/Special:EntityData/' + wikidata + '.json') as url_data:
        data = json.loads(url_data.read().decode())
        sitelinks = data['entities'][wikidata]['sitelinks']
        if 'commonswiki' in sitelinks.keys():
            wikilinks['commons'] = sitelinks['commonswiki']['url']
        if 'specieswiki' in sitelinks.keys():
            wikilinks['species'] = sitelinks['specieswiki']['url']

        claims = data['entities'][wikidata]['claims']
        if 'P646' in claims.keys():
            freebase_id = claims['P646'][0]['mainsnak']['datavalue']['value']
        if 'P846' in claims.keys():
            gbif_id = claims['P846'][0]['mainsnak']['datavalue']['value']
        if 'P1772' in claims.keys():
            usda_id = claims['P1772'][0]['mainsnak']['datavalue']['value']
        if 'P961' in claims.keys():
            ipni_id = claims['P961'][0]['mainsnak']['datavalue']['value']
            if ipni_id == '161931-2':
                ipni_id = '508578-1'
            elif ipni_id == '597506-1':
                ipni_id = '597505-1'

    taxons = []
    apg_iv = {}
    if 'species' in wikilinks.keys():
        species = wikilinks['species']
        with urllib.request.urlopen(species) as url_species:
            bs = BeautifulSoup(url_species.read().decode('utf8'), features='lxml')
            tag = bs('p')
            for i in range(0,2):
                elem = tag[i]
                taxons.extend([y.strip() for y in [x for x in elem.text.split('\n') if x]])

        taxon_count = 0
        taxons.reverse()
        for taxon in taxons:
            if ':' in taxon and not taxon.startswith('Species') and not taxon.startswith('Variet') and not taxon.startswith('Subspecies'):
                if taxon.startswith('Ordo'):
                    taxon_names = constants.apgiv_names[order].split('/')
                    taxon_names.reverse()
                    taxon_values = constants.apgiv_values[order].split('/')
                    taxon_values.reverse()
                    for i in range(len(taxon_names)):
                        apg_iv['{:0>2d}'.format(taxon_count) + '_' + taxon_names[i]] = taxon_values[i]
                        taxon_count += 1
                    break
                else:
                    line = taxon.split(': ')
                    line_value = line[1].split(' ')
                    apg_iv['{:0>2d}'.format(taxon_count) + '_' + line[0]] = line_value[len(line_value)-1]
                    taxon_count += 1

    plant_v2 = {
        'APGIV': apg_iv,
        'floweringFrom': int(flowering_from),
        'floweringTo': int(flowering_to),
        'id': id,
        'illustrationUrl': '/'.join(
            [order, family, plant.replace(' ', '_'), plant.replace(' ', '_') + constants.extension]),
        'heightFrom': int(height_from),
        'heightTo': int(height_to),
        'name': plant,
        'photoUrls': photo_urls,
        'sourceUrls': source_urls,
        'wikilinks': wikilinks,
    }
    if freebase_id:
        plant_v2['freebaseId'] = freebase_id
    if gbif_id:
        plant_v2['gbifId'] = gbif_id
    if usda_id:
        plant_v2['usdaId'] = usda_id
    if ipni_id:
        plant_v2['ipniId'] = ipni_id

    ref_plant = db.reference('plants_v2/' + plant)
    ref_plant.update(plant_v2)
    return ipni_id


def add_plant_synonyms(plant, ipni_id):
    synonyms = []
    with urllib.request.urlopen('http://plantsoftheworldonline.org/taxon/urn:lsid:ipni.org:names:' + ipni_id) as url_ipni:
        bs = BeautifulSoup(url_ipni.read().decode('utf8'), features='lxml')
        ul = bs.find('h1', {'class': 'c-summary__heading'}).find('small')
        author = ul.text.strip()
        if author:
            plant_v2 = {'author': author}
            ref_plant = db.reference('plants_v2/' + plant)
            ref_plant.update(plant_v2)

        ul = bs.find('section', {'id': 'synonyms'})
        if ul:
            ul = ul.find('ul', {'class': 'c-synonym-list'})
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
            ref_synonyms = db.reference('synonyms/' + plant)
            ref_synonyms.update({'ipni': synonyms})

    return synonyms


def add_plant_translations(plant, wikidata, synonyms):
    with urllib.request.urlopen('https://www.wikidata.org/wiki/Special:EntityData/' + wikidata + '.json') as url_data:
        data = json.loads(url_data.read().decode())

        names = {}
        labels = data['entities'][wikidata]['labels']
        for label in labels:
            if labels[label]['value'] != plant:
                names[label] = [getName(labels[label]['value'], label)]

        aliases = data['entities'][wikidata]['aliases']
        for alias in aliases:
            for alias_item in aliases[alias]:
                if alias_item['value'] != plant and not isSynonym(alias_item['value'], synonyms):
                    if alias in names.keys():
                        names[alias].append(getName(alias_item['value'], alias))
                    else:
                        names[alias] = [getName(alias_item['value'], alias)]

        wikilinks = {}
        sitelinks = data['entities'][wikidata]['sitelinks']
        for sitelink in sitelinks:
            if sitelink != 'commonswiki' and sitelink != 'specieswiki':
                wikilinks[sitelink.replace('wiki', '')] = urllib.parse.unquote(sitelinks[sitelink]['url'])

        languages = []
        languages.extend(names.keys())
        languages.extend(wikilinks.keys())
        languages = list(dict.fromkeys(languages))
        for language in languages:
            ref_translation = db.reference('translations/' + language + '/' + plant)
            translation = {}
            if language in names.keys():
                translation['label'] = names[language][0]
                if len(names[language]) > 1:
                    translation['names'] = names[language][1:]
            if language in wikilinks.keys():
                translation['wikipedia'] = wikilinks[language]
            ref_translation.update(translation)


def isSynonym(name, synonyms):
    for synonym in synonyms:
        if synonym['name'].startswith(name):
            return True
    return False

def getName(name, language):
    if language == 'de':
        if ' ' in name:
            return name[0].lower() + name[1:]
        else:
            return name
    else:
        return name.lower()

if __name__ == "__main__":
    cred = credentials.Certificate('D:\\Dev\\Keystore\\abherbs-backend-firebase-adminsdk-l5787-d877acd19f.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://abherbs-backend.firebaseio.com'
    })
    refCount = db.reference('plants_to_update/count')
    count = refCount.get()

    filepath = 'plants_to_upload.txt'
    with open(filepath) as fp:
        for line in fp:
            items = line.rstrip().split(';')
            print(items[2].strip())
            add_plant(
                id=count,
                order=items[0].strip(),
                family=items[1].strip(),
                plant=items[2].strip(),
                wikidata=items[3].strip(),
                flowering_from=items[4].strip(),
                flowering_to=items[5].strip(),
                height_from=items[6].strip(),
                height_to=items[7].strip(),
                color=items[8].strip(),
                habitat=items[9].strip(),
                petal=items[10].strip()
            )
            count += 1
