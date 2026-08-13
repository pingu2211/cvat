# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import os

import numpy as np
import torch
from transformers import Sam3Model, Sam3Processor

CHECKPOINT = "facebook/sam3"


def to_cvat_mask(mask: np.ndarray, xtl: int, ytl: int, xbr: int, ybr: int) -> list:
    # Matches serverless/openvino/base/shared.py's to_cvat_mask: the DetectionResultConverter
    # on the CVAT server (cvat/apps/lambda_manager/views.py) expects the raw, uncompressed
    # per-pixel mask values cropped to the bounding box, not a pre-computed RLE - it computes
    # the RLE itself server-side.
    flattened = mask[ytl : ybr + 1, xtl : xbr + 1].flatten().tolist()
    flattened.extend([xtl, ytl, xbr, ybr])
    return flattened


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

    def handle(self, image, text_prompts: dict, threshold: float = 0.5) -> list:
        # text_prompts: { task_label_name: prompt_text }
        img_inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            vision_embeds = self.model.get_vision_features(pixel_values=img_inputs.pixel_values)

        mask_height, mask_width = image.height, image.width
        results = []

        for label_name, prompt in text_prompts.items():
            if not prompt:
                continue

            text_inputs = self.processor(text=prompt, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.model(vision_embeds=vision_embeds, **text_inputs)

            post_processed = self.processor.post_process_instance_segmentation(
                outputs,
                threshold=threshold,
                mask_threshold=threshold,
                target_sizes=img_inputs.get("original_sizes").tolist(),
            )[0]

            for mask, box, score in zip(
                post_processed["masks"], post_processed["boxes"], post_processed["scores"]
            ):
                mask_np = mask.cpu().numpy() if hasattr(mask, "cpu") else np.asarray(mask)

                xtl, ytl, xbr, ybr = [int(round(v)) for v in box.tolist()]
                xtl = max(xtl, 0)
                ytl = max(ytl, 0)
                xbr = min(xbr, mask_width - 1)
                ybr = min(ybr, mask_height - 1)
                if xbr < xtl or ybr < ytl:
                    continue

                results.append(
                    {
                        "confidence": str(float(score)),
                        "label": label_name,
                        "mask": to_cvat_mask(mask_np, xtl, ytl, xbr, ybr),
                        "type": "mask",
                    }
                )

        return results
