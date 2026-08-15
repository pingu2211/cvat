// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React from 'react';
import dayjs from 'dayjs';
import { Row, Col } from 'antd/lib/grid';
import Button from 'antd/lib/button';
import Tag from 'antd/lib/tag';
import Text from 'antd/lib/typography/Text';
import Paragraph from 'antd/lib/typography/Paragraph';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';

import { LabelTemplate } from 'cvat-core-wrapper';
import CVATTooltip from 'components/common/cvat-tooltip';

const MAX_VISIBLE_LABELS = 12;

interface Props {
    template: LabelTemplate;
    deleting: boolean;
    onEdit: (template: LabelTemplate) => void;
    onDelete: (template: LabelTemplate) => void;
}

function LabelTemplateItem(props: Readonly<Props>): JSX.Element {
    const {
        template, deleting, onEdit, onDelete,
    } = props;
    const { labels } = template;
    const visibleLabels = labels.slice(0, MAX_VISIBLE_LABELS);
    const hiddenCount = labels.length - visibleLabels.length;

    return (
        <Row className='cvat-label-templates-list-item' justify='center' align='middle'>
            <Col span={7}>
                <Paragraph ellipsis={{ tooltip: template.name }}>
                    <Text strong className='cvat-label-template-name'>{template.name}</Text>
                </Paragraph>
                {template.description ? (
                    <Paragraph ellipsis={{ rows: 2, tooltip: template.description }} type='secondary'>
                        {template.description}
                    </Paragraph>
                ) : null}
                <Text type='secondary'>
                    {`${labels.length} label${labels.length === 1 ? '' : 's'}`}
                </Text>
            </Col>
            <Col span={11} className='cvat-label-template-labels'>
                {visibleLabels.map((label) => (
                    <Tag key={label.name} color={label.color || undefined}>{label.name}</Tag>
                ))}
                {hiddenCount > 0 ? <Text type='secondary'>{`and ${hiddenCount} more`}</Text> : null}
            </Col>
            <Col span={4} className='cvat-label-template-info'>
                {template.owner ? (
                    <Text type='secondary'>{`Created by ${template.owner.username}`}</Text>
                ) : null}
                <br />
                <Text type='secondary'>{`Last updated ${dayjs(template.updatedDate).fromNow()}`}</Text>
            </Col>
            <Col span={2} className='cvat-label-template-actions'>
                <CVATTooltip title='Edit the template'>
                    <Button
                        className='cvat-edit-label-template-button'
                        type='text'
                        icon={<EditOutlined />}
                        disabled={deleting}
                        onClick={() => onEdit(template)}
                    />
                </CVATTooltip>
                <CVATTooltip title='Delete the template'>
                    <Button
                        className='cvat-delete-label-template-button'
                        type='text'
                        danger
                        icon={<DeleteOutlined />}
                        disabled={deleting}
                        onClick={() => onDelete(template)}
                    />
                </CVATTooltip>
            </Col>
        </Row>
    );
}

export default React.memo(LabelTemplateItem);
