from itertools import combinations

import json
import pytest
import uuid
from unittest import mock

from mlflow.entities.model_registry import RegisteredModelTag, ModelVersionTag
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_uc_registry_messages_pb2 import (
    CreateRegisteredModelRequest,
    UpdateRegisteredModelRequest,
    DeleteRegisteredModelRequest,
    GetRegisteredModelRequest,
    SearchRegisteredModelsRequest,
    CreateModelVersionRequest,
    GetModelVersionRequest,
    UpdateModelVersionRequest,
    DeleteModelVersionRequest,
    SearchModelVersionsRequest,
    GetModelVersionDownloadUriRequest,
)
from mlflow.store._unity_catalog.registry.rest_store import UcModelRegistryStore
from mlflow.utils.proto_json_utils import message_to_json
from mlflow.utils.rest_utils import MlflowHostCreds
from tests.helper_functions import mock_http_200


def host_creds():
    return MlflowHostCreds("https://hello")


@pytest.fixture
def store():
    return UcModelRegistryStore(host_creds)


def _args(endpoint, method, json_body):
    res = {
        "host_creds": host_creds(),
        "endpoint": f"/api/2.0/mlflow/unity-catalog/{endpoint}",
        "method": method,
    }
    if method == "GET":
        res["params"] = json.loads(json_body)
    else:
        res["json"] = json.loads(json_body)
    return res


def _verify_requests(http_request, endpoint, method, proto_message):
    json_body = message_to_json(proto_message)
    http_request.assert_any_call(**(_args(endpoint, method, json_body)))


def _expected_unsupported_method_error_message(method):
    return f"Method '{method}' is unsupported for models in the Unity Catalog"


def _expected_unsupported_arg_error_message(arg):
    return f"Argument '{arg}' is unsupported for models in the Unity Catalog"


def _verify_all_requests(http_request, endpoints, proto_message):
    json_body = message_to_json(proto_message)
    http_request.assert_has_calls(
        [mock.call(**(_args(endpoint, method, json_body))) for endpoint, method in endpoints]
    )


@mock_http_200
def test_create_registered_model(mock_http, store):
    description = "best model ever"
    store.create_registered_model(name="model_1", description=description)
    _verify_requests(
        mock_http,
        "registered-models/create",
        "POST",
        CreateRegisteredModelRequest(name="model_1", description=description),
    )


def test_create_registered_model_with_tags_unsupported(store):
    tags = [
        RegisteredModelTag(key="key", value="value"),
        RegisteredModelTag(key="anotherKey", value="some other value"),
    ]
    description = "best model ever"
    with pytest.raises(MlflowException, match=_expected_unsupported_arg_error_message("tags")):
        store.create_registered_model(name="model_1", tags=tags, description=description)


@mock_http_200
def test_update_registered_model_name(mock_http, store):
    name = "model_1"
    new_name = "model_2"
    with pytest.raises(
        MlflowException, match=_expected_unsupported_method_error_message("rename_registered_model")
    ):
        store.rename_registered_model(name=name, new_name=new_name)


@mock_http_200
def test_update_registered_model_description(mock_http, store):
    name = "model_1"
    description = "test model"
    store.update_registered_model(name=name, description=description)
    _verify_requests(
        mock_http,
        "registered-models/update",
        "PATCH",
        UpdateRegisteredModelRequest(name=name, description=description),
    )


@mock_http_200
def test_delete_registered_model(mock_http, store):
    name = "model_1"
    store.delete_registered_model(name=name)
    _verify_requests(
        mock_http, "registered-models/delete", "DELETE", DeleteRegisteredModelRequest(name=name)
    )


@mock_http_200
def test_search_registered_model(mock_http, store):
    store.search_registered_models()
    _verify_requests(mock_http, "registered-models/search", "GET", SearchRegisteredModelsRequest())
    params_list = [
        {"max_results": 400},
        {"page_token": "blah"},
    ]
    # test all combination of params
    for sz in range(3):
        for combination in combinations(params_list, sz):
            params = {k: v for d in combination for k, v in d.items()}
            store.search_registered_models(**params)
            _verify_requests(
                mock_http,
                "registered-models/search",
                "GET",
                SearchRegisteredModelsRequest(**params),
            )


def test_search_registered_models_invalid_args(store):
    params_list = [
        {"filter_string": "model = 'yo'"},
        {"order_by": ["x", "Y"]},
    ]
    # test all combination of invalid params
    for sz in range(1, 3):
        for combination in combinations(params_list, sz):
            params = {k: v for d in combination for k, v in d.items()}
            with pytest.raises(
                MlflowException, match="unsupported for models in the Unity Catalog"
            ):
                store.search_registered_models(**params)


