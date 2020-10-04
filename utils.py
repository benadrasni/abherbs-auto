

def crop_square(img, crop_width, crop_height, scale):
    img_width, img_height = img.size
    center = scale.get()
    if img_width > img_height:
        return img.crop((min(max(0, (img_width - crop_width) // 2 - (img_width // 2 - center)), img_width - crop_width),
                         0,
                         max(min(img_width, (img_width + crop_width) // 2 - (img_width // 2 - center)), crop_width),
                         crop_height))
    else:
        return img.crop((0,
                        min(max(0, (img_height - crop_height) // 2 - (img_height // 2 - center)), img_height - crop_height),
                        crop_width,
                        max(min(img_height, (img_height + crop_height) // 2 - (img_height // 2 - center)), crop_height)))