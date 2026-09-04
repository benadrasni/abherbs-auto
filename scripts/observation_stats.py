import time

import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from geopy.geocoders import Nominatim

import constants


def _is_indoors(observation):
    return isinstance(observation, dict) and observation.get('indoors') is True


def _country_for(observation, geolocator):
    if 'country' in observation:
        return observation['country']
    lat = observation.get('latitude')
    lon = observation.get('longitude')
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None
    if abs(lat_f) < 0.001 and abs(lon_f) < 0.001:
        return None
    try:
        location = geolocator.reverse(str(lat) + ', ' + str(lon), exactly_one=True, timeout=10)
    except Exception as e:
        print('geocode fail', lat, lon, e)
        time.sleep(1.1)
        return None
    time.sleep(1.1)
    if not location:
        return None
    return location.raw.get('address', {}).get('country_code')


def refresh_public_stats(geolocator):
    stats = {}
    ref_by_date = db.reference('observations/public/by date/list')
    by_date = ref_by_date.get() or {}

    first = None
    first_flower = ''
    last = None
    last_flower = ''
    observers = []
    ranks = {}
    counts = {}
    plant_counts = {}
    counted = 0
    skipped_indoors = 0

    for observation_key, observation in by_date.items():
        if not isinstance(observation, dict):
            continue
        if _is_indoors(observation):
            skipped_indoors += 1
            continue
        counted += 1

        time_in_miliseconds = -1 * int(observation['order'])
        if first is None or time_in_miliseconds < first:
            first = time_in_miliseconds
            first_flower = observation['plant']
        if last is None or time_in_miliseconds > last:
            last = time_in_miliseconds
            last_flower = observation['plant']

        observer = observation['id'][: observation['id'].index('_')]
        if observer not in observers:
            observers.append(observer)
            ranks[observer] = 1
        else:
            ranks[observer] += 1

        plant = observation['plant']
        plant_counts[plant] = plant_counts.get(plant, 0) + 1

        country_code = _country_for(observation, geolocator)
        if country_code and 'country' not in observation:
            print('geo public', observation_key, country_code)
            observation['country'] = country_code
            ref_by_date.child(observation_key).update({'country': country_code})
            db.reference(
                'observations/public/by plant/' + plant + '/list/' + observation_key
            ).update({'country': country_code})
        if country_code:
            counts[country_code] = counts.get(country_code, 0) + 1

    stats['count'] = counted
    stats['firstFlower'] = first_flower
    stats['firstDate'] = first or 0
    stats['lastFlower'] = last_flower
    stats['lastDate'] = last or 0
    stats['observers'] = len(observers)
    stats['countries'] = counts
    stats['distinctFlowers'] = len(plant_counts)
    if plant_counts:
        max_plant = max(plant_counts, key=plant_counts.get)
        stats['mostObserved'] = max_plant
        stats['mostObservedCount'] = plant_counts[max_plant]
    else:
        stats['mostObserved'] = ''
        stats['mostObservedCount'] = 0

    db.reference('observations/public/stats').set(stats)
    print('public counted', counted, 'skipped_indoors', skipped_indoors)
    print('public stats', stats)
    return ranks


def refresh_private_stats(ranks, geolocator):
    ref_by_users = db.reference('observations/by users')
    by_users = ref_by_users.get() or {}
    rank_order = [y[0] for y in ranks]

    for user in by_users.keys():
        stats = {}
        try:
            by_date = by_users[user]['by date']['list']
        except KeyError:
            print(user)
            continue

        first = None
        first_flower = ''
        last = None
        last_flower = ''
        counts = {}
        plant_counts = {}
        counted = 0

        for observation_key, observation in by_date.items():
            if not isinstance(observation, dict):
                continue
            if _is_indoors(observation):
                continue
            counted += 1
            time_in_miliseconds = int(observation['date']['time'])
            if first is None or time_in_miliseconds < first:
                first = time_in_miliseconds
                first_flower = observation['plant']
            if last is None or time_in_miliseconds > last:
                last = time_in_miliseconds
                last_flower = observation['plant']

            plant = observation['plant']
            plant_counts[plant] = plant_counts.get(plant, 0) + 1

            country_code = _country_for(observation, geolocator)
            if country_code and 'country' not in observation:
                observation['country'] = country_code
                db.reference(
                    'observations/by users/' + user + '/by date/list/' + observation_key
                ).update({'country': country_code})
                db.reference(
                    'observations/by users/' + user + '/by plant/' + plant + '/list/' + observation_key
                ).update({'country': country_code})
            if country_code:
                counts[country_code] = counts.get(country_code, 0) + 1

        stats['count'] = counted
        try:
            stats['rank'] = rank_order.index(user) + 1
        except ValueError:
            stats['rank'] = 0
        stats['firstFlower'] = first_flower
        stats['firstDate'] = first or 0
        stats['lastFlower'] = last_flower
        stats['lastDate'] = last or 0
        stats['countries'] = counts
        stats['distinctFlowers'] = len(plant_counts)
        if plant_counts:
            max_plant = max(plant_counts, key=plant_counts.get)
            stats['mostObserved'] = max_plant
            stats['mostObservedCount'] = plant_counts[max_plant]
        else:
            stats['mostObserved'] = ''
            stats['mostObservedCount'] = 0

        db.reference('observations/by users/' + user + '/stats').set(stats)


if __name__ == "__main__":
    cred = credentials.Certificate(constants.certificate_firebase)
    firebase_admin.initialize_app(cred, {
        'databaseURL': constants.databaseURL
    })
    geolocator = Nominatim(user_agent=constants.user_agent, timeout=10)

    ranks = refresh_public_stats(geolocator)
    sorted_ranks = sorted(ranks.items(), key=lambda kv: kv[1], reverse=True)
    print(sorted_ranks)
    refresh_private_stats(sorted_ranks, geolocator)
