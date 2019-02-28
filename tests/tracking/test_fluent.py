import mock
import os
import random

import pytest

import mlflow
import mlflow.tracking.fluent
from mlflow.entities import Experiment
from mlflow.tracking.fluent import _get_experiment_id, _get_experiment_id_from_env, \
    _EXPERIMENT_NAME_ENV_VAR, _EXPERIMENT_ID_ENV_VAR
from mlflow.utils.file_utils import TempDir


class HelperEnv:
    @classmethod
    def assert_values(cls, exp_id, name):
        assert os.environ.get(_EXPERIMENT_NAME_ENV_VAR) == name
        assert os.environ.get(_EXPERIMENT_ID_ENV_VAR) == exp_id

    @classmethod
    def set_values(cls, id=None, name=None):
        if id:
            os.environ[_EXPERIMENT_ID_ENV_VAR] = str(id)
        elif os.environ.get(_EXPERIMENT_ID_ENV_VAR):
            del os.environ[_EXPERIMENT_ID_ENV_VAR]

        if name:
            os.environ[_EXPERIMENT_NAME_ENV_VAR] = str(name)
        elif os.environ.get(_EXPERIMENT_NAME_ENV_VAR):
            del os.environ[_EXPERIMENT_NAME_ENV_VAR]


@pytest.fixture(autouse=True)
def reset_experiment_id():
    """
    This fixture resets the active experiment id *after* the execution of the test case in which
    its included
    """
    yield
    HelperEnv.set_values()
    mlflow.tracking.fluent._active_experiment_id = None


def test_get_experiment_id_from_env():
    # When no env variables are set
    HelperEnv.assert_values(None, None)
    assert _get_experiment_id_from_env() is None

    # set only ID
    random_id = random.randint(1, 1e6)
    HelperEnv.set_values(id=random_id)
    HelperEnv.assert_values(str(random_id), None)
    assert _get_experiment_id_from_env() == str(random_id)

    # set only name
    with TempDir(chdr=True):
        name = "random experiment %d" % random.randint(1, 1e6)
        exp_id = mlflow.create_experiment(name)
        assert exp_id is not None
        HelperEnv.set_values(name=name)
        HelperEnv.assert_values(None, name)
        assert _get_experiment_id_from_env() == exp_id

    # set both: assert that name variable takes precedence
    with TempDir(chdr=True):
        name = "random experiment %d" % random.randint(1, 1e6)
        exp_id = mlflow.create_experiment(name)
        assert exp_id is not None
        random_id = random.randint(1, 1e6)
        HelperEnv.set_values(name=name, id=random_id)
        HelperEnv.assert_values(str(random_id), name)
        assert _get_experiment_id_from_env() == exp_id


def test_get_experiment_id_with_active_experiment_returns_active_experiment_id():
    # Create a new experiment and set that as active experiment
    with TempDir(chdr=True):
        name = "Random experiment %d" % random.randint(1, 1e6)
        exp_id = mlflow.create_experiment(name)
        assert exp_id is not None
        mlflow.set_experiment(name)
        assert _get_experiment_id() == exp_id


def test_get_experiment_id_with_no_active_experiments_returns_default_experiment_id():
    assert _get_experiment_id() == Experiment.DEFAULT_EXPERIMENT_ID


def test_get_experiment_id_in_databricks_detects_notebook_id_by_default():
    notebook_id = 768

    with mock.patch("mlflow.tracking.fluent.is_in_databricks_notebook") as notebook_detection_mock,\
            mock.patch("mlflow.tracking.fluent.get_notebook_id") as notebook_id_mock:
        notebook_detection_mock.return_value = True
        notebook_id_mock.return_value = notebook_id
        assert _get_experiment_id() == notebook_id


def test_get_experiment_id_in_databricks_with_active_experiment_returns_active_experiment_id():
    with TempDir(chdr=True):
        exp_name = "random experiment %d" % random.randint(1, 1e6)
        exp_id = mlflow.create_experiment(exp_name)
        mlflow.set_experiment(exp_name)
        notebook_id = exp_id + 73

    with mock.patch("mlflow.tracking.fluent.is_in_databricks_notebook") as notebook_detection_mock,\
            mock.patch("mlflow.tracking.fluent.get_notebook_id") as notebook_id_mock:
        notebook_detection_mock.return_value = True
        notebook_id_mock.return_value = notebook_id

        assert _get_experiment_id() != notebook_id
        assert _get_experiment_id() == exp_id


def test_get_experiment_id_in_databricks_with_experiment_defined_in_env_returns_env_experiment_id():
    with TempDir(chdr=True):
        exp_name = "random experiment %d" % random.randint(1, 1e6)
        exp_id = mlflow.create_experiment(exp_name)
        notebook_id = exp_id + 73
        HelperEnv.set_values(id=exp_id)

    with mock.patch("mlflow.tracking.fluent.is_in_databricks_notebook") as notebook_detection_mock,\
            mock.patch("mlflow.tracking.fluent.get_notebook_id") as notebook_id_mock:
        notebook_detection_mock.side_effect = lambda *args, **kwargs: True
        notebook_id_mock.side_effect = lambda *args, **kwargs: notebook_id

        assert _get_experiment_id() != notebook_id
        assert _get_experiment_id() == exp_id
