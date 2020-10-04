import os
import storage_upload_file
import storage_make_public
import constants


def upload_plant(order, family, plant):
    photos = os.path.join(constants.storagedir, order, family, plant.replace(' ', '_'))
    thumbnails = os.path.join(photos, constants.thumbdir)
    dest = 'photos/' + order + '/' + family + '/' + plant.replace(' ', '_') + '/'
    thumbdest = dest + constants.thumbdir + '/'

    upload_dir(photos, dest)
    upload_dir(thumbnails, thumbdest)

def upload_dir(source, destination):
    arr = os.listdir(source)
    for item in arr:
        if (os.path.isfile(os.path.join(source, item))):
            storage_upload_file.upload_blob(constants.bucket_name, os.path.join(source, item), destination + item, 'image/webp')
            storage_make_public.make_blob_public(constants.bucket_name, destination + item)

if __name__ == "__main__":
    filepath = 'plants_to_upload.txt'
    with open(filepath) as fp:
        for line in fp:
            items = line.rstrip().split(';')
            upload_plant(
                order=items[0],
                family=items[1],
                plant=items[2],
            )