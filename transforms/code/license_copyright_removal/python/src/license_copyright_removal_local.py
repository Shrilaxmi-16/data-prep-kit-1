# (C) Copyright IBM Corp. 2024.
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#  http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

import os

from data_processing.data_access import DataAccessLocal
from license_copyright_removal_transform import (
    LicenseCopyrightRemoveTransform,
    COLUMN_KEY,
    LICENSE_KEY,
    COPYRIGHT_KEY,
)
import pyarrow.parquet as pq


# create parameters
input_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../test-data/input"))
output_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../output"))
local_conf = {
    "input_folder": input_folder,
    "output_folder": output_folder,
}

license_copyright_removal_params = {
    COLUMN_KEY: 'contents',
    COPYRIGHT_KEY: 'true',
    LICENSE_KEY: 'true',
}

if __name__ == "__main__":
    # Here we show how to run outside of ray
    # Filter transform needs a DataAccess to ready the domain list.
    data_access = DataAccessLocal(local_conf)
    # Create and configure the transform.
    transform = LicenseCopyrightRemoveTransform(license_copyright_removal_params)
    # Use the local data access to read a parquet table.
    table,_ = data_access.get_table(os.path.join(input_folder, "test1.parquet"))
    print(f"input table has {table.num_rows} rows")
    # Transform the table
    table_list, metadata = transform.transform(table)

    print(f"\noutput table has {table_list[0].num_rows} rows")
    print(f"output metadata : {metadata}")
