#!/usr/bin/env python

# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pandas as pd

from google.cloud import bigquery, storage
from wand.image import Image

# TODO Maybe Write Code to Copy Data from PDP to Project BigQuery?


def convert_pdfs(input_bucket_name, output_bucket_name, temp_directory):
    """Converts all pdfs in a bucket to png.

    Args:
      input_bucket_name (string): Bucket of Public PDFs
      output_bucket_name (string): Bucket for Converted PNGs
      temp_directory (string): Temporary Local Directory for coversion
    """

    # Get Images from Public Bucket
    client = storage.Client()
    input_bucket = client.get_bucket(input_bucket_name)
    output_bucket = client.get_bucket(output_bucket_name)

    # Create temp directory & all intermediate directories
    if not os.path.exists(temp_directory):
        os.makedirs(temp_directory)

    for blob in client.list_blobs(input_bucket):
        if (blob.name.endswith('.pdf')):

            pdf_basename = os.path.basename(blob.name)
            png_basename = pdf_basename.replace('.pdf', '.png')

            # Download the file to a local temp directory to convert
            temp_pdf = os.path.join(temp_directory, pdf_basename)
            temp_png = os.path.join(temp_directory, png_basename)

            print(f"Downloading {pdf_basename}")
            input_bucket.get_blob(pdf_basename).download_to_filename(temp_pdf)

            # Convert PDF to PNG
            print(f"Converting to PNG")
            with Image(filename=temp_pdf, resolution=300) as pdf:
                with pdf.convert('png') as png:
                    png.save(filename=temp_png)

            # Upload to GCS Bucket
            print(f"Uploading to Cloud Storage")
            output_bucket.blob(png_basename).upload_from_filename(temp_png)

            # Remove Temp files, Don't want to fill up our local storage
            print(f"Deleting temporary files\n")
            os.remove(temp_pdf)
            os.remove(temp_png)

    # Delete the entire temporary directory
    os.rmdir(temp_directory)


def bq_to_csv(project_id, dataset_id, input_bucket_name, output_bucket_name):
    """Fetches Data From BQ Dataset, uploads CSV to Cloud Storage Bucket

    Args:
      project_id (string): Project where dataset is stored
      dataset_id (string): Dataset ID
      input_bucket_name (string): Bucket with PDF files to convert
      output_bucket_name (string): Bucket for Converted PNGs and CSV
    """

    client = bigquery.Client(project_id)

    csv_uris = []

    # Extract Table Data into CSV
    for table_ref in client.list_tables(dataset_id):

        destination_uri = f"gs://{output_bucket_name}/{table_ref.table_id}.csv"

        csv_uris.append(destination_uri)

        table = client.get_table(table_ref)

        # Download CSV to change links to new bucket and pdf to png
        print(f"Processing {table_ref.table_id}")
        df = client.list_rows(table).to_dataframe()
        df.replace({
            input_bucket_name: output_bucket_name,
            r"\.pdf": ".png"
        }, regex=True, inplace=True)

        df.to_csv(destination_uri, index=False)

    return csv_uris
