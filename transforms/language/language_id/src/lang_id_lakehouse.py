import os
import sys

from data_processing.ray import TransformLauncher
from data_processing.utils import ParamsUtils
from lang_id_implementation import (
    PARAM_MODEL_KIND,
    PARAM_MODEL_PATH,
    LangIdentificationTableTransformConfiguration,
)
from lang_models import KIND_FASTTEXT


print(os.environ)
# create launcher
launcher = TransformLauncher(transform_runtime_config=LangIdentificationTableTransformConfiguration())
# create parameters

s3_cred = {
    "access_key": os.environ.get("COS_ACCESS_KEY", "access"),
    "secret_key": os.environ.get("COS_SECRET_KEY", "secret"),
    "cos_url": "https://s3.us-east.cloud-object-storage.appdomain.cloud",
}

# Configure lakehouse unit test tables
lakehouse_config = {
    "lh_environment": "STAGING",
    "input_table": "academic.ieee_lh_unittest",
    "input_dataset": "",
    "input_version": "main",
    "output_table": "academic.ieee_lang_id_0304_02",
    "output_path": "lh-test/tables/academic/ieee_lang_id_0304_02",
    "token": "YOUR LAKEHOUSE TOKEN",
}

worker_options = {"num_cpus": 1}
code_location = {"github": "github", "commit_hash": "12345", "path": "path"}
params = {
    "run_locally": True,
    "max_files": -1,
    "s3_cred": ParamsUtils.convert_to_ast(s3_cred),
    "lh_config": ParamsUtils.convert_to_ast(lakehouse_config),
    "worker_options": ParamsUtils.convert_to_ast(worker_options),
    "num_workers": 2,
    "checkpointing": False,
    "pipeline_id": "pipeline_id",
    "job_id": "job_id",
    "creation_delay": 0,
    "code_location": ParamsUtils.convert_to_ast(code_location),
    PARAM_MODEL_KIND: KIND_FASTTEXT,
    PARAM_MODEL_PATH: "PATH TO YOUR MODEL",
}
sys.argv = ParamsUtils.dict_to_req(d=params)

# launch
launcher.launch()
