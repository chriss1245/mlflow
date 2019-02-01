from __future__ import print_function

import os
import logging
import json
import mock

import pytest
import numpy as np
import pandas as pd
import pandas.testing
import sklearn.datasets as datasets
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader

import mlflow.pyfunc as pyfunc
import mlflow.pytorch
import mlflow.pyfunc.scoring_server as pyfunc_scoring_server
from mlflow import tracking
from mlflow.exceptions import MlflowException
from mlflow.models import Model
from mlflow.pytorch import pickle_module as mlflow_pytorch_pickle_module
from mlflow.utils.environment import _mlflow_conda_env
from mlflow.utils.file_utils import TempDir
from mlflow.utils.model_utils import _get_flavor_configuration

_logger = logging.getLogger(__name__)

# This test suite is included as a code dependency when testing PyTorch model scoring in new
# processes and docker containers. In these environments, the `tests` module is not available.
# Therefore, we attempt to import from `tests` and gracefully emit a warning if it's unavailable.
try:
    from tests.helper_functions import pyfunc_serve_and_score_model
    from tests.helper_functions import score_model_in_sagemaker_docker_container
except ImportError:
    _logger.warning(
        "Failed to import test helper functions. Tests depending on these functions may fail!")


@pytest.fixture(scope='module')
def data():
    iris = datasets.load_iris()
    data = pd.DataFrame(data=np.c_[iris['data'], iris['target']],
                        columns=iris['feature_names'] + ['target'])
    y = data['target']
    x = data.drop('target', axis=1)
    return x, y


def get_dataset(data):
    x, y = data
    dataset = [(xi.astype(np.float32), yi.astype(np.float32))
               for xi, yi in zip(x.values, y.values)]
    return dataset


def train_model(model, data):
    dataset = get_dataset(data)
    criterion = nn.MSELoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    batch_size = 16
    num_workers = 4
    dataloader = DataLoader(dataset, batch_size=batch_size,
                            num_workers=num_workers, shuffle=True, drop_last=False)

    model.train()
    for _ in range(5):
        for batch in dataloader:
            optimizer.zero_grad()
            batch_size = batch[0].shape[0]
            y_pred = model(batch[0]).squeeze(dim=1)
            loss = criterion(y_pred, batch[1])
            loss.backward()
            optimizer.step()


@pytest.fixture(scope='module')
def sequential_model(data):
    model = nn.Sequential(
        nn.Linear(4, 3),
        nn.ReLU(),
        nn.Linear(3, 1),
    )

    train_model(model=model, data=data)
    return model


def get_subclassed_model_definition():
    """
    Defines a PyTorch model class that inherits from ``torch.nn.Module``. This method can be invoked
    within a pytest fixture to define the model class in the ``__main__`` scope. Alternatively, it
    can be invoked within a module to define the class in the module's scope.
    """
    class SubclassedModel(torch.nn.Module):

        def __init__(self):
            super(SubclassedModel, self).__init__()
            self.linear = torch.nn.Linear(4, 1)

        def forward(self, x):
            y_pred = self.linear(x)
            return y_pred

    return SubclassedModel


@pytest.fixture(scope='module')
def main_scoped_subclassed_model(data):
    """
    A custom PyTorch model inheriting from ``torch.nn.Module`` whose class is defined in the
    "__main__" scope.
    """
    model_class = get_subclassed_model_definition()
    model = model_class()
    train_model(model=model, data=data)
    return model


class ModuleScopedSubclassedModel(get_subclassed_model_definition()):
    """
    A custom PyTorch model class defined in the test module scope. This is a subclass of
    ``torch.nn.Module``.
    """


@pytest.fixture(scope='module')
def module_scoped_subclassed_model(data):
    """
    A custom PyTorch model inheriting from ``torch.nn.Module`` whose class is defined in the test
    module scope.
    """
    model = ModuleScopedSubclassedModel()
    train_model(model=model, data=data)
    return model


@pytest.fixture
def model_path(tmpdir):
    return os.path.join(str(tmpdir), "model")


@pytest.fixture
def pytorch_custom_env(tmpdir):
    conda_env = os.path.join(str(tmpdir), "conda_env.yml")
    _mlflow_conda_env(
            conda_env,
            additional_conda_deps=["pytorch", "torchvision", "pytest"],
            additional_conda_channels=["pytorch"])
    return conda_env


