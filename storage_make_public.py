import sys

# [START storage_make_public]
from google.cloud import storage


def make_blob_public(bucket_name, blob_name):
    """Makes a blob publicly accessible."""
    # bucket_name = "your-bucket-name"
    # blob_name = "your-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.make_public()

    print(
        "Blob {} is publicly accessible at {}".format(
            blob.name, blob.public_url
        )
    )


# [END storage_make_public]

if __name__ == "__main__":
    make_blob_public(bucket_name=sys.argv[1], blob_name=sys.argv[2])