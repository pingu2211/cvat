// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useState } from 'react';
import Button from 'antd/lib/button';
import Select from 'antd/lib/select';
import Text from 'antd/lib/typography';
import { PlusCircleOutlined } from '@ant-design/icons';

import { LabelOptColor } from './common';
import { labelTemplates, LabelTemplate } from './label-templates';

interface Props {
    labelNames: string[];
    onCreate: (label: LabelOptColor) => void;
    onCancel: () => void;
}

function compareProps(prevProps: Props, nextProps: Props): boolean {
    return (
        prevProps.onCreate === nextProps.onCreate &&
        prevProps.onCancel === nextProps.onCancel &&
        prevProps.labelNames.length === nextProps.labelNames.length &&
        prevProps.labelNames.every((value: string, index: number) => nextProps.labelNames[index] === value)
    );
}

function PickFromTemplateComponent(props: Props): JSX.Element {
    const { onCreate, onCancel, labelNames } = props;
    const [selectedTemplate, setSelectedTemplate] = useState<LabelTemplate | null>(null);
    const labels = selectedTemplate?.labels || [];

    return (
        <div className='cvat-label-constructor-pick-from-model cvat-label-constructor-pick-from-template'>
            <div>
                <Text>Select a template to pick labels from:</Text>
            </div>
            <Select
                onSelect={(name: string): void => {
                    setSelectedTemplate(labelTemplates.find((template) => template.name === name) || null);
                }}
            >
                {labelTemplates.map((template) => (
                    <Select.Option value={template.name} key={template.name}>{template.name}</Select.Option>
                ))}
            </Select>
            <Button
                className='cvat-label-constructor-done-pick-labels-button'
                type='primary'
                style={{ width: '150px' }}
                onClick={onCancel}
            >
                Done
            </Button>

            <div className='cvat-label-constructor-pick-from-model-list cvat-label-constructor-pick-from-template-list'>
                {labels.map((label) => (
                    <Button
                        key={label.name}
                        disabled={labelNames.includes(label.name)}
                        onClick={() => {
                            if (!labelNames.includes(label.name)) {
                                onCreate({ ...label });
                            }
                        }}
                    >
                        {label.name}
                        <PlusCircleOutlined />
                    </Button>
                ))}
            </div>
        </div>
    );
}

export default React.memo(PickFromTemplateComponent, compareProps);
