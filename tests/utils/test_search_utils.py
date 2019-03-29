import pytest

from mlflow.entities import RunInfo, RunData, Run, SourceType, LifecycleStage, RunStatus
from mlflow.exceptions import MlflowException
from mlflow.protos.service_pb2 import SearchExpression, DoubleClause, \
    MetricSearchExpression, FloatClause, ParameterSearchExpression, StringClause
from mlflow.utils.search_utils import SearchFilter


def test_search_filter_basics():
    search_filter = "This is a filter string"
    anded_expressions = [SearchExpression(), SearchExpression()]

    # only anded_expressions
    SearchFilter(anded_expressions=anded_expressions)

    # only search filter
    SearchFilter(filter_string=search_filter)

    # both
    with pytest.raises(MlflowException) as e:
        SearchFilter(anded_expressions=anded_expressions, filter_string=search_filter)
        assert e.message.contains("Can specify only one of 'filter' or 'search_expression'")


def test_anded_expression():
    se = SearchExpression(metric=MetricSearchExpression(key="accuracy",
                                                        double=DoubleClause(comparator=">=",
                                                                            value=.94)))
    sf = SearchFilter(anded_expressions=[se])
    assert sf._parse() == [{"type": "metric", "key": "accuracy", "comparator": ">=", "value": 0.94}]


def test_anded_expression_2():
    m1 = MetricSearchExpression(key="accuracy", double=DoubleClause(comparator=">=", value=.94))
    m2 = MetricSearchExpression(key="error", double=DoubleClause(comparator="<", value=.01))
    m3 = MetricSearchExpression(key="mse", float=FloatClause(comparator=">=", value=5))
    p1 = ParameterSearchExpression(key="a", string=StringClause(comparator="=", value="0"))
    p2 = ParameterSearchExpression(key="b", string=StringClause(comparator="!=", value="blah"))
    sf = SearchFilter(anded_expressions=[SearchExpression(metric=m1),
                                         SearchExpression(metric=m2),
                                         SearchExpression(metric=m3),
                                         SearchExpression(parameter=p1),
                                         SearchExpression(parameter=p2)])

    assert sf._parse() == [
        {'comparator': '>=', 'key': 'accuracy', 'type': 'metric', 'value': 0.94},
        {'comparator': '<', 'key': 'error', 'type': 'metric', 'value': 0.01},
        {'comparator': '>=', 'key': 'mse', 'type': 'metric', 'value': 5},
        {'comparator': '=', 'key': 'a', 'type': 'parameter', 'value': '0'},
        {'comparator': '!=', 'key': 'b', 'type': 'parameter', 'value': 'blah'}
    ]


@pytest.mark.parametrize("filter_string, parsed_filter", [
    ("metric.acc >= 0.94", [{'comparator': '>=', 'key': 'acc', 'type': 'metric', 'value': '0.94'}]),
    ("metric.acc>=100", [{'comparator': '>=', 'key': 'acc', 'type': 'metric', 'value': '100'}]),
    ("params.m!='tf'", [{'comparator': '!=', 'key': 'm', 'type': 'parameter', 'value': 'tf'}]),
    ('params."m"!="tf"', [{'comparator': '!=', 'key': 'm', 'type': 'parameter', 'value': 'tf'}]),
    ('metric."legit name" >= 0.243', [{'comparator': '>=',
                                       'key': 'legit name',
                                       'type': 'metric',
                                       'value': '0.243'}]),
    ("metrics.XYZ = 3", [{'comparator': '=', 'key': 'XYZ', 'type': 'metric', 'value': '3'}]),
    ('params."cat dog" = "pets"', [{'comparator': '=',
                                    'key': 'cat dog',
                                    'type': 'parameter',
                                    'value': 'pets'}]),
    ('metrics."X-Y-Z" = 3', [{'comparator': '=', 'key': 'X-Y-Z', 'type': 'metric', 'value': '3'}]),
    ('metrics."X//Y#$$@&Z" = 3', [{'comparator': '=',
                                   'key': 'X//Y#$$@&Z',
                                   'type': 'metric',
                                   'value': '3'}]),
    ("params.model = 'LinearRegression'", [{'comparator': '=',
                                            'key': 'model',
                                            'type': 'parameter',
                                            'value': "LinearRegression"}]),
    ("metrics.rmse < 1 and params.model_class = 'LR'", [
        {'comparator': '<', 'key': 'rmse', 'type': 'metric', 'value': '1'},
        {'comparator': '=', 'key': 'model_class', 'type': 'parameter', 'value': "LR"}
    ]),
    ('', []),
    ("`metric`.a >= 0.1", [{'comparator': '>=', 'key': 'a', 'type': 'metric', 'value': '0.1'}]),
    ("`params`.model >= 'LR'", [{'comparator': '>=',
                                 'key': 'model',
                                 'type': 'parameter',
                                 'value': "LR"}]),
    ("tags.version = 'commit-hash'", [{'comparator': '=',
                                       'key': 'version',
                                       'type': 'tag',
                                       'value': "commit-hash"}]),
    ("`tags`.source_name = 'a notebook'", [{'comparator': '=',
                                            'key': 'source_name',
                                            'type': 'tag',
                                            'value': "a notebook"}]),
    ('metrics."accuracy.2.0" > 5', [{'comparator': '>',
                                     'key': 'accuracy.2.0',
                                     'type': 'metric',
                                     'value': '5'}]),
    ('params."p.a.r.a.m" != "a"', [{'comparator': '!=',
                                    'key': 'p.a.r.a.m',
                                    'type': 'parameter',
                                    'value': 'a'}]),
    ('tags."t.a.g" = "a"', [{'comparator': '=',
                             'key': 't.a.g',
                             'type': 'tag',
                             'value': 'a'}]),
])
def test_filter(filter_string, parsed_filter):
    assert SearchFilter(filter_string=filter_string)._parse() == parsed_filter


