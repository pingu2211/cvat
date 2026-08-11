# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import base64
import io
import json

from PIL import Image

from model_handler import ModelHandler


def init_context(context):
    context.logger.info("Init context...  0%")
    model = ModelHandler()
    context.user_data.model = model
    context.logger.info("Init context...100%")


def _extract_text_prompt(data):
    # The interactor is only ever asked to segment a single, currently active label,
    # so text_prompts (a { label_name: prompt } mapping, same shape the detector-kind
    # invocation uses) is expected to carry at most one entry here.
    text_prompts = data.get("text_prompts")
    if isinstance(text_prompts, dict):
        return next(iter(text_prompts.values()), None)
    if isinstance(text_prompts, str):
        return text_prompts
    return None


def handler(context, event):
    context.logger.info("call handler")
    data = event.body

    buf = io.BytesIO(base64.b64decode(data["image"]))
    image = Image.open(buf).convert("RGB")

    pos_points = data.get("pos_points") or []
    neg_points = data.get("neg_points") or []
    obj_bbox = data.get("obj_bbox")
    text_prompt = _extract_text_prompt(data)

    rle = context.user_data.model.handle(
        image, pos_points, neg_points, obj_bbox, text_prompt
    )

    if rle is None:
        return context.Response(
            body=json.dumps({"shapes": []}),
            headers={},
            content_type="application/json",
            status_code=200,
        )

    return context.Response(
        body=json.dumps(
            {
                "shapes": [
                    {
                        "points": rle,
                        "group": 0,
                        "source": "semi-auto",
                        "attributes": [],
                        "occluded": False,
                        "rotation": 0,
                        "type": "mask",
                    }
                ]
            }
        ),
        headers={},
        content_type="application/json",
        status_code=200,
    )
