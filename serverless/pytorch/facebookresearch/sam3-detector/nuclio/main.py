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


def handler(context, event):
    context.logger.info("call handler")
    data = event.body

    buf = io.BytesIO(base64.b64decode(data["image"]))
    image = Image.open(buf).convert("RGB")

    text_prompts = data.get("text_prompts") or {}
    threshold = float(data.get("threshold", 0.5))

    results = context.user_data.model.handle(image, text_prompts, threshold)

    return context.Response(
        body=json.dumps(results),
        headers={},
        content_type="application/json",
        status_code=200,
    )
