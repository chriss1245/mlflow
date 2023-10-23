from typing import List, Optional

from mlflow.exceptions import MlflowException
from mlflow.metrics.base import EvaluationExample
from mlflow.metrics.genai.genai_metric import make_genai_metric
from mlflow.metrics.genai.utils import _get_latest_metric_version
from mlflow.models import EvaluationMetric
from mlflow.protos.databricks_pb2 import INTERNAL_ERROR, INVALID_PARAMETER_VALUE
from mlflow.utils.annotations import experimental
from mlflow.utils.class_utils import _get_class_from_string


@experimental
def answer_similarity(
    model: Optional[str] = None,
    metric_version: Optional[str] = None,
    examples: Optional[List[EvaluationExample]] = None,
    judge_request_timeout=60,
) -> EvaluationMetric:
    """
    This function will create a genai metric used to evaluate the answer similarity of an LLM
    using the model provided. Answer similarity will be assessed by the semantic similarity of the
    output to the ``ground_truth``, which should be specified in the ``target`` column.

    The ``target`` eval_arg must be provided as part of the input dataset or output
    predictions. This can be mapped to a column of a different name using the a ``col_mapping``
    in the ``evaluator_config``.

    An MlflowException will be raised if the specified version for this metric does not exist.

    :param model: (Optional) The model that will be used to evaluate this metric. Defaults to
        gpt-4. Your use of a third party LLM service (e.g., OpenAI) for evaluation may
        be subject to and governed by the LLM service's terms of use.
    :param metric_version: (Optional) The version of the answer similarity metric to use.
        Defaults to the latest version.
    :param examples: (Optional) Provide a list of examples to help the judge model evaluate the
        answer similarity. It is highly recommended to add examples to be used as a reference to
        evaluate the new results.
    :param judge_request_timeout: (Optional) The timeout in seconds for the judge API request.
        Defaults to 60 seconds.
    :return: A metric object
    """
    if metric_version is None:
        metric_version = _get_latest_metric_version()
    class_name = f"mlflow.metrics.genai.prompts.{metric_version}.AnswerSimilarityMetric"
    try:
        answer_similarity_class_module = _get_class_from_string(class_name)
    except ModuleNotFoundError:
        raise MlflowException(
            f"Failed to find answer similarity metric for version {metric_version}."
            f" Please check the version",
            error_code=INVALID_PARAMETER_VALUE,
        ) from None
    except Exception as e:
        raise MlflowException(
            f"Failed to construct answer similarity metric {metric_version}. Error: {e!r}",
            error_code=INTERNAL_ERROR,
        ) from None

    if examples is None:
        examples = answer_similarity_class_module.default_examples
    if model is None:
        model = answer_similarity_class_module.default_model

    return make_genai_metric(
        name="answer_similarity",
        definition=answer_similarity_class_module.definition,
        grading_prompt=answer_similarity_class_module.grading_prompt,
        examples=examples,
        version=metric_version,
        model=model,
        grading_context_columns=answer_similarity_class_module.grading_context_columns,
        parameters=answer_similarity_class_module.parameters,
        aggregations=["mean", "variance", "p90"],
        greater_is_better=True,
        judge_request_timeout=judge_request_timeout,
    )


