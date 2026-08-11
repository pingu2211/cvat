// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useEffect } from 'react';
import { Row, Col } from 'antd/lib/grid';
import Input from 'antd/lib/input';
import Text from 'antd/lib/typography/Text';

import { LabelInterface } from './labels-mapper';

interface Props {
    taskLabels: LabelInterface[];
    onUpdateMapping(mapping: Record<string, string>): void;
}

function LabelColorDot({ color }: { color?: string }): JSX.Element | null {
    if (!color) {
        return null;
    }

    return (
        <span
            className='cvat-label-color-dot'
            style={{ background: color }}
        />
    );
}

function TextPromptMapper(props: Props): JSX.Element {
    const { taskLabels, onUpdateMapping } = props;
    const [mapping, setMapping] = React.useState<Record<string, string>>(
        () => Object.fromEntries(taskLabels.map((label) => [label.name, label.prompt || ''])),
    );

    useEffect(() => {
        setMapping(Object.fromEntries(taskLabels.map((label) => [label.name, label.prompt || ''])));
    }, [taskLabels]);

    useEffect(() => {
        onUpdateMapping(mapping);
    }, [mapping]);

    return (
        <div className='cvat-text-prompt-mapper'>
            {taskLabels.map((label) => (
                <Row key={label.name} align='middle' justify='space-between' className='cvat-text-prompt-mapper-row'>
                    <Col span={7}>
                        <LabelColorDot color={label.color} />
                        <Text>{label.name}</Text>
                    </Col>
                    <Col span={17}>
                        <Input
                            placeholder='Text prompt (leave empty to skip this label)'
                            className='cvat-text-prompt-mapper-input'
                            value={mapping[label.name] || ''}
                            onChange={(event) => {
                                setMapping({ ...mapping, [label.name]: event.target.value });
                            }}
                        />
                    </Col>
                </Row>
            ))}
        </div>
    );
}

export default React.memo(TextPromptMapper);