def _predict(model, data):
    dataset = get_dataset(data)
    batch_size = 16
    num_workers = 4
    dataloader = DataLoader(dataset, batch_size=batch_size,
                            num_workers=num_workers, shuffle=False, drop_last=False)
    predictions = np.zeros((len(dataloader.sampler),))
    model.eval()
    with torch.no_grad():
        for i, batch in enumerate(dataloader):
            y_preds = model(batch[0]).squeeze(dim=1).numpy()
            predictions[i * batch_size:(i + 1) * batch_size] = y_preds
    return predictions


@pytest.fixture(scope='module')
def sequential_predicted(sequential_model, data):
    return _predict(sequential_model, data)


def test_log_model(sequential_model, data, sequential_predicted):
    old_uri = tracking.get_tracking_uri()
    # should_start_run tests whether or not calling log_model() automatically starts a run.
    for should_start_run in [False, True]:
        with TempDir(chdr=True, remove_on_exit=True) as tmp:
            try:
                tracking.set_tracking_uri(tmp.path("test"))
                if should_start_run:
                    mlflow.start_run()

                mlflow.pytorch.log_model(sequential_model, artifact_path="pytorch")

                # Load model
                run_id = mlflow.active_run().info.run_uuid
                sequential_model_loaded = mlflow.pytorch.load_model("pytorch", run_id=run_id)

                test_predictions = _predict(sequential_model_loaded, data)
                np.testing.assert_array_equal(test_predictions, sequential_predicted)
            finally:
                mlflow.end_run()
                tracking.set_tracking_uri(old_uri)


def test_raise_exception(sequential_model):
    with TempDir(chdr=True, remove_on_exit=True) as tmp:
        path = tmp.path("model")
        with pytest.raises(MlflowException):
            mlflow.pytorch.load_model(path)

        with pytest.raises(TypeError):
            mlflow.pytorch.save_model([1, 2, 3], path)

        mlflow.pytorch.save_model(sequential_model, path)
        with pytest.raises(RuntimeError):
            mlflow.pytorch.save_model(sequential_model, path)

        from mlflow import sklearn
        import sklearn.neighbors as knn
        import pickle
        path = tmp.path("knn.pkl")
        knn = knn.KNeighborsClassifier()
        with open(path, "wb") as f:
            pickle.dump(knn, f)
        path = tmp.path("knn")
        sklearn.save_model(knn, path=path)
        with pytest.raises(MlflowException):
            mlflow.pytorch.load_model(path)


def test_save_and_load_model(sequential_model, model_path, data, sequential_predicted):
    mlflow.pytorch.save_model(sequential_model, model_path)

    # Loading pytorch model
    sequential_model_loaded = mlflow.pytorch.load_model(model_path)
    np.testing.assert_array_equal(_predict(sequential_model_loaded, data), sequential_predicted)

    # Loading pyfunc model
    pyfunc_loaded = mlflow.pyfunc.load_pyfunc(model_path)
    np.testing.assert_array_almost_equal(
        pyfunc_loaded.predict(data[0]).values[:, 0], sequential_predicted, decimal=4)


def test_model_save_persists_specified_conda_env_in_mlflow_model_directory(
        sequential_model, model_path, pytorch_custom_env):
    mlflow.pytorch.save_model(
            pytorch_model=sequential_model, path=model_path, conda_env=pytorch_custom_env)

    pyfunc_conf = _get_flavor_configuration(model_path=model_path, flavor_name=pyfunc.FLAVOR_NAME)
    saved_conda_env_path = os.path.join(model_path, pyfunc_conf[pyfunc.ENV])
    assert os.path.exists(saved_conda_env_path)
    assert saved_conda_env_path != pytorch_custom_env

    with open(pytorch_custom_env, "r") as f:
        pytorch_custom_env_text = f.read()
    with open(saved_conda_env_path, "r") as f:
        saved_conda_env_text = f.read()
    assert saved_conda_env_text == pytorch_custom_env_text


def test_model_save_accepts_conda_env_as_dict(sequential_model, model_path):
    conda_env = dict(mlflow.pytorch.DEFAULT_CONDA_ENV)
    conda_env["dependencies"].append("pytest")
    mlflow.pytorch.save_model(pytorch_model=sequential_model, path=model_path, conda_env=conda_env)

    pyfunc_conf = _get_flavor_configuration(model_path=model_path, flavor_name=pyfunc.FLAVOR_NAME)
    saved_conda_env_path = os.path.join(model_path, pyfunc_conf[pyfunc.ENV])
    assert os.path.exists(saved_conda_env_path)

    with open(saved_conda_env_path, "r") as f:
        saved_conda_env_parsed = yaml.safe_load(f)
    assert saved_conda_env_parsed == conda_env


