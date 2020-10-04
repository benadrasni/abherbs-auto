import os
import shutil
from PIL import Image, ExifTags, ImageFile, ImageTk
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import tkinter as tk
from tkinter import ttk

import constants
import utils
from upload_plant import upload_plant
from add_plant import add_plant

def process_plant(order, family, plant):
    origin = os.path.join(constants.plantsdir, family, plant)
    target = os.path.join(constants.storagedir, order, family, plant.replace(' ', '_'))

    arr = os.listdir(origin)
    if not os.path.isdir(target):
        os.mkdir(target)
        os.mkdir(os.path.join(target, constants.thumbdir))

    frame = tk.Frame(root)
    frame.pack()

    bottom_frame = tk.Frame(root)
    bottom_frame.pack(side=tk.BOTTOM)

    images = []
    labels = []
    photos = []
    scales = []
    combos = []
    col = 0
    row = 0
    count = 0
    horizontal = False
    for item in arr:
        path = os.path.join(origin, item)
        if (os.path.isfile(path)):
            if not item.endswith(constants.extension) and not item.endswith(constants.extension_txt):
                image = Image.open(path)
                images.append(image)
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

                image.filename = path

                ratio = image.width / image.height
                photo = ImageTk.PhotoImage(image.resize((200, int(200 / ratio)), Image.ANTIALIAS))
                photos.append(photo)
                label = tk.Label(frame, image=photo).grid(row=row, column=col)
                labels.append(label)
                if image.width > image.height:
                    w = tk.Scale(frame, from_=0, to=max(image.width, image.height), orient=tk.HORIZONTAL)
                    w.set(int(max(image.width, image.height) / 2))
                    scales.append(w)
                    w.grid(row=row+1, column=col, sticky=tk.W + tk.E)
                    n = tk.IntVar()
                    combo = ttk.Combobox(frame, width=10, textvariable=n)
                    combo['values'] = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
                    combos.append(combo)
                    combo.grid(row=row+2, column=col)
                    horizontal = True
                else:
                    n = tk.IntVar()
                    combo = ttk.Combobox(frame, width=10, textvariable=n)
                    combo['values'] = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
                    combos.append(combo)
                    combo.grid(row=row+1, column=col)
                    w = tk.Scale(frame, from_=0, to=max(image.width, image.height))
                    w.set(int(max(image.width, image.height) / 2))
                    scales.append(w)
                    w.grid(row=row, column=col+1, sticky=tk.N + tk.S)
                    n = tk.IntVar()
                    col += 1

                if count % 3 == 2:
                    row += 2
                    if horizontal:
                        row +=1
                    col = -1

                col += 1
                count += 1


            elif item.endswith(constants.extension):
                shutil.copyfile(os.path.join(origin, item), os.path.join(target, item))

    ok_button = tk.Button(bottom_frame, text="OK",
                          command=lambda: photo_ok(root, images, scales, combos, origin, target, plant))
    ok_button.pack(side=tk.LEFT, pady=10, ipadx=10)

    cancel_button = tk.Button(bottom_frame, text="Cancel", command=lambda: photo_cancel(root))
    cancel_button.pack(side=tk.LEFT, padx=10)

    root.mainloop()

def photo_cancel(root):
    root.destroy()


def photo_ok(root, images, scales, combos, origin, target, plant):
    i = 0
    for image in images:
        if (int(combos[i].get()) > 0):
            names = plant.split(' ')
            name = names[0][:1].lower() + names[len(names)-1][:1].lower() + combos[i].get() + constants.extension
            size = min(image.width, image.height)
            image = utils.crop_square(image, size, size, scales[i])
            image = image.resize((512, 512))

            image.save(os.path.join(origin, name))
            shutil.copyfile(os.path.join(origin, name), os.path.join(target, name))

            image = image.resize((128, 128))
            image.save(os.path.join(target, constants.thumbdir, name))
        i += 1

    root.destroy()


if __name__ == "__main__":
    cred = credentials.Certificate('D:\\Dev\\Keystore\\abherbs-backend-firebase-adminsdk-l5787-d877acd19f.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://abherbs-backend.firebaseio.com'
    })
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    refCount = db.reference('plants_to_update/count')
    count = refCount.get()
    refList = db.reference('plants_to_update/list')

    filepath = 'plants_to_upload.txt'
    with open(filepath) as fp:
        for line in fp:
            root = tk.Tk()
            items = line.rstrip().split(';')
            process_plant(
                order=items[0],
                family=items[1],
                plant=items[2],
            )
            upload_plant(
                order=items[0],
                family=items[1],
                plant=items[2],
            )
            refList.update({count: items[2]})
            # add_plant(
            #     id=count,
            #     order=items[0].strip(),
            #     family=items[1].strip(),
            #     plant=items[2].strip(),
            #     wikidata=items[3].strip(),
            #     flowering_from=items[4].strip(),
            #     flowering_to=items[5].strip(),
            #     height_from=items[6].strip(),
            #     height_to=items[7].strip(),
            #     color=items[8].strip(),
            #     habitat=items[9].strip(),
            #     petal=items[10].strip()
            # )
            count += 1