@experimental
def strict_correctness(
    model: Optional[str] = None,
    metric_version: Optional[str] = None,
    examples: Optional[List[EvaluationExample]] = None,
    judge_request_timeout=60,
) -> EvaluationMetric:
    """
    This function will create a genai metric used to evaluate the strict correctness of an LLM
    using the model provided. Strict correctness should be used in cases where correctness is
    binary, and the source of truth is provided in the ``ground_truth``. Outputs will be
    given either the highest or lowest score depending on if they are consistent with the
    ``ground_truth``. When dealing with inputs that may have multiple correct outputs, varying
    degrees of correctness, or when considering other factors such as the comprehensiveness of
    the output, it is more appropriate to use the correctness metric instead.

    The ``ground_truth`` eval_arg must be provided as part of the input dataset or output
    predictions. This can be mapped to a column of a different name using the a ``col_mapping``
    in the ``evaluator_config``.

    An MlflowException will be raised if the specified version for this metric does not exist.

    :param model: (Optional) The model that will be used to evaluate this metric. Defaults to
        gpt-4. Your use of a third party LLM service (e.g., OpenAI) for evaluation may
        be subject to and governed by the LLM service's terms of use.
    :param metric_version: (Optional) The version of the strict correctness metric to use.
        Defaults to the latest version.
    :param examples: (Optional) Provide a list of examples to help the judge model evaluate the
        strict correctness. It is highly recommended to add examples to be used as a reference to
        evaluate the new results.
    :param judge_request_timeout: (Optional) The timeout in seconds for the judge API request.
        Defaults to 60 seconds.
    :return: A metric object
    """
    if metric_version is None:
        metric_version = _get_latest_metric_version()
    class_name = f"mlflow.metrics.genai.prompts.{metric_version}.StrictCorrectnessMetric"
    try:
        strict_correctness_class_module = _get_class_from_string(class_name)
    except ModuleNotFoundError:
        raise MlflowException(
            f"Failed to find strict correctness metric for version {metric_version}."
            f"Please check the version",
            error_code=INVALID_PARAMETER_VALUE,
        ) from None
    except Exception as e:
        raise MlflowException(
            f"Failed to construct strict correctness metric {metric_version}. Error: {e!r}",
            error_code=INTERNAL_ERROR,
        ) from None

    if examples is None:
        examples = strict_correctness_class_module.default_examples
    if model is None:
        model = strict_correctness_class_module.default_model

    return make_genai_metric(
        name="strict_correctness",
        definition=strict_correctness_class_module.definition,
        grading_prompt=strict_correctness_class_module.grading_prompt,
        examples=examples,
        version=metric_version,
        model=model,
        grading_context_columns=strict_correctness_class_module.grading_context_columns,
        parameters=strict_correctness_class_module.parameters,
        aggregations=["mean", "variance", "p90"],
        greater_is_better=True,
        judge_request_timeout=judge_request_timeout,
    )


@experimental
def relevance(
    model: Optional[str] = None,
    metric_version: Optional[str] = None,
    examples: Optional[List[EvaluationExample]] = None,
    judge_request_timeout=60,
) -> EvaluationMetric:
    """
    This function will create a genai metric used to evaluate the relevance of an LLM using the
    model provided. Relevance will be assessed by the appropriateness, significance, and
    applicability of the output with respect to the ``input`` and ``context``.

    The ``input`` and ``context`` args must be provided as part of the input dataset or output
    predictions. This can be mapped to a column of a different name using the a ``col_mapping``
    in the ``evaluator_config``.

    An MlflowException will be raised if the specified version for this metric does not exist.

    :param model: (Optional) The model that will be used to evaluate this metric. Defaults to
        gpt-4. Your use of a third party LLM service (e.g., OpenAI) for evaluation may
        be subject to and governed by the LLM service's terms of use.
    :param metric_version: (Optional) The version of the relevance metric to use.
        Defaults to the latest version.
    :param examples: (Optional) Provide a list of examples to help the judge model evaluate the
        relevance. It is highly recommended to add examples to be used as a reference to evaluate
        the new results.
    :param judge_request_timeout: (Optional) The timeout in seconds for the judge API request.
        Defaults to 60 seconds.
    :return: A metric object
    """
    if metric_version is None:
        metric_version = _get_latest_metric_version()
    class_name = f"mlflow.metrics.genai.prompts.{metric_version}.RelevanceMetric"
    try:
        relevance_class_module = _get_class_from_string(class_name)
    except ModuleNotFoundError:
        raise MlflowException(
            f"Failed to find relevance metric for version {metric_version}."
            f" Please check the version",
            error_code=INVALID_PARAMETER_VALUE,
        ) from None
    except Exception as e:
        raise MlflowException(
            f"Failed to construct relevance metric {metric_version}. Error: {e!r}",
            error_code=INTERNAL_ERROR,
        ) from None

    if examples is None:
        examples = relevance_class_module.default_examples
    if model is None:
        model = relevance_class_module.default_model

    return make_genai_metric(
        name="relevance",
        definition=relevance_class_module.definition,
        grading_prompt=relevance_class_module.grading_prompt,
        examples=examples,
        version=metric_version,
        model=model,
        grading_context_columns=relevance_class_module.grading_context_columns,
        parameters=relevance_class_module.parameters,
        aggregations=["mean", "variance", "p90"],
        greater_is_better=True,
        judge_request_timeout=judge_request_timeout,
    )