def test_model_log_persists_specified_conda_env_in_mlflow_model_directory(
        sequential_model, pytorch_custom_env):
    artifact_path = "model"
    with mlflow.start_run():
        mlflow.pytorch.log_model(pytorch_model=sequential_model,
                                 artifact_path=artifact_path,
                                 conda_env=pytorch_custom_env)
        run_id = mlflow.active_run().info.run_uuid
    model_path = tracking.utils._get_model_log_dir(artifact_path, run_id)

    pyfunc_conf = _get_flavor_configuration(model_path=model_path, flavor_name=pyfunc.FLAVOR_NAME)
    saved_conda_env_path = os.path.join(model_path, pyfunc_conf[pyfunc.ENV])
    assert os.path.exists(saved_conda_env_path)
    assert saved_conda_env_path != pytorch_custom_env

    with open(pytorch_custom_env, "r") as f:
        pytorch_custom_env_text = f.read()
    with open(saved_conda_env_path, "r") as f:
        saved_conda_env_text = f.read()
    assert saved_conda_env_text == pytorch_custom_env_text


def test_model_save_without_specified_conda_env_uses_default_env_with_expected_dependencies(
        sequential_model, model_path):
    mlflow.pytorch.save_model(pytorch_model=sequential_model, path=model_path, conda_env=None)

    pyfunc_conf = _get_flavor_configuration(model_path=model_path, flavor_name=pyfunc.FLAVOR_NAME)
    conda_env_path = os.path.join(model_path, pyfunc_conf[pyfunc.ENV])
    with open(conda_env_path, "r") as f:
        conda_env = yaml.safe_load(f)

    assert conda_env == mlflow.pytorch.DEFAULT_CONDA_ENV


def test_model_log_without_specified_conda_env_uses_default_env_with_expected_dependencies(
        sequential_model):
    artifact_path = "model"
    with mlflow.start_run():
        mlflow.pytorch.log_model(pytorch_model=sequential_model,
                                 artifact_path=artifact_path,
                                 conda_env=None)
        run_id = mlflow.active_run().info.run_uuid
    model_path = tracking.utils._get_model_log_dir(artifact_path, run_id)

    pyfunc_conf = _get_flavor_configuration(model_path=model_path, flavor_name=pyfunc.FLAVOR_NAME)
    conda_env_path = os.path.join(model_path, pyfunc_conf[pyfunc.ENV])
    with open(conda_env_path, "r") as f:
        conda_env = yaml.safe_load(f)

    assert conda_env == mlflow.pytorch.DEFAULT_CONDA_ENV


def test_load_model_with_differing_pytorch_version_logs_warning(sequential_model, model_path):
    mlflow.pytorch.save_model(pytorch_model=sequential_model, path=model_path)
    saver_pytorch_version = "1.0"
    model_config_path = os.path.join(model_path, "MLmodel")
    model_config = Model.load(model_config_path)
    model_config.flavors[mlflow.pytorch.FLAVOR_NAME]["pytorch_version"] = saver_pytorch_version
    model_config.save(model_config_path)

    log_messages = []

    def custom_warn(message_text, *args, **kwargs):
        log_messages.append(message_text % args % kwargs)

    loader_pytorch_version = "0.8.2"
    with mock.patch("mlflow.pytorch._logger.warning") as warn_mock,\
            mock.patch("torch.__version__") as torch_version_mock:
        torch_version_mock.__str__ = lambda *args, **kwargs: loader_pytorch_version
        warn_mock.side_effect = custom_warn
        mlflow.pytorch.load_model(path=model_path)

    assert any([
        "does not match installed PyTorch version" in log_message and
        saver_pytorch_version in log_message and
        loader_pytorch_version in log_message
        for log_message in log_messages
    ])


