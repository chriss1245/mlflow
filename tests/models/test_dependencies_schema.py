from mlflow.models.dependencies_schema import (
    DependenciesSchemas,
    VectorSearchIndexSchema,
    _get_dependencies_schema,
    _get_vector_search_schema,
    set_vector_search_schema,
)


def test_vector_search_index_creation():
    vsi = VectorSearchIndexSchema(
        name="index-name",
        primary_key="primary-key",
        text_column="text-column",
        doc_uri="doc-uri",
        other_columns=["column1", "column2"],
    )
    assert vsi.name == "index-name"
    assert vsi.primary_key == "primary-key"
    assert vsi.text_column == "text-column"
    assert vsi.doc_uri == "doc-uri"
    assert vsi.other_columns == ["column1", "column2"]


def test_vector_search_index_to_dict():
    vsi = VectorSearchIndexSchema(
        name="index-name",
        primary_key="primary-key",
        text_column="text-column",
        doc_uri="doc-uri",
        other_columns=["column1", "column2"],
    )
    expected_dict = {
        "vector_search_index": [
            {
                "name": "index-name",
                "primary_key": "primary-key",
                "text_column": "text-column",
                "doc_uri": "doc-uri",
                "other_columns": ["column1", "column2"],
            }
        ]
    }
    assert vsi.to_dict() == expected_dict


def test_vector_search_index_from_dict():
    data = {
        "name": "index-name",
        "primary_key": "primary-key",
        "text_column": "text-column",
        "doc_uri": "doc-uri",
        "other_columns": ["column1", "column2"],
    }
    vsi = VectorSearchIndexSchema.from_dict(data)
    assert vsi.name == "index-name"
    assert vsi.primary_key == "primary-key"
    assert vsi.text_column == "text-column"
    assert vsi.doc_uri == "doc-uri"
    assert vsi.other_columns == ["column1", "column2"]


def test_dependencies_schemas_to_dict():
    vsi = VectorSearchIndexSchema(
        name="index-name",
        primary_key="primary-key",
        text_column="text-column",
        doc_uri="doc-uri",
        other_columns=["column1", "column2"],
    )
    schema = DependenciesSchemas(vector_search_index_schemas=[vsi])
    expected_dict = {
        "dependencies_schemas": {
            "vector_search_index": [
                {
                    "name": "index-name",
                    "primary_key": "primary-key",
                    "text_column": "text-column",
                    "doc_uri": "doc-uri",
                    "other_columns": ["column1", "column2"],
                }
            ]
        }
    }
    assert schema.to_dict() == expected_dict


def test_set_vector_search_schema_creation():
    set_vector_search_schema(
        primary_key="primary-key",
        text_column="text-column",
        doc_uri="doc-uri",
        other_columns=["column1", "column2"],
    )
    with _get_dependencies_schema() as schema:
        assert schema.vector_search_index_schemas[0].to_dict() == {
            "vector_search_index": [
                {
                    "doc_uri": "doc-uri",
                    "name": "vector_search_index",
                    "other_columns": ["column1", "column2"],
                    "primary_key": "primary-key",
                    "text_column": "text-column",
                }
            ]
        }

    with _get_dependencies_schema() as schema:
        assert schema.to_dict() is None
    assert _get_vector_search_schema() == []


def test_set_vector_search_schema_empty_creation():
    with _get_dependencies_schema() as schema:
        assert schema.to_dict() is None
