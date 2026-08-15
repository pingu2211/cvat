// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useEffect, useState } from 'react';
import { useHistory } from 'react-router';
import Button from 'antd/lib/button';
import Select from 'antd/lib/select';
import Spin from 'antd/lib/spin';
import Text from 'antd/lib/typography/Text';
import { PlusCircleOutlined } from '@ant-design/icons';

import { getCore, LabelTemplate } from 'cvat-core-wrapper';
import { LabelOptColor } from './common';

const core = getCore();

interface Props {
    labelNames: string[];
    onCreate: (label: LabelOptColor) => void;
    onCreateMany: (labels: LabelOptColor[]) => void;
    onCancel: () => void;
}

function compareProps(prevProps: Props, nextProps: Props): boolean {
    return (
        prevProps.onCreate === nextProps.onCreate &&
        prevProps.onCreateMany === nextProps.onCreateMany &&
        prevProps.onCancel === nextProps.onCancel &&
        prevProps.labelNames.length === nextProps.labelNames.length &&
        prevProps.labelNames.every((value: string, index: number) => nextProps.labelNames[index] === value)
    );
}

function PickFromTemplateComponent(props: Props): JSX.Element {
    const {
        onCreate, onCreateMany, onCancel, labelNames,
    } = props;
    const history = useHistory();
    const [templates, setTemplates] = useState<LabelTemplate[]>([]);
    const [fetching, setFetching] = useState(true);
    const [selectedTemplate, setSelectedTemplate] = useState<LabelTemplate | null>(null);
    const labels = (selectedTemplate?.labels ?? []) as LabelOptColor[];
    const newLabels = labels.filter((label) => !labelNames.includes(label.name));

    useEffect(() => {
        let unmounted = false;

        core.labelTemplates.get({ page: 1, pageSize: 'all' })
            .then((result) => {
                if (!unmounted) {
                    setTemplates(Array.from(result));
                }
            })
            .catch(() => {
                if (!unmounted) {
                    setTemplates([]);
                }
            })
            .finally(() => {
                if (!unmounted) {
                    setFetching(false);
                }
            });

        return () => {
            unmounted = true;
        };
    }, []);

    if (fetching) {
        return (
            <div className='cvat-label-constructor-pick-from-model cvat-label-constructor-pick-from-template'>
                <Spin className='cvat-spinner' />
            </div>
        );
    }

    return (
        <div className='cvat-label-constructor-pick-from-model cvat-label-constructor-pick-from-template'>
            <div>
                {templates.length ? (
                    <Text>Select a template to pick labels from:</Text>
                ) : (
                    <Text type='secondary'>
                        No label templates yet.&nbsp;
                        <Button type='link' size='small' onClick={() => history.push('/label-templates')}>
                            Create one
                        </Button>
                    </Text>
                )}
            </div>
            {templates.length ? (
                <Select
                    className='cvat-label-constructor-template-select'
                    value={selectedTemplate?.name}
                    onSelect={(name: string): void => {
                        setSelectedTemplate(templates.find((template) => template.name === name) ?? null);
                    }}
                >
                    {templates.map((template) => (
                        <Select.Option value={template.name} key={template.id}>{template.name}</Select.Option>
                    ))}
                </Select>
            ) : null}
            <Button
                className='cvat-label-constructor-add-all-labels-button'
                disabled={!newLabels.length}
                onClick={() => onCreateMany(newLabels)}
            >
                {`Add all (${newLabels.length})`}
            </Button>
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