@pytest.mark.parametrize("filter_string, parsed_filter", [
    ("params.m = 'LR'", [{'type': 'parameter', 'comparator': '=', 'key': 'm', 'value': 'LR'}]),
    ("params.m = \"LR\"", [{'type': 'parameter', 'comparator': '=', 'key': 'm', 'value': 'LR'}]),
    ('params.m = "LR"', [{'type': 'parameter', 'comparator': '=', 'key': 'm', 'value': 'LR'}]),
    ('params.m = "L\'Hosp"', [{'type': 'parameter', 'comparator': '=',
                               'key': 'm', 'value': "L'Hosp"}]),
])
def test_correct_quote_trimming(filter_string, parsed_filter):
    assert SearchFilter(filter_string=filter_string)._parse() == parsed_filter


@pytest.mark.parametrize("filter_string, error_message", [
    ("metric.acc >= 0.94; metrics.rmse < 1", "Search filter contained multiple expression"),
    ("m.acc >= 0.94", "Invalid search expression type"),
    ("acc >= 0.94", "Invalid filter string"),
    ("p.model >= 'LR'", "Invalid search expression type"),
    ("model >= 'LR'", "Invalid filter string"),
    ("metrics.A > 0.1 OR params.B = 'LR'", "Invalid clause(s) in filter string"),
    ("metrics.A > 0.1 NAND params.B = 'LR'", "Invalid clause(s) in filter string"),
    ("metrics.A > 0.1 AND (params.B = 'LR')", "Invalid clause(s) in filter string"),
    ("`metrics.A > 0.1", "Invalid clause(s) in filter string"),
    ("param`.A > 0.1", "Invalid clause(s) in filter string"),
    ("`dummy.A > 0.1", "Invalid clause(s) in filter string"),
    ("dummy`.A > 0.1", "Invalid clause(s) in filter string"),
])
def test_error_filter(filter_string, error_message):
    with pytest.raises(MlflowException) as e:
        SearchFilter(filter_string=filter_string)._parse()
    assert error_message in e.value.message


@pytest.mark.parametrize("filter_string, error_message", [
    ("metric.model = 'LR'", "Expected numeric value type for metric"),
    ("metric.model = '5'", "Expected numeric value type for metric"),
    ("params.acc = 5", "Expected a quoted string value for param"),
    ("tags.acc = 5", "Expected a quoted string value for tag"),
    ("metrics.acc != metrics.acc", "Expected numeric value type for metric"),
    ("1.0 > metrics.acc", "Expected 'Identifier' found"),
])
def test_error_comparison_clauses(filter_string, error_message):
    with pytest.raises(MlflowException) as e:
        SearchFilter(filter_string=filter_string)._parse()
    assert error_message in e.value.message


@pytest.mark.parametrize("filter_string, error_message", [
    ("params.acc = LR", "value is either not quoted or unidentified quote types"),
    ("tags.acc = LR", "value is either not quoted or unidentified quote types"),
    ("params.'acc = LR", "Invalid clause(s) in filter string"),
    ("params.acc = 'LR", "Invalid clause(s) in filter string"),
    ("params.acc = LR'", "Invalid clause(s) in filter string"),
    ("params.acc = \"LR'", "Invalid clause(s) in filter string"),
    ("tags.acc = \"LR'", "Invalid clause(s) in filter string"),
    ("tags.acc = = 'LR'", "Invalid clause(s) in filter string"),
])
def test_bad_quotes(filter_string, error_message):
    with pytest.raises(MlflowException) as e:
        SearchFilter(filter_string=filter_string)._parse()
    assert error_message in e.value.message


@pytest.mark.parametrize("filter_string, error_message", [
    ("params.acc LR !=", "Invalid clause(s) in filter string"),
    ("params.acc LR", "Invalid clause(s) in filter string"),
    ("metric.acc !=", "Invalid clause(s) in filter string"),
    ("acc != 1.0", "Invalid filter string"),
    ("foo is null", "Invalid clause(s) in filter string"),
    ("1=1", "Expected 'Identifier' found"),
    ("1==2", "Expected 'Identifier' found"),
])
def test_invalid_clauses(filter_string, error_message):
    with pytest.raises(MlflowException) as e:
        SearchFilter(filter_string=filter_string)._parse()
    assert error_message in e.value.message


@pytest.mark.parametrize("entity_type, bad_comparators, entity_value", [
    ("metrics", ["~", "~="], 1.0),
    ("params", [">", "<", ">=", "<=", "~"], "'my-param-value'"),
    ("tags", [">", "<", ">=", "<=", "~"], "'my-tag-value'"),
])
def test_bad_comparators(entity_type, bad_comparators, entity_value):
    run = Run(run_info=RunInfo(
        run_uuid="hi", experiment_id=0, name="name", source_type=SourceType.PROJECT,
        source_name="source-name", entry_point_name="entry-point-name",
        user_id="user-id", status=RunStatus.FAILED, start_time=0, end_time=1,
        source_version="version", lifecycle_stage=LifecycleStage.ACTIVE),
        run_data=RunData(metrics=[], params=[], tags=[])
    )
    for bad_comparator in bad_comparators:
        bad_filter = "{entity_type}.abc {comparator} {value}".format(
            entity_type=entity_type, comparator=bad_comparator, value=entity_value)
        sf = SearchFilter(filter_string=bad_filter)
        with pytest.raises(MlflowException) as e:
            sf.filter(run)
        assert "Invalid comparator" in str(e.value.message)