def test_pyfunc_model_serving_with_module_scoped_subclassed_model_and_default_conda_env(
        module_scoped_subclassed_model, model_path, data):
    mlflow.pytorch.save_model(
        path=model_path,
        pytorch_model=module_scoped_subclassed_model,
        conda_env=None,
        code_paths=[__file__])

    scoring_response = pyfunc_serve_and_score_model(
            model_path=model_path,
            data=data[0],
            content_type=pyfunc_scoring_server.CONTENT_TYPE_JSON_SPLIT_ORIENTED,
            extra_args=["--no-conda"])
    assert scoring_response.status_code == 200

    deployed_model_preds = pd.DataFrame(json.loads(scoring_response.content))
    np.testing.assert_array_almost_equal(
        deployed_model_preds.values[:, 0],
        _predict(model=module_scoped_subclassed_model, data=data),
        decimal=4)


def test_pyfunc_model_serving_with_main_scoped_subclassed_model_and_custom_pickle_module(
        main_scoped_subclassed_model, model_path, data):
    mlflow.pytorch.save_model(
        path=model_path,
        pytorch_model=main_scoped_subclassed_model,
        conda_env=None,
        pickle_module=mlflow_pytorch_pickle_module)

    scoring_response = pyfunc_serve_and_score_model(
            model_path=model_path,
            data=data[0],
            content_type=pyfunc_scoring_server.CONTENT_TYPE_JSON_SPLIT_ORIENTED,
            extra_args=["--no-conda"])
    assert scoring_response.status_code == 200

    deployed_model_preds = pd.DataFrame(json.loads(scoring_response.content))
    np.testing.assert_array_almost_equal(
        deployed_model_preds.values[:, 0],
        _predict(model=main_scoped_subclassed_model, data=data),
        decimal=4)


def test_load_model_succeeds_with_dependencies_specified_via_code_paths(
        module_scoped_subclassed_model, model_path, data):
    # Save a PyTorch model whose class is defined in the current test suite. Because the
    # `tests` module is not available when the model is deployed for local scoring, we include
    # the test suite file as a code dependency
    mlflow.pytorch.save_model(
        path=model_path,
        pytorch_model=module_scoped_subclassed_model,
        conda_env=None,
        code_paths=[__file__])

    # Define a custom pyfunc model that loads a PyTorch model artifact using
    # `mlflow.pytorch.load_model`
    class TorchValidatorModel(pyfunc.PythonModel):

        def load_context(self, context):
            self.pytorch_model = mlflow.pytorch.load_model(context.artifacts["pytorch_model"])

        def predict(self, context, model_input):
            with torch.no_grad():
                input_tensor = torch.from_numpy(model_input.values.astype(np.float32))
                output_tensor = self.pytorch_model(input_tensor)
                return pd.DataFrame(output_tensor.numpy())

    pyfunc_artifact_path = "pyfunc_model"
    with mlflow.start_run():
        pyfunc.log_model(artifact_path=pyfunc_artifact_path,
                         python_model=TorchValidatorModel(),
                         artifacts={
                            "pytorch_model": model_path,
                         })
        pyfunc_run_id = mlflow.active_run().info.run_uuid

    pyfunc_model_path = tracking.utils._get_model_log_dir(pyfunc_artifact_path, pyfunc_run_id)

    # Deploy the custom pyfunc model and ensure that it is able to successfully load its
    # constituent PyTorch model via `mlflow.pytorch.load_model`
    scoring_response = pyfunc_serve_and_score_model(
            model_path=pyfunc_model_path,
            data=data[0],
            content_type=pyfunc_scoring_server.CONTENT_TYPE_JSON_SPLIT_ORIENTED,
            extra_args=["--no-conda"])
    assert scoring_response.status_code == 200

    deployed_model_preds = pd.DataFrame(json.loads(scoring_response.content))
    np.testing.assert_array_almost_equal(
        deployed_model_preds.values[:, 0],
        _predict(model=module_scoped_subclassed_model, data=data),
        decimal=4)


@pytest.mark.release
def test_sagemaker_docker_model_scoring_with_sequential_model_and_default_conda_env(
        model, model_path, data, sequential_predicted):
    mlflow.pytorch.save_model(pytorch_model=model, path=model_path, conda_env=None)

    scoring_response = score_model_in_sagemaker_docker_container(
            model_path=model_path,
            data=data[0],
            content_type=pyfunc_scoring_server.CONTENT_TYPE_JSON_SPLIT_ORIENTED,
            flavor=mlflow.pyfunc.FLAVOR_NAME,
            activity_polling_timeout_seconds=360)
    deployed_model_preds = pd.DataFrame(json.loads(scoring_response.content))

    np.testing.assert_array_almost_equal(
        deployed_model_preds.values[:, 0],
        sequential_predicted,
        decimal=4)
