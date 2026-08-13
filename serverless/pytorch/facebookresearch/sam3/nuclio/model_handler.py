# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import os

import numpy as np
import torch
from transformers import Sam3Model, Sam3Processor

CHECKPOINT = "facebook/sam3"


def mask_to_rle(mask):
    [height, width] = mask.shape
    pixels = (np.asarray(mask).reshape(-1) != 0).astype(np.uint8)
    if pixels.size == 0:
        return []

    changes = np.flatnonzero(pixels[1:] != pixels[:-1]) + 1
    rle = np.diff(np.concatenate(([0], changes, [pixels.size]))).tolist()
    if pixels[0] == 1:
        rle.insert(0, 0)

    rle.extend([0, 0, width - 1, height - 1])
    return rle


class ModelHandler:
    def __init__(self):
        token = os.environ.get("HUGGING_FACE_HUB_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "HUGGING_FACE_HUB_TOKEN is not set. SAM3 (facebook/sam3) is a gated model on "
                "Hugging Face and requires an access token with access to it. Redeploy this "
                "function with a valid token."
            )

        # torch.cuda.is_available() decides the device; a missing GPU never blocks the
        # model from loading or running, it only makes inference slower.
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # The checkpoint is deliberately left unpinned (bandit B615) so that redeploying the
        # function picks up the current facebook/sam3 weights. The repository is gated, and is
        # only reachable with the access token the operator supplies at deploy time.
        model = Sam3Model.from_pretrained(CHECKPOINT, token=token)  # nosec B615
        self.model = model.to(self.device)
        self.model.eval()
        self.processor = Sam3Processor.from_pretrained(CHECKPOINT, token=token)  # nosec B615

    def handle(self, image, pos_points, neg_points, obj_bbox, text_prompt, threshold=0.5):
        # obj_bbox, pos_points and neg_points all arrive as nested point pairs,
        # e.g. obj_bbox is [[x1, y1], [x2, y2]] rather than a flat [x1, y1, x2, y2] list
        # (see ROIHelper.translate_prompt_points in cvat/apps/lambda_manager/utils.py).
        if obj_bbox:
            (x1, y1), (x2, y2) = obj_bbox
            flat_bbox = [float(x1), float(y1), float(x2), float(y2)]
        elif pos_points or neg_points:
            # SAM3 is a box/text-promptable (concept) model, it does not take raw point
            # prompts. Approximate a box prompt from the points the user clicked, the same
            # fallback the IOG interactor uses when no box is provided.
            points = np.array((pos_points or []) + (neg_points or []), dtype=np.float64)
            x_min, y_min = points.min(axis=0)
            x_max, y_max = points.max(axis=0)
            flat_bbox = [float(x_min), float(y_min), float(x_max), float(y_max)]
        else:
            flat_bbox = None

        if not flat_bbox and not text_prompt:
            raise ValueError("SAM3 requires a bounding box, points, and/or a text prompt")

        processor_kwargs = {}
        if flat_bbox:
            processor_kwargs["input_boxes"] = [[flat_bbox]]
            processor_kwargs["input_boxes_labels"] = [[1]]
        if text_prompt:
            processor_kwargs["text"] = text_prompt

        inputs = self.processor(images=image, return_tensors="pt", **processor_kwargs).to(
            self.device
        )

        with torch.no_grad():
            outputs = self.model(**inputs)

        results = self.processor.post_process_instance_segmentation(
            outputs,
            threshold=threshold,
            mask_threshold=threshold,
            target_sizes=inputs.get("original_sizes").tolist(),
        )[0]

        masks = results["masks"]
        if len(masks) == 0:
            return None

        best_index = int(torch.as_tensor(results["scores"]).argmax())
        mask = masks[best_index]
        mask = mask.cpu().numpy() if hasattr(mask, "cpu") else np.asarray(mask)

        return mask_to_rle(mask)
