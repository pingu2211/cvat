# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError

from cvat.apps.engine.models import Task
from cvat.apps.events.handlers import handle_function_call
from cvat.apps.lambda_manager.models import FunctionKind


def run_configured_auto_annotation(
    db_task: Task, *, user: User, frames: Sequence[int] | None = None
) -> str | None:
    """
    Starts an auto annotation request for the model configured on the task
    (or, if the task has no configuration of its own, on its project).

    'frames' limits the run to the given task frame numbers, all of them by default.

    Returns the id of the started request, or None if no model is configured.
    """
    # Imported here because cvat.apps.lambda_manager.views imports from cvat.apps.engine.task,
    # which is one of the callers of this function
    from cvat.apps.lambda_manager.views import LambdaGateway, LambdaQueue

    config = db_task.get_auto_annotation_config()
    if not config:
        return None

    if frames is not None and not frames:
        return None

    function = LambdaGateway().get(config.function)

    if function.kind != FunctionKind.DETECTOR:
        raise ValidationError(
            f"The configured auto annotation function '{config.function}' is "
            f"a {function.kind} function. Only detectors can be run automatically."
        )

    text_prompts = None
    if function.supports_text_prompt:
        # The function has no label set of its own, it detects what the task labels ask for
        text_prompts = {label.name: label.prompt for label in db_task.get_labels() if label.prompt}
        if not text_prompts:
            raise ValidationError(
                f"The configured auto annotation function '{config.function}' is driven by "
                "text prompts, but none of the labels of the task have a prompt set."
            )

    rq_job = LambdaQueue().enqueue(
        function,
        config.threshold,
        db_task.id,
        None,  # mapping: use the default one, by label name
        False,  # cleanup: never drop the annotations the task already has
        False,  # conv_mask_to_poly
        None,  # max_distance: reid functions only
        user=user,
        request_uuid=uuid4(),
        text_prompts=text_prompts,
        frames=frames,
    )

    handle_function_call(function.id, db_task, category="batch")

    return rq_job.to_dict()["id"]
