# pylint: disable=redefined-outer-name
import os
import mock
import pytest

from google.cloud.storage import client as gcs_client

from mlflow.store.artifact_repo import ArtifactRepository
from mlflow.store.gcs_artifact_repo import GCSArtifactRepository


@pytest.fixture
def gcs_mock():
    # Make sure that the environment variable isn't set to actually make calls
    old_G_APP_CREDS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/dev/null'

    yield mock.MagicMock(autospec=gcs_client)

    if old_G_APP_CREDS:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = old_G_APP_CREDS


def test_artifact_uri_factory():
    repo = ArtifactRepository.from_artifact_uri("gs://test_bucket/some/path", mock.Mock())
    assert isinstance(repo, GCSArtifactRepository)


def test_list_artifacts_empty(gcs_mock):
    repo = GCSArtifactRepository("gs://test_bucket/some/path", gcs_mock)
    gcs_mock.Client.return_value.get_bucket.return_value \
        .list_blobs.return_value = mock.MagicMock()
    assert repo.list_artifacts() == []


def test_list_artifacts(gcs_mock):
    artifact_root_path = "/experiment_id/run_id/"
    repo = GCSArtifactRepository("gs://test_bucket" + artifact_root_path, gcs_mock)

    # mocked bucket/blob structure
    # gs://test_bucket/experiment_id/run_id/
    #  |- file
    #  |- model
    #     |- model.pb

    # mocking a single blob returned by bucket.list_blobs iterator
    # https://googlecloudplatform.github.io/google-cloud-python/latest/storage/buckets.html#google.cloud.storage.bucket.Bucket.list_blobs

    # list artifacts at artifact root level
    obj_mock = mock.Mock()
    file_path = 'file'
    obj_mock.configure_mock(name=artifact_root_path + file_path, size=1)

    dir_mock = mock.Mock()
    dir_name = "model"
    dir_mock.configure_mock(prefixes=(artifact_root_path + dir_name + "/",))

    mock_results = mock.MagicMock()
    mock_results.configure_mock(pages=[dir_mock])
    mock_results.__iter__.return_value = [obj_mock]

    gcs_mock.Client.return_value.get_bucket.return_value\
        .list_blobs.return_value = mock_results

    artifacts = repo.list_artifacts(path=None)

    assert len(artifacts) == 2
    assert artifacts[0].path == file_path
    assert artifacts[0].is_dir is False
    assert artifacts[0].file_size == obj_mock.size
    assert artifacts[1].path == dir_name
    assert artifacts[1].is_dir is True
    assert artifacts[1].file_size is None


def test_list_artifacts_with_subdir(gcs_mock):
    artifact_root_path = "/experiment_id/run_id/"
    repo = GCSArtifactRepository("gs://test_bucket" + artifact_root_path, gcs_mock)

    # mocked bucket/blob structure
    # gs://test_bucket/experiment_id/run_id/
    #  |- model
    #     |- model.pb
    #     |- variables

    # list artifacts at sub directory level
    dir_name = "model"
    obj_mock = mock.Mock()
    file_path = dir_name + "/" + 'model.pb'
    obj_mock.configure_mock(name=artifact_root_path + file_path, size=1)

    subdir_mock = mock.Mock()
    subdir_name = dir_name + "/" + 'variables'
    subdir_mock.configure_mock(prefixes=(artifact_root_path + subdir_name + "/",))

    mock_results = mock.MagicMock()
    mock_results.configure_mock(pages=[subdir_mock])
    mock_results.__iter__.return_value = [obj_mock]

    gcs_mock.Client.return_value.get_bucket.return_value\
        .list_blobs.return_value = mock_results

    artifacts = repo.list_artifacts(path=dir_name)
    assert len(artifacts) == 2
    assert artifacts[0].path == file_path
    assert artifacts[0].is_dir is False
    assert artifacts[0].file_size == obj_mock.size
    assert artifacts[1].path == subdir_name
    assert artifacts[1].is_dir is True
    assert artifacts[1].file_size is None


def test_log_artifact(gcs_mock, tmpdir):
    repo = GCSArtifactRepository("gs://test_bucket/some/path", gcs_mock)

    d = tmpdir.mkdir("data")
    f = d.join("test.txt")
    f.write("hello world!")
    fpath = d + '/test.txt'
    fpath = fpath.strpath

    # This will call isfile on the code path being used,
    # thus testing that it's being called with an actually file path
    gcs_mock.Client.return_value.get_bucket.return_value.blob.return_value\
        .upload_from_filename.side_effect = os.path.isfile
    repo.log_artifact(fpath)

    gcs_mock.Client().get_bucket.assert_called_with('test_bucket')
    gcs_mock.Client().get_bucket().blob\
        .assert_called_with('some/path/test.txt')
    gcs_mock.Client().get_bucket().blob().upload_from_filename\
        .assert_called_with(fpath)


def test_log_artifacts(gcs_mock, tmpdir):
    repo = GCSArtifactRepository("gs://test_bucket/some/path", gcs_mock)

    subd = tmpdir.mkdir("data").mkdir("subdir")
    subd.join("a.txt").write("A")
    subd.join("b.txt").write("B")
    subd.join("c.txt").write("C")

    gcs_mock.Client.return_value.get_bucket.return_value.blob.return_value\
        .upload_from_filename.side_effect = os.path.isfile
    repo.log_artifacts(subd.strpath)

    gcs_mock.Client().get_bucket.assert_called_with('test_bucket')
    gcs_mock.Client().get_bucket().blob().upload_from_filename\
        .assert_has_calls([
            mock.call('%s/a.txt' % subd.strpath),
            mock.call('%s/b.txt' % subd.strpath),
            mock.call('%s/c.txt' % subd.strpath),
        ], any_order=True)


def test_download_artifacts(gcs_mock, tmpdir):
    repo = GCSArtifactRepository("gs://test_bucket/some/path", gcs_mock)

    def mkfile(fname):
        fname = fname.replace(tmpdir.strpath, '')
        f = tmpdir.join(fname)
        f.write("hello world!")
        return f.strpath

    gcs_mock.Client.return_value.get_bucket.return_value.get_blob.return_value\
        .download_to_filename.side_effect = mkfile

    open(repo._download_artifacts_into("test.txt", tmpdir.strpath)).read()
    gcs_mock.Client().get_bucket.assert_called_with('test_bucket')
    gcs_mock.Client().get_bucket().get_blob\
        .assert_called_with('some/path/test.txt')
    gcs_mock.Client().get_bucket().get_blob()\
        .download_to_filename.assert_called_with(tmpdir + "/test.txt")
