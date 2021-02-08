import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from geopy.geocoders import Nominatim

import constants


def refresh_public_stats():
    stats = {}

    # count
    ref_by_date = db.reference('observations/public/by date/list')
    by_date = ref_by_date.get()
    stats['count'] = len(by_date)

    # first / last
    first = 999999999999999
    first_flower = ''
    last = 0
    last_flower = ''
    observers = []
    countries = []
    ranks = {}
    counts = {}
    for observation_key in by_date.keys():
        observation = by_date[observation_key]
        time_in_miliseconds = -1*int(observation['order'])
        if time_in_miliseconds < first:
            first = time_in_miliseconds
            first_flower = observation['plant']

        if time_in_miliseconds > last:
            last = time_in_miliseconds
            last_flower = observation['plant']

        index = observation['id'].index('_')
        observer = observation['id'][:index]
        if observer not in observers:
            observers.append(observer)
            ranks[observer] = 1
        else:
            ranks[observer] += 1

        if 'country' in observation.keys():
            country_code = observation['country']
        else:
            try:
                location = geolocator.reverse(str(observation['latitude']) + ', ' + str(observation['longitude']))
            except TypeError:
                print(observation_key)
                continue

            country_code = location.raw['address']['country_code']
            ref_observation_cc = db.reference('observations/public/by date/list/' + observation_key)
            observation['country'] = country_code
            ref_observation_cc.update(observation)
            ref_observation_cc = db.reference('observations/public/by plant/' + observation['plant'] + '/list/' + observation_key)
            ref_observation_cc.update(observation)

        if country_code not in countries:
            countries.append(country_code)
            counts[country_code] = 1
        else:
            counts[country_code] += 1


    stats['firstFlower'] = first_flower
    stats['firstDate'] = first
    stats['lastFlower'] = last_flower
    stats['lastDate'] = last
    stats['observers'] = len(observers)
    stats['countries'] = counts

    # distinct flowers
    ref_by_plant = db.reference('observations/public/by plant')
    by_plant = ref_by_plant.get()
    stats['distinctFlowers'] = len(by_plant)

    # max observed
    max_count = 0
    max_plant = ''
    for plant_name in by_plant.keys():
        plant_count = len(by_plant[plant_name]['list'])
        if plant_count > max_count:
            max_count = plant_count
            max_plant = plant_name
    stats['mostObserved'] = max_plant
    stats['mostObservedCount'] = max_count

    ref_observation_stats = db.reference('observations/public/stats')
    ref_observation_stats.set(stats)

    return ranks


def refresh_private_stats(ranks):

    ref_by_users = db.reference('observations/by users')
    by_users = ref_by_users.get()
    for user in by_users.keys():
        stats = {}
        try:
            by_date = by_users[user]['by date']['list']
        except KeyError:
            print(user)
            continue

        # count
        stats['count'] = len(by_date)

        # rank
        try:
            stats['rank'] = [y[0] for y in ranks].index(user) + 1
        except ValueError:
            stats['rank'] = 0

            # first / last
        first = 999999999999999
        first_flower = ''
        last = 0
        last_flower = ''
        countries = []
        counts = {}
        for observation_key in by_date.keys():
            observation = by_date[observation_key]
            time_in_miliseconds = int(observation['date']['time'])
            if time_in_miliseconds < first:
                first = time_in_miliseconds
                first_flower = observation['plant']

            if time_in_miliseconds > last:
                last = time_in_miliseconds
                last_flower = observation['plant']

            if 'country' in observation.keys():
                country_code = observation['country']
            else:
                try:
                    location = geolocator.reverse(str(observation['latitude']) + ', ' + str(observation['longitude']))
                except:
                    print(observation_key + ': ' + str(observation['latitude']) + ', ' + str(observation['longitude']))
                    continue

                country_code = location.raw['address']['country_code']
                ref_observation_cc = db.reference('observations/by users/' + user + '/by date/list/' + observation_key)
                observation['country'] = country_code
                ref_observation_cc.update(observation)
                ref_observation_cc = db.reference(
                    'observations/by users/' + user + '/by plant/' + observation['plant'] + '/list/' + observation_key)
                ref_observation_cc.update(observation)

            if country_code not in countries:
                countries.append(country_code)
                counts[country_code] = 1
            else:
                counts[country_code] += 1

        stats['firstFlower'] = first_flower
        stats['firstDate'] = first
        stats['lastFlower'] = last_flower
        stats['lastDate'] = last
        stats['countries'] = counts

        # distinct flowers
        by_plant = by_users[user]['by plant']
        stats['distinctFlowers'] = len(by_plant)

        # max observed
        max_count = 0
        max_plant = ''
        for plant_name in by_plant.keys():
            plant_count = len(by_plant[plant_name]['list'])
            if plant_count > max_count:
                max_count = plant_count
                max_plant = plant_name
        stats['mostObserved'] = max_plant
        stats['mostObservedCount'] = max_count

        ref_observation_stats = db.reference('observations/by users/' + user + '/stats')
        ref_observation_stats.set(stats)


if __name__ == "__main__":
    cred = credentials.Certificate(constants.certificate_firebase)
    firebase_admin.initialize_app(cred, {
        'databaseURL': constants.databaseURL
    })
    geolocator = Nominatim(user_agent="abherbs")

    ranks = refresh_public_stats()
    sorted_ranks = sorted(ranks.items(), key=lambda kv: kv[1], reverse=True)
    print(sorted_ranks)
    refresh_private_stats(sorted_ranks)
