// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { LabelType } from 'cvat-core-wrapper';
import { LabelOptColor } from './common';

export interface LabelTemplate {
    name: string;
    labels: LabelOptColor[];
}

function makeLabels(names: string[], type: LabelType = LabelType.RECTANGLE): LabelOptColor[] {
    return names.map((name) => ({ name, type, attributes: [] }));
}

const COCO_CATEGORIES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog',
    'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
    'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle',
    'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich',
    'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
    'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book',
    'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush',
];

const VEHICLE_CATEGORIES = [
    'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'van', 'trailer', 'ambulance', 'tram',
];

const PEDESTRIAN_CATEGORIES = [
    'pedestrian', 'rider', 'person sitting',
];

const ANIMAL_CATEGORIES = [
    'dog', 'cat', 'bird', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe',
];

export const labelTemplates: LabelTemplate[] = [
    { name: 'COCO (80 categories)', labels: makeLabels(COCO_CATEGORIES) },
    { name: 'Vehicles', labels: makeLabels(VEHICLE_CATEGORIES) },
    { name: 'Pedestrians', labels: makeLabels(PEDESTRIAN_CATEGORIES) },
    { name: 'Animals', labels: makeLabels(ANIMAL_CATEGORIES) },
];
