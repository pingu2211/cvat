# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import os

import numpy as np
import torch
from transformers import Sam3Config, Sam3Model, Sam3Processor

CHECKPOINT = "facebook/sam3"

DTYPES = {
    "float32": torch.float32,
    "bfloat16": torch.bfloat16,
    "float16": torch.float16,
}


def thread_count():
    """
    Size of the thread pool to give PyTorch.

    PyTorch derives its default from the host's core count, which knows nothing about
    the container's CPU allowance nor about the other Nuclio workers in the same
    container, each of which builds a pool just as wide. Oversubscribed like that, the
    threads spend more time contending for cores than computing. os.sched_getaffinity()
    respects the container's cpuset, and an explicit OMP_NUM_THREADS overrides both.
    """
    configured = os.environ.get("OMP_NUM_THREADS", "").strip()
    if configured.isdigit() and int(configured) > 0:
        return int(configured)

    try:
        with open("/sys/fs/cgroup/cpu.max", encoding="utf-8") as cpu_max:  # cgroup v2
            quota, period = cpu_max.read().split()
        if quota != "max":
            return max(1, int(quota) // int(period))
    except (OSError, ValueError):
        pass

    return max(1, len(os.sched_getaffinity(0)))


def configure_torch_runtime():
    torch.set_num_threads(thread_count())

    # Inference is one graph at a time, so the inter-op pool has nothing to overlap and
    # only adds scheduling overhead. Its size is fixed once the pool is up, hence the
    # tolerance for the call arriving too late.
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    # Denormals show up in the mask logits and are an order of magnitude slower to
    # handle than ordinary floats on x86; flushing them to zero costs no visible
    # accuracy at the mask threshold.
    torch.set_flush_denormal(True)


def model_dtype():
    """
    Precision to run the model in, from SAM3_DTYPE (default float32).

    bfloat16 halves the memory the weights take and is faster on CPUs with AVX512-BF16
    or AMX; on CPUs without them PyTorch emulates it and inference gets slower instead,
    so it stays opt-in.
    """
    name = os.environ.get("SAM3_DTYPE", "").strip().lower() or "float32"
    if name not in DTYPES:
        raise RuntimeError(f"SAM3_DTYPE must be one of {sorted(DTYPES)}, got {name!r}")
    return DTYPES[name]


def image_size():
    """
    Resolution to run the vision encoder at, from SAM3_IMAGE_SIZE (default: the
    checkpoint's own 1008).

    Cost scales with the number of patches, so e.g. 560 makes the encoder - the bulk of
    the inference time - roughly three times cheaper, at the price of some accuracy on
    small objects. Left unset, the checkpoint's configuration is used untouched.
    """
    configured = os.environ.get("SAM3_IMAGE_SIZE", "").strip()
    if not configured:
        return None

    if not configured.isdigit() or int(configured) <= 0:
        raise RuntimeError(f"SAM3_IMAGE_SIZE must be a positive integer, got {configured!r}")
    return int(configured)


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

        configure_torch_runtime()

        # torch.cuda.is_available() decides the device; a missing GPU never blocks the
        # model from loading or running, it only makes inference slower.
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = model_dtype()

        # The checkpoint is pinned to an immutable commit, so that redeploying the function
        # always fetches the same weights. To move to newer weights, replace the hashes below
        # with the one reported by <https://huggingface.co/api/models/facebook/sam3>. Each
        # call needs it spelled out as a literal: routing it through a shared constant hides
        # the pin from the revision check (bandit B615).
        model_kwargs = {}
        processor_kwargs = {}
        if configured_image_size := image_size():
            config = Sam3Config.from_pretrained(
                CHECKPOINT, revision="3c879f39826c281e95690f02c7821c4de09afae7", token=token
            )
            config.image_size = configured_image_size
            model_kwargs["config"] = config
            # The processor has to resize to match, otherwise the encoder is handed
            # patches at a resolution its position embeddings were not built for.
            processor_kwargs["size"] = {
                "height": configured_image_size,
                "width": configured_image_size,
            }

        self.model = Sam3Model.from_pretrained(
            CHECKPOINT,
            revision="3c879f39826c281e95690f02c7821c4de09afae7",
            token=token,
            dtype=self.dtype,
            **model_kwargs,
        ).to(self.device)
        self.model.eval()
        self.processor = Sam3Processor.from_pretrained(
            CHECKPOINT,
            revision="3c879f39826c281e95690f02c7821c4de09afae7",
            token=token,
            **processor_kwargs,
        )

    def handle(self, image, text_prompts: dict, threshold: float = 0.5) -> list:
        # text_prompts: { task_label_name: prompt_text }
        img_inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            vision_embeds = self.model.get_vision_features(
                pixel_values=img_inputs.pixel_values.to(self.dtype)
            )

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