@mock_http_200
def test_get_registered_model(mock_http, store):
    name = "model_1"
    store.get_registered_model(name=name)
    _verify_requests(
        mock_http, "registered-models/get", "GET", GetRegisteredModelRequest(name=name)
    )


def test_get_latest_versions_unsupported(store):
    name = "model_1"
    expected_err_msg = _expected_unsupported_method_error_message("get_latest_versions")
    with pytest.raises(MlflowException, match=expected_err_msg):
        store.get_latest_versions(name=name)
    with pytest.raises(MlflowException, match=expected_err_msg):
        store.get_latest_versions(name=name, stages=["Production"])


def test_set_registered_model_tag_unsupported(store):
    name = "model_1"
    tag = RegisteredModelTag(key="key", value="value")
    expected_err_msg = _expected_unsupported_method_error_message("set_registered_model_tag")
    with pytest.raises(MlflowException, match=expected_err_msg):
        store.set_registered_model_tag(name=name, tag=tag)


def test_delete_registered_model_tag_unsupported(store):
    name = "model_1"
    expected_err_msg = _expected_unsupported_method_error_message("delete_registered_model_tag")
    with pytest.raises(MlflowException, match=expected_err_msg):
        store.delete_registered_model_tag(name=name, key="key")


@mock_http_200
def test_create_model_version(mock_http, store):
    store.create_model_version("model_1", "path/to/source")
    _verify_requests(
        mock_http,
        "model-versions/create",
        "POST",
        CreateModelVersionRequest(name="model_1", source="path/to/source"),
    )

    # test optional fields
    run_id = uuid.uuid4().hex
    description = "version description"
    store.create_model_version(
        "model_1",
        "path/to/source",
        run_id,
        description=description,
    )
    _verify_requests(
        mock_http,
        "model-versions/create",
        "POST",
        CreateModelVersionRequest(
            name="model_1",
            source="path/to/source",
            run_id=run_id,
            description=description,
        ),
    )


def test_create_model_version_unsupported_fields(store):
    with pytest.raises(MlflowException, match=_expected_unsupported_arg_error_message("run_link")):
        store.create_model_version(name="mymodel", source="mysource", run_link="https://google.com")
    with pytest.raises(MlflowException, match=_expected_unsupported_arg_error_message("tags")):
        store.create_model_version(
            name="mymodel", source="mysource", tags=[ModelVersionTag("a", "b")]
        )


def test_transition_model_version_stage_unsupported(store):
    name = "model_1"
    version = "5"
    with pytest.raises(
        MlflowException,
        match=_expected_unsupported_method_error_message("transition_model_version_stage"),
    ):
        store.transition_model_version_stage(
            name=name, version=version, stage="prod", archive_existing_versions=True
        )


@mock_http_200
def test_update_model_version_description(mock_http, store):
    name = "model_1"
    version = "5"
    description = "test model version"
    store.update_model_version(name=name, version=version, description=description)
    _verify_requests(
        mock_http,
        "model-versions/update",
        "PATCH",
        UpdateModelVersionRequest(name=name, version=version, description="test model version"),
    )


@mock_http_200
def test_delete_model_version(mock_http, store):
    name = "model_1"
    version = "12"
    store.delete_model_version(name=name, version=version)
    _verify_requests(
        mock_http,
        "model-versions/delete",
        "DELETE",
        DeleteModelVersionRequest(name=name, version=version),
    )


@mock_http_200
def test_get_model_version_details(mock_http, store):
    name = "model_11"
    version = "8"
    store.get_model_version(name=name, version=version)
    _verify_requests(
        mock_http, "model-versions/get", "GET", GetModelVersionRequest(name=name, version=version)
    )


@mock_http_200
def test_get_model_version_download_uri(mock_http, store):
    name = "model_11"
    version = "8"
    store.get_model_version_download_uri(name=name, version=version)
    _verify_requests(
        mock_http,
        "model-versions/get-download-uri",
        "GET",
        GetModelVersionDownloadUriRequest(name=name, version=version),
    )


@mock_http_200
def test_search_model_versions(mock_http, store):
    store.search_model_versions(filter_string="name='model_12'")
    _verify_requests(
        mock_http,
        "model-versions/search",
        "GET",
        SearchModelVersionsRequest(filter="name='model_12'"),
    )


def test_set_model_version_tag_unsupported(store):
    name = "model_1"
    tag = ModelVersionTag(key="key", value="value")
    with pytest.raises(
        MlflowException, match=_expected_unsupported_method_error_message("set_model_version_tag")
    ):
        store.set_model_version_tag(name=name, version="1", tag=tag)


def test_delete_model_version_tag_unsupported(store):
    name = "model_1"
    with pytest.raises(
        MlflowException,
        match=_expected_unsupported_method_error_message("delete_model_version_tag"),
    ):
        store.delete_model_version_tag(name=name, version="1", key="key")
