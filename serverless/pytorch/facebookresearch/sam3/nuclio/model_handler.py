# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import os

import numpy as np
import torch
from transformers import Sam3Config, Sam3Model, Sam3Processor

CHECKPOINT = "facebook/sam3"

# The processor returns the prompt tensors below alongside pixel_values and the sizes
# needed for post-processing. Sam3Model.forward only accepts the prompt tensors once the
# vision features are passed in ready-made, so they are picked out by name.
PROMPT_INPUT_KEYS = ("input_ids", "attention_mask", "input_boxes", "input_boxes_labels")

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

        self._cached_image_key = None
        self._cached_vision_embeds = None

    def _vision_embeds(self, pixel_values, image_key):
        """
        Vision features for the image, reused when the previous call had the same image.

        The vision encoder - a ViT over several thousand patches - dominates the
        inference time, and the interactor is invoked on the same frame over and over as
        the annotator adds points, so reusing its output makes every call after the
        first one on a frame cost little more than prompt decoding. Only the latest
        frame is kept, because the features run to ~100 MB and a container short of
        memory is exactly what this is meant to avoid.
        """
        if image_key is not None and image_key == self._cached_image_key:
            return self._cached_vision_embeds

        with torch.no_grad():
            vision_embeds = self.model.get_vision_features(pixel_values=pixel_values)

        self._cached_image_key = image_key
        self._cached_vision_embeds = vision_embeds
        return vision_embeds

    def handle(
        self, image, pos_points, neg_points, obj_bbox, text_prompt, threshold=0.5, image_key=None
    ):
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

        vision_embeds = self._vision_embeds(inputs.pixel_values.to(self.dtype), image_key)
        prompt_inputs = {key: inputs[key] for key in PROMPT_INPUT_KEYS if key in inputs}

        with torch.no_grad():
            outputs = self.model(vision_embeds=vision_embeds, **prompt_inputs)

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
