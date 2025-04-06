import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from google.cloud import storage
from PIL import Image, ImageTk, ExifTags, ImageFile
import tkinter as tk

import storage_upload_file
import storage_make_public
import constants
import utils


def observation_ok(observation_key, observation, images, scales):

    i = 0
    for image in images:
        extension = image.filename[image.filename.rindex('.'):]
        filename = image.filename

        if '.jpg' != extension:
            image.save(filename.replace(extension, '.jpg'))
            storage_upload_file.upload_blob(constants.bucket_name, filename.replace(extension, '.jpg'),
                                            observation['photoPaths'][i].replace(extension, '.jpg'), 'image/jpeg')
            storage_make_public.make_blob_public(constants.bucket_name, observation['photoPaths'][i].replace(extension,
                                                                                                             '.jpg'))
        else:
            storage_make_public.make_blob_public(constants.bucket_name, observation['photoPaths'][i])

        size = min(image.width, image.height)
        image = utils.crop_square(image, size, size, scales[i])
        if size > 512:
            image = image.resize((512, 512), Image.ANTIALIAS)
        image.save(filename.replace(extension, '.webp'))
        storage_upload_file.upload_blob(constants.bucket_name, filename.replace(extension, '.webp'),
                                        observation['photoPaths'][i].replace(extension, '.webp'), 'image/webp')
        storage_make_public.make_blob_public(constants.bucket_name, observation['photoPaths'][i].replace(extension,
                                                                                                         '.webp'))
        i += 1
        image.close()

    observation['status'] = 'public'
    i = 0
    for path in observation['photoPaths']:
        extension = path[path.rindex('.'):]
        observation['photoPaths'][i] = observation['photoPaths'][i].replace(extension, '.webp')
        i += 1
    ref_public_by_date.child(observation_key).update(observation)
    ref_public_by_plant.child(observation['plant']).child('list').child(observation_key).update(observation)

    user = observation['id'][:observation['id'].index('_')]
    ref_private.child(user).child('by date').child('list').child(observation['id']).update(
        observation)
    ref_private.child(user).child('by plant').child(observation['plant']).child('list').child(
        observation['id']).update(observation)
    root.destroy()


def observation_cancel():
    root.destroy()


def review_observation(observation_key, observation):
    storage_client = storage.Client("abherbs-backend")
    bucket = storage_client.bucket(constants.bucket_name)

    paths = observation['photoPaths']
    images = []
    for path in paths:
        blob = bucket.blob(path)
        with open(constants.observationsdir + path[path.rindex('/'):], "wb") as file_obj:
            blob.download_to_file(file_obj)
            image = Image.open(file_obj.name)

            # rotate if necessary
            try:
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break

                exif = dict(image._getexif().items())

                if exif[orientation] == 3:
                    image = image.rotate(180, expand=True)
                elif exif[orientation] == 6:
                    image = image.rotate(270, expand=True)
                elif exif[orientation] == 8:
                    image = image.rotate(90, expand=True)
            except (AttributeError, KeyError, IndexError):
                # cases: image don't have getexif
                pass

            image.filename = file_obj.name
            images.append(image)
            file_obj.close()

    plant = tk.Label(root, text=observation['plant'])
    plant.pack()

    frame = tk.Frame(root)
    frame.pack(side=tk.BOTTOM)

    bottom_frame = tk.Frame(root)
    bottom_frame.pack(side=tk.BOTTOM)

    labels = []
    photos = []
    scales = []
    i = 0
    for image in images:
        ratio = image.width/image.height
        photo = ImageTk.PhotoImage(image.resize((250, int(250/ratio)), Image.Resampling.LANCZOS))
        photos.append(photo)
        label = tk.Label(frame, image=photo).grid(row=0, column=i)
        labels.append(label)
        if image.width > image.height:
            w = tk.Scale(frame, from_=0, to=max(image.width, image.height), orient=tk.HORIZONTAL)
            w.set(int(max(image.width, image.height)/2))
            scales.append(w)
            w.grid(row=1, column=i, sticky=tk.W+tk.E)
        else:
            w = tk.Scale(frame, from_=0, to=max(image.width, image.height))
            w.set(int(max(image.width, image.height)/2))
            scales.append(w)
            w.grid(row=0, column=i+1, sticky=tk.N+tk.S)
            i += 1
        i += 1

    ok_button = tk.Button(bottom_frame, text="OK", command=lambda: observation_ok(observation_key, observation, images, scales))
    ok_button.pack(side=tk.LEFT, pady=10, ipadx=10)

    cancel_button = tk.Button(bottom_frame, text="Cancel", command=observation_cancel)
    cancel_button.pack(side=tk.LEFT, padx=10)

    root.mainloop()


if __name__ == "__main__":
    cred = credentials.Certificate(constants.certificate_firebase)
    firebase_admin.initialize_app(cred, {
        'databaseURL': constants.databaseURL
    })
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    ref_public_by_date = db.reference('observations/public/by date/list')
    ref_public_by_plant = db.reference('observations/public/by plant')
    ref_private = db.reference('observations/by users')
    new_observations = ref_public_by_date.order_by_child('status').equal_to('review').get()
    for observation_key in new_observations.keys():
        root = tk.Tk()
        observation = new_observations[observation_key]
        review_observation(observation_key, observation)