# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import base64
import hashlib
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

    image_data = base64.b64decode(data["image"])
    image = Image.open(io.BytesIO(image_data)).convert("RGB")

    # The UI re-sends the same frame with every click of an interaction, byte for byte,
    # so a digest of the encoded image identifies it well enough for the model handler
    # to tell when it can reuse the vision features it computed for the previous call.
    image_key = hashlib.sha256(image_data).digest()

    pos_points = data.get("pos_points") or []
    neg_points = data.get("neg_points") or []
    obj_bbox = data.get("obj_bbox")
    text_prompt = _extract_text_prompt(data)

    rle = context.user_data.model.handle(
        image, pos_points, neg_points, obj_bbox, text_prompt, image_key=image_key
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
