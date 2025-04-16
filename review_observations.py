import firebase_admin
import pillow_heif
from firebase_admin import credentials
from firebase_admin import db
from google.cloud import storage
from PIL import Image, ImageTk, ExifTags, ImageFile
import tkinter as tk
import storage_upload_file
import storage_make_public
import constants
import utils

class ReviewApp(tk.Tk):
    def __init__(self, observations):
        super().__init__()
        self.title("Observation Review")
        self.observations = list(observations.items())  # Convert to list of (key, observation) pairs
        self.current_index = 0

        # Create persistent frames
        self.observation_frame = tk.Frame(self)
        self.observation_frame.pack()
        self.bottom_frame = tk.Frame(self)
        self.bottom_frame.pack(side=tk.BOTTOM)

        # Create buttons (persistent across observations)
        self.ok_button = tk.Button(self.bottom_frame, text="OK")
        self.reject_button = tk.Button(self.bottom_frame, text="Reject")
        self.skip_button = tk.Button(self.bottom_frame, text="Skip", command=self.observation_skip)
        self.ok_button.pack(side=tk.LEFT, pady=10, ipadx=10)
        self.reject_button.pack(side=tk.LEFT, padx=10)
        self.skip_button.pack(side=tk.LEFT, padx=10)

        # Load the first observation if there are any and center the window
        if self.observations:
            self.load_observation(self.current_index)
            self.center_window()
        else:
            self.destroy()  # Close if no observations

    def center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"+{x}+{y}")

    def load_observation(self, index):
        """Load and display the observation at the given index."""
        if index >= len(self.observations):
            print("All observations reviewed.")
            self.destroy()  # Close window when done
            return

        key, observation = self.observations[index]

        # Clear the observation_frame
        for widget in self.observation_frame.winfo_children():
            widget.destroy()

        # Load images from storage
        storage_client = storage.Client(constants.project)
        bucket = storage_client.bucket(constants.bucket_name)
        paths = observation['photoPaths']
        self.images = []
        pillow_heif.register_heif_opener()
        for path in paths:
            blob = bucket.blob(path)
            local_path = constants.observationsdir + path[path.rindex('/'):]
            with open(local_path, "wb") as file_obj:
                blob.download_to_file(file_obj)
                image = Image.open(local_path)
                # Handle rotation
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
                    pass
                image.filename = local_path
                self.images.append(image)

        # Subframe for plant name
        plant_frame = tk.Frame(self.observation_frame)
        plant_frame.pack(fill='x')
        tk.Label(plant_frame, text=observation['plant']).pack()

        # Subframe for images and scales
        images_frame = tk.Frame(self.observation_frame)
        images_frame.pack()

        # Display images and scales
        self.photos = []
        self.scales = []
        cols = 2  # Maximum 2 images per row
        image_width = int(self.winfo_screenwidth() * 0.20)
        for idx, image in enumerate(self.images):
            pair_frame = tk.Frame(images_frame)
            pair_frame.grid(row=idx // cols, column=idx % cols, padx=10, pady=10)

            ratio = image.width / image.height
            image_height = int(image_width / ratio)
            photo = ImageTk.PhotoImage(image.resize((image_width, image_height), Image.Resampling.LANCZOS))
            self.photos.append(photo)
            label = tk.Label(pair_frame, image=photo)
            label.pack()

            if image.width > image.height:
                # Horizontal image: scale below
                w = tk.Scale(pair_frame, from_=0, to=max(image.width, image.height), orient=tk.HORIZONTAL)
                w.set(int(max(image.width, image.height) / 2))
                # w.pack(fill='x')
            else:
                # Vertical image: scale beside
                scale_frame = tk.Frame(pair_frame)
                scale_frame.pack(side=tk.RIGHT)
                w = tk.Scale(scale_frame, from_=0, to=max(image.width, image.height), orient=tk.VERTICAL)
                w.set(int(max(image.width, image.height) / 2))
                # w.pack(fill='y')
            self.scales.append(w)

        # Controls frame for coordinates, checkbox, and textbox
        controls_frame = tk.Frame(self.observation_frame)
        controls_frame.pack(pady=10)

        # Subframe for coordinates
        info_frame = tk.Frame(controls_frame)
        info_frame.pack(side=tk.TOP)

        # Retrieve and display longitude and latitude
        id = observation.get('id', 'N/A')
        tk.Label(info_frame, text=f"ID: {id}").pack(side=tk.TOP)

        # Subframe for coordinates
        coords_frame = tk.Frame(controls_frame)
        coords_frame.pack(side=tk.TOP)

        # Retrieve and display longitude and latitude
        longitude = observation.get('longitude', 'N/A')
        latitude = observation.get('latitude', 'N/A')
        tk.Label(coords_frame, text=f"Longitude: {longitude:.6f}" if isinstance(longitude, (
        int, float)) else f"Longitude: {longitude}").pack(side=tk.LEFT)
        tk.Label(coords_frame, text=f"Latitude: {latitude:.6f}" if isinstance(latitude, (
        int, float)) else f"Latitude: {latitude}").pack(side=tk.LEFT)

        # Subframe for controls
        controls_subframe = tk.Frame(controls_frame)
        controls_subframe.pack(side=tk.TOP)

        # Checkbox for 'Indoors'
        self.indoors_var = tk.BooleanVar()
        if 'indoors' in observation:
            self.indoors_var.set(observation['indoors'])
        else:
            self.indoors_var.set(False)
        tk.Checkbutton(controls_subframe, text="Indoors", variable=self.indoors_var).pack(side=tk.LEFT, padx=10)

        # Textbox for 'Rejected'
        tk.Label(controls_subframe, text="Rejected:").pack(side=tk.LEFT)
        self.rejected_entry = tk.Entry(controls_subframe, width=50)
        self.rejected_entry.pack(side=tk.LEFT, padx=10)

        # Update button commands for the current observation
        self.ok_button.config(command=lambda: self.observation_ok(key, observation))
        self.reject_button.config(command=lambda: self.observation_cancel(key, observation))

    def observation_ok(self, key, observation):
        """Handle OK button click."""
        observation['indoors'] = self.indoors_var.get()
        i = 0
        for image in self.images:
            extension = image.filename[image.filename.rindex('.'):]
            filename = image.filename
            if '.jpg' != extension:
                new_filename = filename.replace(extension, '.jpg')
                image.save(new_filename)
                storage_upload_file.upload_blob(constants.bucket_name, new_filename,
                                                observation['photoPaths'][i].replace(extension, '.jpg'), 'image/jpeg')
                storage_make_public.make_blob_public(constants.bucket_name,
                                                     observation['photoPaths'][i].replace(extension, '.jpg'))
            else:
                storage_make_public.make_blob_public(constants.bucket_name, observation['photoPaths'][i])

            size = min(image.width, image.height)
            image = utils.crop_square(image, size, size, self.scales[i])
            if size > 512:
                image = image.resize((512, 512), Image.Resampling.LANCZOS)
            webp_filename = filename.replace(extension, '.webp')
            image.save(webp_filename)
            storage_upload_file.upload_blob(constants.bucket_name, webp_filename,
                                            observation['photoPaths'][i].replace(extension, '.webp'), 'image/webp')
            storage_make_public.make_blob_public(constants.bucket_name,
                                                 observation['photoPaths'][i].replace(extension, '.webp'))
            i += 1
            image.close()

        observation['status'] = 'public'
        for j in range(len(observation['photoPaths'])):
            extension = observation['photoPaths'][j][observation['photoPaths'][j].rindex('.'):]
            observation['photoPaths'][j] = observation['photoPaths'][j].replace(extension, '.webp')

        ref_public_by_date.child(key).update(observation)
        ref_public_by_plant.child(observation['plant']).child('list').child(key).update(observation)
        self.update_observation(observation)

        # Move to next observation
        self.current_index += 1
        self.load_observation(self.current_index)

    def observation_cancel(self, key, observation):
        """Handle Cancel button click."""
        ref_public_by_date.child(key).delete()
        ref_public_by_plant.child(observation['plant']).child('list').child(key).delete()
        user = key[:key.index('_')]
        logs = ref_logs.child(user).get()
        for logs_key in logs.keys():
            log = logs[logs_key]
            if key in log.keys():
                ref_logs.child(user).child(logs_key).child(key).child('status').set('rejected')
                break

        rejected_text = self.rejected_entry.get().strip()
        if rejected_text:
            if 'note' in observation:
                observation['note'] += "\n" + rejected_text
            else:
                observation['note'] = rejected_text
        observation['status'] = 'rejected'
        self.update_observation(observation)

        # Move to next observation
        self.current_index += 1
        self.load_observation(self.current_index)

    def observation_skip(self):
        """Handle Skip button click."""
        self.current_index += 1
        self.load_observation(self.current_index)

    def update_observation(self, observation):
        """Update observation in the private database."""
        user = observation['id'][:observation['id'].index('_')]
        ref_private.child(user).child('by date').child('list').child(observation['id']).update(observation)
        ref_private.child(user).child('by plant').child(observation['plant']).child('list').child(
            observation['id']).update(observation)

if __name__ == "__main__":
    cred = credentials.Certificate(constants.certificate_firebase)
    firebase_admin.initialize_app(cred, {'databaseURL': constants.databaseURL})
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    ref_public_by_date = db.reference('observations/public/by date/list')
    ref_public_by_plant = db.reference('observations/public/by plant')
    ref_logs = db.reference('observations/logs')
    ref_private = db.reference('observations/by users')
    new_observations = ref_public_by_date.order_by_child('status').equal_to('review').get()

    # Create a single review application instance
    app = ReviewApp(new_observations)
    app.mainloop()